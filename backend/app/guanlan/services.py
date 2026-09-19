"""观澜服务目录：服务、日志来源、时区的唯一定义处。

前端的服务/来源下拉、控制台状态都以这里（通过 /api/meta）为准。
"""
from __future__ import annotations

# 时区 = 服务所在机器/容器的时区，界面按这个时区展示该服务的日志时间。
SERVICE_CATALOG = {
    "nginx-demo": {
        "name": "nginx-demo",
        "label": "Nginx 演示站",
        "timezone": "Asia/Shanghai",
        "sources": {
            "nginx-access": {
                "name": "nginx-access",
                "label": "访问日志",
                "levels": ["INFO", "WARN", "ERROR"],
            },
        },
    },
    "spring-demo": {
        "name": "spring-demo",
        "label": "Spring Boot 演示服务",
        "timezone": "Europe/London",
        "sources": {
            "spring-app": {
                "name": "spring-app",
                "label": "应用日志",
                "levels": ["DEBUG", "INFO", "WARN", "ERROR"],
            },
        },
    },
}

# filebeat fields 里允许出现的 service/source 白名单（防御未知来源写脏数据）
KNOWN_SERVICES = set(SERVICE_CATALOG.keys())
KNOWN_SOURCES = {
    (svc, src)
    for svc, meta in SERVICE_CATALOG.items()
    for src in meta["sources"]
}
