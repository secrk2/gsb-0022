"""持续从 Redis 队列批量拉取 Filebeat 事件，解析后 bulk 写入 ES。

要点：
  - LPOP 批量取（count 版），单批最多 CONSUMER_BATCH 条；
  - 空队列时短暂休眠，避免空转打满 CPU；
  - 用 event_id 作为文档 _id，重复投递天然幂等；
  - 入库时计算 latency_ms = ingested_at - @timestamp（采集延迟）；
  - 解析失败的坏消息只计数、不回队，防止毒消息卡死队列。
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

import redis
from django.conf import settings
from django.core.management.base import BaseCommand
from elasticsearch import helpers

from logs.es import ensure_index, get_es
from logs.parsers import parse_event

logger = logging.getLogger("guanlan.consumer")


class Command(BaseCommand):
    help = "消费 Redis 日志队列并批量写入 Elasticsearch"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=settings.CONSUMER_BATCH)
        parser.add_argument("--once", action="store_true", help="只处理一批后退出（测试用）")

    def handle(self, *args, **options):
        self.running = True
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))

        ensure_index()
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
        es = get_es()

        self.stdout.write(self.style.SUCCESS(
            f"消费者启动: queue={settings.LOG_QUEUE_KEY} batch={options['batch']} -> {settings.LOG_INDEX}"
        ))

        total_in, total_out, total_bad = 0, 0, 0
        while self.running:
            # 批量 LPOP，一次往返取一批
            raw_events = r.lpop(settings.LOG_QUEUE_KEY, count=options["batch"])
            if not raw_events:
                if options["once"]:
                    break
                time.sleep(settings.CONSUMER_IDLE_SLEEP)
                continue

            total_in += len(raw_events)
            actions = []
            now = datetime.now(timezone.utc)
            for raw in raw_events:
                doc = parse_event(raw)
                if doc is None:
                    total_bad += 1
                    continue
                event_time = datetime.fromisoformat(doc["@timestamp"])
                doc["ingested_at"] = now.isoformat()
                doc["latency_ms"] = max(0, int((now - event_time).total_seconds() * 1000))
                actions.append({
                    "_index": settings.LOG_INDEX,
                    "_id": doc["event_id"],
                    "_source": doc,
                })

            if actions:
                # bulk：单条失败不拖垮整批；返回 (成功数, 失败列表)
                ok, errors = helpers.bulk(
                    es, actions, raise_on_error=False, raise_on_exception=False,
                    stats_only=False,
                )
                total_out += ok
                if errors:
                    logger.error("bulk 写入部分失败 %d 条，示例: %s", len(errors), errors[:3])

            if total_in % 2000 < options["batch"]:
                self.stdout.write(
                    f"进度: 取 {total_in} / 写 {total_out} / 丢弃 {total_bad}"
                )

            if options["once"]:
                break

        self.stdout.write(self.style.SUCCESS(
            f"消费者停止。累计: 取 {total_in} / 写 {total_out} / 丢弃 {total_bad}"
        ))
