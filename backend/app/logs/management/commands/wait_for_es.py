import time

from django.core.management.base import BaseCommand

from logs.es import ensure_index, get_es


class Command(BaseCommand):
    help = "阻塞等待 Elasticsearch 可连接，并确保日志索引存在"

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=120)
        parser.add_argument("--interval", type=float, default=2.0)

    def handle(self, *args, **options):
        deadline = time.monotonic() + options["timeout"]
        es = get_es()
        while True:
            try:
                if es.ping():
                    ensure_index()
                    self.stdout.write(self.style.SUCCESS(
                        f"Elasticsearch 就绪，索引已确保存在"
                    ))
                    return
            except Exception as exc:  # 连接未就绪时反复重试
                last_exc = exc
            if time.monotonic() >= deadline:
                raise SystemExit(f"等待 Elasticsearch 超时: {last_exc}")
            time.sleep(options["interval"])
