"""观澜对外 API：控制台、日志检索、服务元数据、健康检查。

检索的大数据量防护：
  - 用 search_after 做游标翻页，绝不 from + size 深翻；
  - 单页硬性上限 PAGE_SIZE_MAX；
  - 只返回渲染所需字段，命中文档数只报告 capped 总数（relation）。
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone

import redis
from django.conf import settings
from elasticsearch import ApiError, TransportError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .es import get_es, parse_iso, recent_window, today_window

logger = logging.getLogger(__name__)

PAGE_SIZE_DEFAULT = 30
PAGE_SIZE_MAX = 100

# 检索结果只下发这些字段（堆栈在 message 内，整段返回但单条事件可控）
RETURN_FIELDS = [
    "@timestamp", "service", "source", "level", "message",
    "status_code", "method", "path", "remote_ip", "bytes_sent",
    "logger", "thread", "exception_class", "is_exception", "tz",
    "latency_ms", "event_id",
]


def _es_error_response(exc: Exception) -> Response:
    logger.exception("Elasticsearch 查询失败")
    return Response(
        {"detail": f"查询存储失败：{exc.__class__.__name__}"},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _csv(value) -> list[str]:
    """支持 ?level=ERROR 与 ?levels=ERROR,WARN 两种写法。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = []
        for part in value:
            items.extend(p.strip() for p in str(part).split(",") if p.strip())
        return items
    return [p.strip() for p in str(value).split(",") if p.strip()]


# 只对这些字段做关键字检索：message 为正文，其余为与日志强相关的短文本
# （路径/UA 等）；level/service 等枚举字段前端有专门的 chip 过滤。
KEYWORD_FIELDS = ["message", "path", "referer", "user_agent"]

# wildcard 需要转义的 Lucene 通配符/转义符；其余字符（含 . + ? 等正则元字
# 符）在 wildcard 语法里都是普通字面量，不需要转义。
_WILDCARD_ESCAPE_RE = re.compile(r"([*\\?])")


def _keyword_clause(keyword: str) -> dict | None:
    """把搜索框文本转成「子串包含」查询。

    历史实现把 q 原样作为 regexp 丢给 ES，且作用在 text 类型的 message 上：
    regexp 针对的是分词后的单个 term，既不跨行匹配原文（含空格/=/中文的明
    确字符串永远命不中），用户输入里的 . 等正则元字符又会造成大量误命中。
    现在的语义：按空白拆词，每个词都是「不区分大小写的任意位置子串」，多
    词之间为 AND（与输入框提示一致）。
    """
    terms = keyword.split()
    if not terms:
        return None
    word_clauses = []
    for word in terms:
        pattern = "*" + _WILDCARD_ESCAPE_RE.sub(r"\\\1", word) + "*"
        should = []
        for field in KEYWORD_FIELDS:
            # .keyword 上做整段原文的大小写不敏感子串匹配，结果可预期；
            # ignore_above 超过 8192 字符的超长行会没有 keyword 值，下面的
            # match 负责兜底。
            should.append({
                "wildcard": {
                    f"{field}.keyword": {
                        "value": pattern,
                        "case_insensitive": True,
                    }
                }
            })
            # text 子字段走分词匹配：兜住超长行（keyword 被截断）与 CJK
            # 单字成词后子串无法跨字匹配的场景。
            should.append({"match": {field: {"query": word, "operator": "and"}}})
        word_clauses.append({"bool": {"should": should, "minimum_should_match": 1}})
    return {"bool": {"filter": word_clauses}}


class HealthView(APIView):
    def get(self, request):
        es_ok = False
        try:
            es_ok = bool(get_es().ping())
        except Exception:
            pass
        redis_ok = False
        try:
            redis_ok = bool(redis.Redis.from_url(settings.REDIS_URL).ping())
        except Exception:
            pass
        payload = {"status": "ok" if es_ok and redis_ok else "degraded",
                   "elasticsearch": es_ok, "redis": redis_ok}
        return Response(payload, status=status.HTTP_200_OK if es_ok and redis_ok
                        else status.HTTP_503_SERVICE_UNAVAILABLE)


class MetaView(APIView):
    """服务/来源/级别/时区目录，前端表单的唯一数据源。"""

    def get(self, request):
        services = []
        for key, meta in settings.SERVICE_CATALOG.items():
            services.append({
                "service": key,
                "label": meta["label"],
                "timezone": meta["timezone"],
                "sources": [
                    {"source": sk, "label": sm["label"], "levels": sm["levels"]}
                    for sk, sm in meta["sources"].items()
                ],
            })
        levels = sorted({lvl for m in settings.SERVICE_CATALOG.values()
                         for sm in m["sources"].values() for lvl in sm["levels"]})
        return Response({
            "services": services,
            "levels": levels,
            "stale_gap_seconds": settings.STALE_GAP_SECONDS,
            "latency_warn_ms": settings.LATENCY_WARN_MS,
            "dashboard_timezone": settings.TIME_ZONE,
        })


class DashboardView(APIView):
    """控制台：今日总量/错误、服务与来源 Top、采集延迟与断流红点。"""

    def get(self, request):
        es = get_es()
        index = settings.LOG_INDEX
        now_utc = datetime.now(timezone.utc)

        # ---- 今日指标：每个服务按「它所在时区」的今日窗口分别统计 ----------
        total_count, error_count = 0, 0
        top_services, top_sources = [], []
        for svc_key, svc_meta in settings.SERVICE_CATALOG.items():
            day_start, _day_now = today_window(svc_meta["timezone"])
            try:
                resp = es.search(
                    index=index,
                    size=0,
                    track_total_hits=True,
                    query={"bool": {"filter": [
                        {"term": {"service": svc_key}},
                        {"range": {"@timestamp": {"gte": day_start.isoformat()}}},
                    ]}},
                    aggs={
                        "errors": {"filter": {"term": {"level": "ERROR"}}},
                        "by_source": {
                            "terms": {"field": "source", "size": 20},
                            "aggs": {"errors": {"filter": {"term": {"level": "ERROR"}}}},
                        },
                    },
                )
            except (ApiError, TransportError) as exc:
                return _es_error_response(exc)

            svc_count = resp["hits"]["total"]["value"]
            svc_errors = resp["aggregations"]["errors"]["doc_count"]
            total_count += svc_count
            error_count += svc_errors
            top_services.append({
                "service": svc_key, "label": svc_meta["label"],
                "timezone": svc_meta["timezone"],
                "count": svc_count, "errors": svc_errors,
            })
            src_bucket = resp["aggregations"]["by_source"]["buckets"]
            for b in src_bucket:
                src_meta = svc_meta["sources"].get(b["key"], {})
                top_sources.append({
                    "service": svc_key,
                    "source": b["key"],
                    "label": f"{svc_meta['label']} · {src_meta.get('label', b['key'])}",
                    "count": b["doc_count"],
                    "errors": b["errors"]["doc_count"],
                })

        top_services.sort(key=lambda x: x["count"], reverse=True)
        top_sources.sort(key=lambda x: x["count"], reverse=True)

        # ---- 采集链路健康：每服务最新事件时间 + 近窗平均延迟 ---------------
        # 外层窗口取近 24h：真断流超过 5 分钟时仍能拿到「最后事件时间/间隔」，
        # 而延迟均值/最近延迟单独限定在近 5 分钟内统计。
        lag_window_start = recent_window(24 * 3600)
        try:
            resp = es.search(
                index=index,
                size=0,
                query={"range": {"@timestamp": {"gte": lag_window_start.isoformat()}}},
                aggs={"by_service": {
                    "terms": {"field": "service", "size": 20},
                    "aggs": {
                        "last_event": {"max": {"field": "@timestamp"}},
                        "recent": {
                            # 近 5 分钟（用于延迟均值）
                            "filter": {"range": {"@timestamp": {
                                "gte": recent_window(300).isoformat()}}},
                            "aggs": {"avg_latency": {"avg": {"field": "latency_ms"}},
                                     "latest": {"top_hits": {"size": 1, "sort": [
                                         {"@timestamp": "desc"}],
                                         "_source": ["latency_ms", "@timestamp"]}}},
                        },
                    },
                }},
            )
        except (ApiError, TransportError) as exc:
            return _es_error_response(exc)

        pipeline_services = {}
        any_stale, any_latency = False, False
        buckets = {b["key"]: b for b in resp["aggregations"]["by_service"]["buckets"]}
        for svc_key, svc_meta in settings.SERVICE_CATALOG.items():
            b = buckets.get(svc_key)
            last_ms = b["last_event"]["value"] if b else None
            avg_lat = None
            latest_lat = None
            if b:
                avg_lat = b["recent"]["avg_latency"]["value"]
                hits = b["recent"]["latest"]["hits"]["hits"]
                if hits:
                    latest_lat = hits[0]["_source"].get("latency_ms")
            gap = (now_utc.timestamp() * 1000 - last_ms) if last_ms else None
            stale = gap is None or gap / 1000 > settings.STALE_GAP_SECONDS
            latency_alert = latest_lat is not None and latest_lat > settings.LATENCY_WARN_MS
            any_stale = any_stale or stale
            any_latency = any_latency or latency_alert
            pipeline_services[svc_key] = {
                "label": svc_meta["label"],
                "timezone": svc_meta["timezone"],
                "last_event_at": datetime.fromtimestamp(last_ms / 1000, timezone.utc).isoformat()
                if last_ms else None,
                "gap_seconds": round(gap / 1000, 1) if gap is not None else None,
                "stale": stale,
                "avg_latency_ms": round(avg_lat) if avg_lat is not None else None,
                "latest_latency_ms": latest_lat,
                "latency_alert": latency_alert,
            }

        queue_len = None
        redis_ok = True
        try:
            queue_len = redis.Redis.from_url(settings.REDIS_URL).llen(settings.LOG_QUEUE_KEY)
        except Exception:
            redis_ok = False

        healthy = not any_stale and not any_latency and redis_ok
        return Response({
            "generated_at": now_utc.isoformat(),
            "totals": {
                "today_total": total_count,
                "today_errors": error_count,
                "error_rate": round(error_count / total_count, 4) if total_count else 0,
            },
            "top_services": top_services,
            "top_sources": top_sources,
            "pipeline": {
                "healthy": healthy,
                "stale": any_stale,
                "latency_alert": any_latency,
                "redis_ok": redis_ok,
                "queue_len": queue_len,
                "stale_gap_seconds": settings.STALE_GAP_SECONDS,
                "latency_warn_ms": settings.LATENCY_WARN_MS,
                "services": pipeline_services,
            },
        })


def _encode_cursor(sort_values) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(sort_values, separators=(",", ":")).encode()
    ).decode()


def _decode_cursor(cursor: str):
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return None


class LogSearchView(APIView):
    """组合筛选 + 时间倒序 + search_after 游标分页的日志检索。"""

    def get(self, request):
        params = request.query_params
        page_size = PAGE_SIZE_DEFAULT
        if params.get("page_size"):
            try:
                page_size = max(1, min(int(params["page_size"]), PAGE_SIZE_MAX))
            except ValueError:
                return Response({"detail": "page_size 必须是整数"},
                                status=status.HTTP_400_BAD_REQUEST)

        filters = []
        for field, raw in (("service", _csv(params.get("service") or params.get("services"))),
                           ("source", _csv(params.get("source") or params.get("sources"))),
                           ("level", _csv(params.get("level") or params.get("levels")))):
            if raw:
                filters.append({"terms": {field: raw}})

        start = parse_iso(params.get("start"))
        end = parse_iso(params.get("end"))
        if start or end:
            rng = {}
            if start:
                rng["gte"] = start.isoformat()
            if end:
                rng["lte"] = end.isoformat()
            filters.append({"range": {"@timestamp": rng}})

        keyword = (params.get("q") or "").strip()
        keyword_clause = _keyword_clause(keyword)
        if keyword_clause:
            filters.append(keyword_clause)

        search_after = None
        cursor = params.get("cursor")
        if cursor:
            search_after = _decode_cursor(cursor)
            if search_after is None:
                return Response({"detail": "游标无效，请重新查询"},
                                status=status.HTTP_400_BAD_REQUEST)

        body = {
            "size": page_size,
            "track_total_hits": 10000,
            "_source": RETURN_FIELDS,
            # 必须有唯一的二级排序（tiebreaker）：同一毫秒内的日志很多，
            # 只按 @timestamp 排时相等键的相对次序不确定，search_after
            # 深翻会重复或跳过文档，翻得越深越乱。
            "sort": [{"@timestamp": "desc"}, {"event_id": "desc"}],
            "query": {"bool": {"filter": filters}},
        }
        if search_after is not None:
            body["search_after"] = search_after

        try:
            resp = get_es().search(index=settings.LOG_INDEX, body=body)
        except (ApiError, TransportError) as exc:
            return _es_error_response(exc)

        hits = resp["hits"]["hits"]
        items = [h["_source"] for h in hits]
        next_cursor = _encode_cursor(hits[-1]["sort"]) if len(hits) == page_size else None
        total = resp["hits"]["total"]

        return Response({
            "items": items,
            "page_size": page_size,
            "has_more": next_cursor is not None,
            "next_cursor": next_cursor,
            "total": {"value": total["value"], "relation": total["relation"]},
        })
