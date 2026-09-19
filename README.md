# 观澜 · Guanlan —— 日志分析系统

散落在各台机器上的日志，经 Filebeat 采集、Redis 排队、批量入 Elasticsearch，
由 Django（DRF）提供查询，Vue3 呈现「控制台」与「日志检索」。

## 架构与数据流

```
 nginx-demo  (access.log,   Asia/Shanghai)
                                   ┐
                                   ├─► Filebeat ──RPUSH──► Redis(list) ──LPOP 批量──► Django consumer ──bulk──► Elasticsearch
 spring-demo (application.log, Europe/London)  ┘  (Java 堆栈多行合并)                                         ▲
                                                                                                              │
                          Vue3 (8121) ── /api ──► Django + DRF (7121) ── search/聚合 ───────────────────────────┘
```

- **多行堆栈是一个事件**：Filebeat filestream 对 Spring 日志配置 multiline，
  凡不是以 `yyyy-MM-dd HH:mm:ss` 开头的行（`at ...`、`Caused by ...`、
  `... N more`）都并入上一条，异常整条入库，绝不一行一条。
- **削峰排队**：采集速度与入库速度解耦，日志先落 Redis list，消费者批量拉取、bulk 写入。
- **幂等**：以 Filebeat 的文件路径+offset 派生 `event_id` 作为 ES `_id`，重复投递不产生重复文档。
- **按服务时区展示**：日志时间统一以 UTC 存储，界面按每条事件所属服务的时区渲染
  （nginx 演示为 `Asia/Shanghai`，Spring 演示为 `Europe/London`）。

## 一键启动

前置：Docker + Docker Compose v2。

```bash
docker compose up -d --build
```

首次构建 Spring 镜像需要拉 Maven 依赖，耗时较长。启动后两个演示服务会**持续写日志**，
稍等 10~30 秒即可在界面查到数据。

| 入口 | 地址 |
|---|---|
| 前端（控制台 / 日志检索） | http://localhost:8121 |
| 后端 API | http://localhost:7121/api |
| 后端健康检查 | http://localhost:7121/api/health |

停止与清理（含数据卷）：

```bash
docker compose down -v
```

## 功能说明

### 控制台（/dashboard，5 秒自动刷新）
- 今日日志总量、今日错误数（含错误率）；
- 按**服务**、按**来源**（服务/来源）的今日事件量 Top 排行；
- 采集链路红点：
  - **断流**：某服务超过 `STALE_GAP_SECONDS`（默认 60s）没有新事件；
  - **延迟**：最近事件的采集延迟（事件时间→入库时间）超过 `LATENCY_WARN_MS`（默认 15s）；
  - 同时展示 Redis 队列积压量；异常时总状态与对应服务亮红点（圆点+文字双通道）。

### 日志检索（/search）
- 组合筛选：时间范围、关键字、级别、服务、来源（来源随服务联动）；
- 结果按时间倒序；
- **大结果集不拖垮页面**：服务端用 `search_after` 游标分页（单页默认 30、上限 100），
  只回传渲染所需字段；命中数只报告上限值（`10000+`），前端按「加载更多」逐页取，
  绝不一整包几万条塞进浏览器；
- 时间筛选的解释时区跟随所选服务（单选时）或手选时区；
- Java 堆栈行可点击展开整条，并显示 logger / 线程 / 异常类 / 采集延迟。

## 目录结构

```
.
├── docker-compose.yml
├── backend/                Django + DRF（7121），同一镜像承担 web / consumer 两角色
│   └── app/
│       ├── guanlan/        项目配置、服务目录（时区唯一定义处）
│       └── logs/
│           ├── es.py       ES 客户端 / mapping / 时间窗口
│           ├── parsers.py  nginx combined 与 Spring(含堆栈) 解析
│           ├── views.py    /api/dashboard /api/logs/search /api/meta /api/health
│           └── management/commands/ wait_for_es、consume_logs
├── frontend/               Vue3 + Vite，构建后由容器内 nginx 在 8121 提供并反代 /api
├── filebeat/filebeat.yml   双输入 + multiline + Redis 输出
└── services/
    ├── nginx-demo/         nginx + 持续混合状态码流量（写真实 access.log）
    └── spring-demo/        Spring Boot 定时日志 + 周期性多行堆栈异常
```

## 主要配置（docker-compose.yml 环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `LOG_INDEX` | `guanlan-logs` | ES 索引名 |
| `LOG_QUEUE_KEY` | `guanlan:logqueue` | Redis 队列 key |
| `CONSUMER_BATCH` | `200` | 每批 LPOP / bulk 条数 |
| `STALE_GAP_SECONDS` | `60` | 断流判定阈值 |
| `LATENCY_WARN_MS` | `15000` | 采集延迟告警阈值 |
| `ES_JAVA_OPTS` | `-Xms512m -Xmx512m` | 单机演示 ES 堆大小 |

## 本地开发（不走容器）

- 后端：`pip install -r backend/requirements.txt`，导出
  `ES_HOSTS` / `REDIS_URL` 后 `python manage.py runserver 0.0.0.0:7121`，
  另起 `python manage.py consume_logs`。
- 前端：`cd frontend && npm install && npm run dev`（8121，已配置 `/api` 到 7121 的代理）。
