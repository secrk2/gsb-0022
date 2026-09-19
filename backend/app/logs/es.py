"""Elasticsearch 客户端、索引映射与时间窗口工具。"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from elasticsearch import Elasticsearch

_client: Elasticsearch | None = None

INDEX_MAPPING = {
    "dynamic": "false",
    "properties": {
        # 事件发生时间（统一存 UTC），检索/排序的主轴
        "@timestamp": {"type": "date"},
        # 消费者写入时间（UTC），用于计算采集延迟
        "ingested_at": {"type": "date"},
        "latency_ms": {"type": "long"},
        "service": {"type": "keyword"},
        "source": {"type": "keyword"},
        # "nginx-demo/nginx-access"，控制台按来源聚合用
        "source_key": {"type": "keyword"},
        "level": {"type": "keyword"},
        "message": {
            "type": "text",
            # 中英混合：standard 分词，关键字检索同时对 message.keyword 兜底
            "fields": {"keyword": {"type": "keyword", "ignore_above": 8192}},
        },
        # Spring Boot 解析字段
        "logger": {"type": "keyword"},
        "thread": {"type": "keyword"},
        "exception_class": {"type": "keyword"},
        "is_exception": {"type": "boolean"},
        # nginx access 解析字段
        "remote_ip": {"type": "keyword"},
        "method": {"type": "keyword"},
        "path": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 2048}},
        },
        "status_code": {"type": "integer"},
        "bytes_sent": {"type": "long"},
        "referer": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 2048}},
        },
        "user_agent": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 2048}},
        },
        "host": {"type": "keyword"},
        "file_path": {"type": "keyword"},
        "file_offset": {"type": "long"},
        "event_id": {"type": "keyword"},
        "tz": {"type": "keyword"},
    },
}

INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "2s",
}


def get_es() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(
            hosts=settings.ES_HOSTS,
            request_timeout=settings.ES_TIMEOUT,
            max_retries=3,
            retry_on_timeout=True,
        )
    return _client


def ensure_index() -> None:
    """幂等建索引；已存在则不改动映射（演示系统）。"""
    es = get_es()
    if not es.indices.exists(index=settings.LOG_INDEX):
        es.indices.create(
            index=settings.LOG_INDEX,
            mappings=INDEX_MAPPING,
            settings=INDEX_SETTINGS,
        )


def today_window(tz_name: str) -> tuple[datetime, datetime]:
    """返回某时区下「今日 00:00 ~ 现在」的 UTC 时间区间。"""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    return start_local.astimezone(ZoneInfo("UTC")), now_local.astimezone(ZoneInfo("UTC"))


def parse_iso(value: str | None, *, default: datetime | None = None) -> datetime | None:
    """宽松解析前端传入的 ISO8601；无时区则按 UTC 处理。"""
    if not value:
        return default
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def recent_window(seconds: int) -> datetime:
    return datetime.now(ZoneInfo("UTC")) - timedelta(seconds=seconds)
