# TrendRadar 系统总览

## 目录

1. [系统架构](#系统架构)
2. [核心流程](#核心流程)
3. [数据流向](#数据流向)
4. [运行模式](#运行模式)
5. [配置文件说明](#配置文件说明)
6. [相关文档](#相关文档)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TrendRadar 系统架构                            │
└─────────────────────────────────────────────────────────────────────────┘

┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   数据源层    │     │   处理层      │     │   输出层      │
│               │     │               │     │               │
│ ┌───────────┐ │     │ ┌───────────┐ │     │ ┌───────────┐ │
│ │ 同花顺7x24│─┼────▶│ │关键词过滤 │─┼────▶│ │   邮件    │ │
│ │  快讯 API │ │     │ └───────────┘ │     │ └───────────┘ │
│ └───────────┘ │     │       │       │     │ ┌───────────┐ │
│               │     │       ▼       │     │ │ 飞书/钉钉  │ │
│ ┌───────────┐ │     │ ┌───────────┐ │     │ └───────────┘ │
│ │  RSS 源   │─┼────▶│ │ AI 分析   │─┼────▶│ ┌───────────┐ │
│ │ (可选)    │ │     │ │ (CrewAI)  │ │     │ │ Telegram  │ │
│ └───────────┘ │     │ └───────────┘ │     │ └───────────┘ │
│               │     │       │       │     │ ┌───────────┐ │
│ ┌───────────┐ │     │       ▼       │     │ │ 推送队列  │ │
│ │  热榜平台  │─┼────▶│ ┌───────────┐ │     │ │ (飞书API) │ │
│ │ (可选)    │ │     │ │ 报告生成  │─┼────▶│ └───────────┘ │
│ └───────────┘ │     │ └───────────┘ │     │               │
└───────────────┘     └───────────────┘     └───────────────┘
```

### 容器服务

| 容器 | 镜像 | 端口 | 功能 |
|------|------|------|------|
| `trendradar` | wantcat/trendradar | 8080 | 核心服务：爬虫 + AI 分析 + 推送 |
| `langbot` | rockchin/langbot | 5300 | LangBot：飞书机器人交互 |
| `langbot_plugin_runtime` | rockchin/langbot | 5401 | LangBot 插件运行时 |
| `feishu_push` | python:3.11-slim | - | 飞书 API 推送服务 |

---

## 核心流程

### 完整执行流程

```
                    ┌─────────────────┐
                    │     启动        │
                    │  TrendRadar     │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐          ┌─────────────────┐
    │  Daemon 模式    │          │   Cron 模式     │
    │  (10秒轮询)     │          │  (定时执行)     │
    └────────┬────────┘          └────────┬────────┘
              │                             │
              └──────────────┬──────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │    数据采集         │
                  │  - 同花顺 7x24 API  │
                  │  - RSS 订阅源       │
                  │  - 热榜平台 (可选)   │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │    去重过滤         │
                  │  - 新闻去重         │
                  │  - 新鲜度过滤       │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   关键词匹配        │
                  │  frequency_words.txt │
                  │  - 全局过滤词       │
                  │  - 关键词分组       │
                  └──────────┬──────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐          ┌─────────────────┐
    │  Phase 1:       │          │  Phase 2:       │
    │  即时推送       │          │  AI 分析        │
    │  (原始新闻)     │          │  (增强推送)     │
    └────────┬────────┘          └────────┬────────┘
              │                             │
              │    ┌─────────────────┐      │
              │    │  推送渠道       │      │
              └───▶│  - 邮件         │◀─────┘
                   │  - 飞书 Webhook │
                   │  - 钉钉         │
                   │  - Telegram     │
                   │  - 推送队列     │
                   └─────────────────┘
                             │
                             ▼
                   ┌─────────────────┐
                   │ Feishu Push     │
                   │ Service         │
                   │ (飞书 API 推送)  │
                   └─────────────────┘
```

### Phase 1: 即时推送 (原始新闻)

当发现新新闻时立即触发：

1. **内容**: 原始新闻标题、摘要、链接、匹配的关键词
2. **格式**:
   - 邮件: HTML 格式
   - 其他: 纯文本 Markdown
3. **目标**: 所有配置的推送渠道 + 推送队列

### Phase 2: AI 分析 (增强推送)

新闻进入 AI 分析队列后触发：

1. **分析器**: SimpleAnalyzer 或 CrewAI
2. **输出**:
   - 摘要 (summary)
   - 关键词 (keywords)
   - 情感分析 (sentiment)
   - 重要性评分 (importance)
3. **推送**:
   - 邮件主题: `[AI分析] xxx`
   - 飞书: 富文本卡片

---

## 数据流向

### 推送队列机制

```
┌──────────────────────────────────────────────────────────────┐
│                       TrendRadar Daemon                       │
│                                                               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │
│  │ 新闻采集    │────▶│ 关键词过滤  │────▶│ 即时推送    │    │
│  └─────────────┘     └─────────────┘     └──────┬──────┘    │
│                                                  │           │
│                             ┌────────────────────┘           │
│                             │                                │
│                             ▼                                │
│                      ┌─────────────┐                         │
│                      │ AI 分析队列 │                         │
│                      └──────┬──────┘                         │
│                             │                                │
│                             ▼                                │
│                      ┌─────────────┐                         │
│                      │ AI 增强推送 │                         │
│                      └──────┬──────┘                         │
│                             │                                │
└─────────────────────────────┼────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ 推送队列目录    │
                    │ .push_queue/    │
                    │                 │
                    │ • raw 消息      │
                    │ • ai_analysis   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Feishu Push     │
                    │ Service         │
                    │                 │
                    │ 轮询队列 (2s)   │
                    │ 调用飞书 API    │
                    │ 移到 .processed │
                    └─────────────────┘
```

### 推送队列文件格式

**文件位置**: `config/.push_queue/*.json`

```json
{
  "id": "uuid",
  "timestamp": "2026-02-02T10:30:00",
  "type": "raw | ai_analysis",
  "subject": "邮件主题",
  "text_content": "纯文本内容",
  "html_content": "HTML内容 (可选)",
  "items": [
    {
      "title": "新闻标题",
      "url": "https://...",
      "summary": "摘要",
      "published_at": "发布时间",
      "matched_keywords": ["关键词1", "关键词2"]
    }
  ],
  "ai_result": {
    "summary": "AI摘要",
    "keywords": ["AI提取的关键词"],
    "sentiment": "positive|negative|neutral",
    "importance": 1-5
  },
  "status": "pending"
}
```

---

## 运行模式

### 1. Daemon 模式 (推荐)

```bash
# .env 配置
RUN_MODE=daemon
CRAWLER_POLL_INTERVAL=10      # 轮询间隔 (秒)
CRAWLER_ENABLE_AI=true        # 启用 AI 分析
CRAWLER_USE_CREWAI=true       # 使用 CrewAI
CRAWLER_VERBOSE=true          # 详细日志
```

**特点**:
- 10秒轮询，实时发现新内容
- 即时推送 + AI 增强推送
- 适合需要实时监控的场景

### 2. Cron 模式

```bash
# .env 配置
RUN_MODE=cron
CRON_SCHEDULE=*/30 * * * *    # 每30分钟执行一次
```

**特点**:
- 定时执行，资源消耗低
- 适合定期汇总的场景

### 3. Once 模式

```bash
# .env 配置
RUN_MODE=once
```

**特点**:
- 执行一次后退出
- 适合手动触发或调试

---

## 配置文件说明

### 配置文件清单

| 文件 | 用途 | 文档 |
|------|------|------|
| `config/config.yaml` | 主配置文件 | 本文件内有详细注释 |
| `config/frequency_words.txt` | 关键词过滤规则 | [KEYWORD_FILTER.md](KEYWORD_FILTER.md) |
| `config/ai_analysis_prompt.txt` | AI 分析提示词 | [AI_PROMPT_GUIDE.md](AI_PROMPT_GUIDE.md) |
| `docker/.env` | Docker 环境变量 | [DOCKER_ENV.md](DOCKER_ENV.md) |

### config.yaml 核心配置

```yaml
# 1. 数据源
platforms:
  enabled: false              # 热榜平台 (目前关闭)

rss:
  enabled: true               # RSS 订阅 (开启)

# 2. 自定义爬虫 (同花顺 7x24)
custom_crawlers:
  enabled: true
  sources:
    - id: "ths-realtime"
      name: "同花顺7x24"
      type: "tapp"            # 使用 tapp API

# 3. 报告模式
report:
  mode: "incremental"         # 增量模式：只推送新内容

# 4. 显示区域
display:
  regions:
    standalone: true          # 独立展示区
    ai_analysis: false        # AI 分析区 (通过 daemon 单独推送)

# 5. AI 分析 (定时报告用，daemon 有独立的 AI 分析)
ai_analysis:
  enabled: false              # 定时报告的 AI 分析关闭
```

### frequency_words.txt 格式

```
# 全局过滤词 (匹配则排除)
[GLOBAL_FILTER]
广告
推广

# 关键词分组 (匹配则标记)
[WORD_GROUPS]
[地缘政治/能源]
石油
伊朗
美国

[科技/AI]
人工智能
ChatGPT
大模型
```

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [AI_PROMPT_GUIDE.md](AI_PROMPT_GUIDE.md) | AI 分析提示词详解 |
| [LANGBOT_PUSH_GUIDE.md](LANGBOT_PUSH_GUIDE.md) | LangBot 集成与飞书推送 |
| [LANGBOT_FEISHU_SETUP.md](LANGBOT_FEISHU_SETUP.md) | LangBot 飞书配置指南 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构详解 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 常见问题排查 |

---

## 运行时关键参数

### 爬虫参数

| 参数 | 默认值 | 位置 | 说明 |
|------|--------|------|------|
| `page_size` | 100 | config.yaml / 代码 | 单次 API 请求获取的新闻条数 |
| `poll_interval` | 10秒 | .env `CRAWLER_POLL_INTERVAL` | 轮询间隔 |
| `content_fetch_delay` | 0.3秒 | 代码 | 获取完整内容时的请求间隔 |

### 存储参数

| 参数 | 默认值 | 位置 | 说明 |
|------|--------|------|------|
| `MAX_ITEMS` | 10000 | config.yaml | 数据库最大存储条目数 |
| `MAX_DAYS` | 30 | config.yaml | 数据最大保留天数 |
| `MAX_DISPLAY_ITEMS` | 100 | config.yaml | 网页显示最大条目数 |

### 推送参数

| 参数 | 默认值 | 位置 | 说明 |
|------|--------|------|------|
| 飞书单次推送 | 10条 | feishu_push_service.py | 单条消息最多包含 10 条新闻 |
| 推送队列轮询 | 2秒 | feishu_push_service.py | 队列检查间隔 |

### AI 分析参数

| 参数 | 默认值 | 位置 | 说明 |
|------|--------|------|------|
| `WORKERS` | 2 | config.yaml / 代码 | AI 分析并发线程数 |
| `QUEUE_SIZE` | 100 | 代码 | AI 分析队列最大长度 |
| `TIMEOUT` | 60秒 | 代码 | 单次 AI 分析超时时间 |

### Prompt 文件

| 文件 | 说明 | 文档 |
|------|------|------|
| `config/ai_analysis_prompt.txt` | AI 新闻分析提示词 | [AI_PROMPT_GUIDE.md](AI_PROMPT_GUIDE.md) |
| `config/ai_translation_prompt.txt` | AI 翻译提示词 | - |

---

## 快速命令参考

```bash
# 查看所有服务状态
docker ps -a --filter name=trendradar --filter name=langbot --filter name=feishu

# 查看 TrendRadar 日志
docker logs -f trendradar

# 查看飞书推送日志
docker logs -f feishu_push

# 重启所有服务
cd docker
docker compose restart trendradar
docker compose -f docker-compose-langbot.yml restart

# 手动执行一次爬取 (调试用)
docker exec trendradar python scripts/run_crawler_daemon.py --once --verbose
```

---

最后更新: 2026-02-02
