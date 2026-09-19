"""把 Filebeat 投递到 Redis 的原始事件解析成 ES 文档。

Filebeat 侧已完成 Java 堆栈的多行合并：一条 event 的 message 可能含换行，
这里不再做行级合并，只做「单事件 -> 结构化字段」的解析。

时间处理：
  - nginx combined 日志自带 +0800 偏移，直接带时区解析；
  - Spring Boot 的 logback 模式不带偏移，按服务所在时区（服务目录）解释；
  - 统一转成 UTC 存 @timestamp。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from guanlan.services import KNOWN_SOURCES

logger = logging.getLogger(__name__)

NGINX_RE = re.compile(
    r'^(?P<remote_ip>\S+)\s+\S+\s+(?P<user>\S+)\s+'
    r'\[(?P<time_local>[^\]]+)\]\s+'
    r'"(?P<request>[^"]*)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>\d+|-)\s+'
    r'"(?P<referer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"\s*$'
)

# logback: 2026-09-19 10:00:00.123 ERROR [scheduling-1] c.e.DemoTask - 消息
# 字段间隔只用空格/制表符匹配，绝不吃掉换行（避免多行堆栈时越过首行）。
SPRING_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)[ \t]+'
    r'(?P<level>[A-Z]{4,5})[ \t]+'
    r'\[(?P<thread>[^\]]+)\][ \t]+'
    r'(?P<logger>\S+)[ \t]+-[ \t]+'
)

EXCEPTION_RE = re.compile(
    r'^(?P<cls>(?:[a-zA-Z_$][\w$]*\.)*[A-Za-z_$][\w$]*(?:Exception|Error|Throwable))'
    r'(?::\s*(?P<detail>.*))?$',
    re.MULTILINE,
)

SPRING_TS_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f",
                     "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def _fallback_event_id(event: dict, message: str) -> str:
    path = str(event.get("log", {}).get("file", {}).get("path") or "")
    offset = event.get("log", {}).get("offset")
    if path and offset is not None:
        return f"{path}:{offset}"
    digest = hashlib.sha1(f"{path}|{message}".encode("utf-8", "replace")).hexdigest()[:16]
    return f"anon:{digest}"


def _beats_timestamp(event: dict) -> datetime | None:
    raw = event.get("@timestamp")
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(ZoneInfo("UTC"))
    except (ValueError, TypeError):
        return None


def _parse_nginx_time(value: str) -> datetime | None:
    # 19/Sep/2026:10:20:30 +0800
    try:
        dt = datetime.strptime(value.strip(), "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    return dt.astimezone(ZoneInfo("UTC"))


def _parse_spring_time(value: str, tz_name: str) -> datetime | None:
    for fmt in SPRING_TS_FORMATS:
        try:
            dt = datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=ZoneInfo(tz_name)).astimezone(ZoneInfo("UTC"))
    return None


def _nginx_level(status: int) -> str:
    if status >= 500:
        return "ERROR"
    if status >= 400:
        return "WARN"
    return "INFO"


def parse_event(raw: str | bytes | dict) -> dict | None:
    """原始 Redis 元素 -> ES 文档 dict；无法识别返回 None。"""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", "replace")
    if isinstance(raw, str):
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("丢弃非 JSON 事件: %r", raw[:200])
            return None
    else:
        event = raw
    if not isinstance(event, dict):
        return None

    fields = event.get("fields") or {}
    service = str(fields.get("service") or "").strip()
    source = str(fields.get("source") or "").strip()
    if (service, source) not in KNOWN_SOURCES:
        logger.warning("丢弃未知 service/source: %s/%s", service, source)
        return None

    tz_name = settings.SERVICE_CATALOG[service]["timezone"]
    message = str(event.get("message") or "").rstrip("\n")
    if not message:
        return None

    doc: dict = {
        "@timestamp": None,
        "service": service,
        "source": source,
        "source_key": f"{service}/{source}",
        "level": "INFO",
        "message": message,
        "host": str((event.get("host") or {}).get("name") or service),
        "file_path": str(event.get("log", {}).get("file", {}).get("path") or ""),
        "file_offset": event.get("log", {}).get("offset"),
        "event_id": str(event.get("event_id") or _fallback_event_id(event, message)),
        "tz": tz_name,
    }

    ts = _beats_timestamp(event)

    if source == "nginx-access":
        m = NGINX_RE.match(message)
        if m:
            status = int(m.group("status"))
            request = m.group("request").split()
            doc.update(
                level=_nginx_level(status),
                status_code=status,
                remote_ip=m.group("remote_ip"),
                method=request[0] if request else "",
                path=request[1] if len(request) > 1 else "",
                bytes_sent=int(m.group("bytes")) if m.group("bytes").isdigit() else 0,
                referer=m.group("referer"),
                user_agent=m.group("user_agent"),
            )
            parsed_ts = _parse_nginx_time(m.group("time_local"))
            if parsed_ts:
                ts = parsed_ts
    elif source == "spring-app":
        m = SPRING_RE.match(message)
        if m:
            body = message[m.end():]
            doc.update(
                level=m.group("level").upper(),
                thread=m.group("thread"),
                logger=m.group("logger"),
                message=message if "\n" in message else body,
            )
            parsed_ts = _parse_spring_time(m.group("ts"), tz_name)
            if parsed_ts:
                ts = parsed_ts
            if "\n" in message:
                # 多行事件：Java 异常堆栈整体入库
                doc["is_exception"] = True
                exc = EXCEPTION_RE.search(message)
                if exc:
                    doc["exception_class"] = exc.group("cls")
            else:
                doc["is_exception"] = False

    if ts is None:
        logger.warning("事件无可用时间戳，丢弃: service=%s", service)
        return None
    doc["@timestamp"] = ts.isoformat()
    return doc
