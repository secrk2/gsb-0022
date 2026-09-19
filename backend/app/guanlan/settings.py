"""
观澜（Guanlan）日志分析系统 —— Django 配置。

环境变量（compose 注入）：
  ES_HOSTS            Elasticsearch 地址，多个用逗号分隔
  REDIS_URL           日志队列
  LOG_INDEX           ES 索引名
  LOG_QUEUE_KEY       Redis list 的 key
  STALE_GAP_SECONDS   判定「断流」的无新事件秒数
  LATENCY_WARN_MS     采集延迟告警阈值（毫秒）
"""
import os

from .services import SERVICE_CATALOG

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-guanlan-demo-do-not-use-in-prod",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "logs",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "guanlan.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "guanlan.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "data", "guanlan.sqlite3"),
    }
}

USE_TZ = True
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": None,
}

CORS_ALLOW_ALL_ORIGINS = True

# ---- 观澜业务配置 -----------------------------------------------------------

ES_HOSTS = [h.strip() for h in os.environ.get("ES_HOSTS", "http://es:9200").split(",") if h.strip()]
ES_REQUEST_TIMEOUT = float(os.environ.get("ES_REQUEST_TIMEOUT", "10"))

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
LOG_QUEUE_KEY = os.environ.get("LOG_QUEUE_KEY", "guanlan:logqueue")
LOG_INDEX = os.environ.get("LOG_INDEX", "guanlan-logs")

CONSUMER_BATCH = int(os.environ.get("CONSUMER_BATCH", "200"))
CONSUMER_IDLE_SLEEP = float(os.environ.get("CONSUMER_IDLE_SLEEP", "0.5"))

# 超过该秒数没有任何新事件 -> 红点（断流）
STALE_GAP_SECONDS = int(os.environ.get("STALE_GAP_SECONDS", "60"))
# 采集延迟（事件时间 -> 入库时间）超过该毫秒数 -> 红点
LATENCY_WARN_MS = int(os.environ.get("LATENCY_WARN_MS", "15000"))

# 服务目录：时区与控制台/检索的元数据同源
SERVICE_CATALOG = SERVICE_CATALOG
