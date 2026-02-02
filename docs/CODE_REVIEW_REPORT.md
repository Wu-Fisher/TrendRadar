# StockTrendRadar 代码审查报告

> **版本**: v2.0
> **日期**: 2026-02-02
> **审查范围**: 全项目代码架构、数据结构、配置系统、代码质量、日志系统
> **状态**: P0/P1/P2 全部完成

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [项目架构](#2-项目架构)
3. [新增模块说明](#3-新增模块说明)
4. [遗留待办](#4-遗留待办)
5. [验证命令](#5-验证命令)

---

## 1. 执行摘要

### 1.1 审查目标

本次代码审查的核心目标是：
- 确保数据结构和接口层的解耦与鲁棒性
- 统一配置系统，便于后续开发和运维
- 减少代码重复，提升架构清晰度
- 引入日志系统替代 print() 输出
- 为长期目标（历史分析、pywencai 接入、Web 管理界面）奠定基础

### 1.2 实施完成清单

| 优先级 | 任务 | 状态 | 说明 |
|--------|------|------|------|
| P0 | 创建 `trendradar/constants.py` | ✅ | 集中管理 BatchSizes, Timeouts, Limits 等常量 |
| P0 | 修复配置默认值不一致 | ✅ | feishu_batch_size 30000→29000 |
| P0 | Daemon 支持多账号推送 | ✅ | 新增 4 个 webhook 函数 |
| P0 | 添加 EMAIL_ENABLED 配置开关 | ✅ | 支持禁用邮件推送 |
| P0 | 消除配置键名冗余检查 | ✅ | 移除大小写双重检查 |
| P1 | 创建 `trendradar/models/` 模块 | ✅ | 统一数据模型，减少重复定义 |
| P1 | 创建 `trendradar/logging.py` | ✅ | 统一日志配置 |
| P1 | 字段命名统一 | ✅ | mobileUrl → mobile_url |
| P1 | Daemon print → logging | ✅ | 63 处迁移完成 |
| P2 | 创建 `ConfigManager` 类 | ✅ | 12+ 个 frozen dataclass |
| P2 | Daemon 使用 ConfigManager | ✅ | 类型安全配置访问 |

### 1.3 Git 提交记录

```
307cb1a refactor: 迁移 daemon 使用 ConfigManager (P2-3)
da9cbca feat: 添加 ConfigManager 类型安全配置管理器 (P2-1, P2-2)
311b567 docs: 更新 CODE_REVIEW_REPORT P1-2 状态
9d92642 refactor: 迁移 daemon 所有 print 到 logging (P1-2a)
```

---

## 2. 项目架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     入口层                                   │
├──────────────────────┬──────────────────────────────────────┤
│  __main__.py (Cron)  │  run_crawler_daemon.py (Daemon)      │
│  - 完整报告流程       │  - 10秒轮询 + 即时推送               │
│  - dispatcher        │  - ConfigManager 类型安全配置        │
└──────────────────────┴──────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     核心模块层                               │
├───────────────┬──────────────────┬──────────────────────────┤
│  models/      │  ai/             │  notification/           │
│  - 统一数据类  │  - analyzers/    │  - dispatcher.py        │
│  - 工具函数   │  - queue/        │  - senders.py           │
├───────────────┼──────────────────┼──────────────────────────┤
│  core/        │  crawler/        │  logging.py             │
│  - loader.py  │  - custom/       │  - 统一日志配置          │
│  - config_manager.py │  - rss/   │                          │
└───────────────┴──────────────────┴──────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     存储层                                   │
│  storage/: SQLite + S3 兼容                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 架构优点

1. **模块化设计良好**：爬虫、AI、通知、存储模块边界清晰
2. **多数据源支持**：RSS、同花顺 TAPP API、热榜平台
3. **多渠道推送**：支持 9+ 推送渠道（飞书、钉钉、企微、Telegram 等）
4. **Docker 部署成熟**：compose 文件完整，支持多种运行模式
5. **配置文件注释详尽**：config.yaml 易于理解
6. **类型安全配置**：ConfigManager 提供 IDE 自动补全

### 2.3 运行模式

| 模式 | 用途 | 配置 |
|------|------|------|
| `daemon` | 10 秒轮询，即时推送 | `RUN_MODE=daemon` |
| `cron` | 定时执行完整报告 | `RUN_MODE=cron` |
| `once` | 单次执行 | `RUN_MODE=once` |

---

## 3. 新增模块说明

### 3.1 统一数据模型 (`trendradar/models/`)

```
trendradar/models/
├── __init__.py      # 统一导出所有数据模型
├── base.py          # ToDictMixin, BaseResult, BaseAnalysisResult, BaseNewsItem
├── analysis.py      # NewsAnalysisResult, BatchAnalysisResult, TranslationResult
└── queue.py         # TaskStatus, QueueTask
```

**核心类型：**

```python
from trendradar.models import (
    NewsAnalysisResult,      # 单条新闻分析结果
    BatchAnalysisResult,     # 批量分析结果（热榜 AI 分析）
    TranslationResult,       # 翻译结果
    TaskStatus,              # 队列任务状态枚举
    QueueTask,               # 队列任务
    get_mobile_url,          # 兼容读取 mobile_url/mobileUrl
    normalize_news_item,     # 标准化新闻条目字段名
)
```

**使用示例：**

```python
from trendradar.models import NewsAnalysisResult, get_mobile_url

# 创建分析结果
result = NewsAnalysisResult(
    news_id="123",
    summary="这是一条关于市场的新闻摘要",
    keywords=["股市", "涨跌"],
    sentiment="positive",
    importance=4
)

# 兼容读取 URL（同时支持 mobile_url 和 mobileUrl）
url = get_mobile_url(item_dict)
```

**向后兼容别名：**
- `AnalysisResult` → `NewsAnalysisResult`
- `ItemAnalysisResult` → `NewsAnalysisResult`
- `AIAnalysisResult` → `BatchAnalysisResult`

### 3.2 日志模块 (`trendradar/logging.py`)

提供统一的日志配置，替代项目中的 print() 输出。

**接口：**

```python
from trendradar.logging import setup_logging, get_logger

# 在入口处初始化（只需调用一次）
setup_logging(level='INFO')  # 或 'DEBUG'

# 在各模块中获取 logger
logger = get_logger(__name__)

# 使用
logger.info("处理完成: %d 条", count)
logger.warning("配置缺失: %s", key)
logger.error("请求失败: %s", error)
logger.debug("详细信息: %s", data)  # 仅 DEBUG 级别输出
```

**日志格式：**
```
2026-02-02 10:30:45 [INFO] daemon: 启动爬虫守护进程
2026-02-02 10:30:46 [WARNING] daemon: 配置警告: 通知已启用但未配置任何推送渠道
```

**迁移状态：**
- ✅ scripts/run_crawler_daemon.py (63处)
- 待迁移: trendradar/notification/senders.py (93处)
- 待迁移: 其他模块 (~600处)

### 3.3 配置管理器 (`trendradar/core/config_manager.py`)

提供类型安全的配置访问接口，同时保持向后兼容。

**包含的配置 dataclass：**

| 类名 | 说明 |
|------|------|
| `AIConfig` | AI 模型配置（model, api_key, timeout 等） |
| `AIQueueConfig` | AI 队列配置（max_size, workers, retry_count） |
| `AIAnalysisConfig` | AI 分析功能配置 |
| `AITranslationConfig` | AI 翻译功能配置 |
| `NotificationConfig` | 通知配置（所有渠道 webhook、批次大小等） |
| `PushWindowConfig` | 推送窗口配置 |
| `ReportConfig` | 报告配置 |
| `StorageConfig` | 存储配置（本地/远程） |
| `RSSConfig` | RSS 订阅配置 |
| `CrawlerCustomConfig` | 自定义爬虫配置 |
| `DisplayConfig` | 显示配置 |
| `AppConfig` | 应用基础配置 |
| `CrawlerConfig` | 爬虫基础配置 |

**使用示例：**

```python
from trendradar.core import load_config, ConfigManager

config = load_config()
cfg = ConfigManager(config)

# 类型安全访问（IDE 自动补全）
timeout = cfg.ai.timeout                        # int: 120
webhook = cfg.notification.feishu_webhook_url   # str
queue_size = cfg.ai.queue.max_size              # int: 100
timezone = cfg.app.timezone                     # str: "Asia/Shanghai"

# 嵌套配置
if cfg.notification.push_window.enabled:
    start = cfg.notification.push_window.start  # str: "08:00"

# 向后兼容（原始字典访问）
raw_value = cfg.get("SOME_KEY", default_value)
all_config = cfg.raw  # 获取完整配置字典副本
```

**配置验证：**
ConfigManager 初始化时会自动验证配置并输出警告：
```
配置警告: 配置了 AI_API_KEY 但未设置 AI_MODEL
配置警告: 通知已启用但未配置任何推送渠道
```

### 3.4 常量定义 (`trendradar/constants.py`)

集中管理项目常量，消除魔法字符串。

```python
from trendradar.constants import BatchSizes, Timeouts, Limits, Sentiments

# 消息批次大小（字节）
batch = BatchSizes.FEISHU       # 29000
batch = BatchSizes.DINGTALK     # 20000
batch = BatchSizes.TELEGRAM     # 4000

# 超时设置（秒）
timeout = Timeouts.AI_ANALYSIS  # 120
timeout = Timeouts.HTTP_REQUEST # 30

# 限制
max_items = Limits.MAX_NEWS_FOR_ANALYSIS    # 50
max_accounts = Limits.MAX_ACCOUNTS_PER_CHANNEL  # 3

# 情感分析
sentiment = Sentiments.POSITIVE  # "positive"
```

---

## 4. 遗留待办

| 任务 | 优先级 | 说明 |
|------|--------|------|
| senders.py print→logging | 低 | 93 处 print 待迁移 |
| 其他模块 print→logging | 低 | 约 600 处，可按需逐步迁移 |
| Makefile | 低 | 简化 Docker 命令（可选） |

---

## 5. 验证命令

### 5.1 本地语法检查

```bash
python3 -m py_compile scripts/run_crawler_daemon.py trendradar/core/loader.py trendradar/core/config_manager.py
```

### 5.2 测试 ConfigManager

```python
python3 -c "
from trendradar.core import load_config, ConfigManager

config = load_config()
cfg = ConfigManager(config)

print('AI 模型:', cfg.ai.model)
print('AI 超时:', cfg.ai.timeout)
print('队列大小:', cfg.ai.queue.max_size)
print('飞书批次:', cfg.notification.feishu_batch_size)
print('时区:', cfg.app.timezone)
"
```

### 5.3 Docker 构建和运行

```bash
# 构建
cd docker && sg docker -c "docker compose -f docker-compose-build.yml build trendradar"

# 启动
sg docker -c "docker compose -f docker-compose-build.yml up -d trendradar --force-recreate"

# 查看日志
sg docker -c "docker logs --tail 100 trendradar"

# 验证配置
sg docker -c "docker exec trendradar python3 -c \"
from trendradar.core import load_config, ConfigManager
cfg = ConfigManager(load_config())
print('时区:', cfg.app.timezone)
print('邮件启用:', cfg.notification.email_enabled)
\""
```

---

*报告更新时间: 2026-02-02*
