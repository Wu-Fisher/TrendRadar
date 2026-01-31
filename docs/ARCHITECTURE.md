# TrendRadar 架构说明

> 版本: v5.6.0
> 更新: 2026-01-31

## 1. 运行模式对比

### 1.1 两种运行模式

| 方面 | Cron 模式 | Daemon 模式 |
|------|-----------|-------------|
| 入口 | `python -m trendradar` | `scripts/run_crawler_daemon.py` |
| 触发 | Cron 定时 (1-60分钟) | 持续轮询 (10秒) |
| 数据源 | 热榜 + RSS + 自定义爬虫 | 仅自定义爬虫 |
| 延迟 | 1-2分钟 | ~15秒 |
| 报告 | 完整 HTML 报告 | 简化即时通知 |
| 适用 | 定时汇总、完整分析 | 快讯即时推送 |

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        TrendRadar 架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐         ┌─────────────────────────────┐   │
│  │   Cron 模式     │         │      Daemon 模式            │   │
│  │ (完整流程)      │         │   (快讯专用)                │   │
│  └────────┬────────┘         └─────────────┬───────────────┘   │
│           │                                │                    │
│           ▼                                ▼                    │
│  ┌─────────────────┐         ┌─────────────────────────────┐   │
│  │ NewsAnalyzer    │         │   CrawlerDaemon             │   │
│  │ (__main__.py)   │         │   (run_crawler_daemon.py)   │   │
│  └────────┬────────┘         └─────────────┬───────────────┘   │
│           │                                │                    │
│           ▼                                ▼                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   共享组件层                             │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │CrawlerRunner│  │ loader.py   │  │ senders.py      │  │   │
│  │  │(爬虫执行器) │  │ (配置加载)  │  │ (推送发送器)    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 推送机制

### 2.1 原有推送流程 (Cron 模式)

```python
# __main__.py
dispatcher = self.ctx.create_notification_dispatcher()
results = dispatcher.dispatch_all(
    report_data=report_data,
    html_file_path=html_file,  # 需要完整 HTML 文件
    rss_items=rss_items,
    ai_analysis=ai_result,
    ...
)
```

特点：
- ✅ 支持全部推送渠道
- ✅ 完整格式化（使用 splitter.py）
- ✅ HTML 报告附件
- ❌ 需要完整报告生成流程

### 2.2 Daemon 推送流程

```python
# run_crawler_daemon.py
def _send_notification(self, new_items):
    # 直接调用底层发送器
    self._send_email_direct(subject, html_content)
    send_to_feishu(subject, text_content, self.config)
    send_to_dingtalk(subject, text_content, self.config)
    ...
```

特点：
- ✅ 即时推送（无需生成报告）
- ✅ 支持多渠道（邮件/飞书/钉钉/企业微信/Telegram）
- ✅ 简化内容格式
- ❌ 不支持 HTML 附件

### 2.3 复用程度分析

| 组件 | Cron 模式 | Daemon 模式 | 复用情况 |
|------|-----------|-------------|----------|
| 配置加载 | loader.py | loader.py | ✅ 完全复用 |
| 爬虫执行 | CrawlerRunner | CrawlerRunner | ✅ 完全复用 |
| 增量检测 | CrawlerRunner | CrawlerRunner | ✅ 完全复用 |
| 关键词过滤 | filter.py | filter.py | ✅ 完全复用 |
| 推送发送 | senders.py | senders.py | ✅ 底层复用 |
| 内容格式化 | splitter.py | 简化实现 | ⚠️ 部分重写 |
| 报告生成 | 完整流程 | 无 | ❌ 不需要 |

## 3. 对原有功能的影响

### 3.1 不受影响的功能

| 功能 | 说明 |
|------|------|
| 热榜抓取 | Cron 模式独有，Daemon 不干扰 |
| RSS 抓取 | Cron 模式独有，Daemon 不干扰 |
| 完整报告 | 仅 Cron 模式生成 |
| AI 分析 | 仅 Cron 模式使用 |
| 推送窗口 | 仅 Cron 模式检查 |

### 3.2 共享但独立的功能

| 功能 | 说明 |
|------|------|
| 配置 | 同一份 config.yaml，互不干扰 |
| 数据库 | 共享 crawler.db，增量检测互相独立 |
| 推送渠道 | 配置共享，发送逻辑独立 |

## 4. 可扩展性评估

### 4.1 添加新数据源

两种模式都支持，只需：
1. 创建新的 Crawler 类（继承 BaseCrawler）
2. 在 runner.py 注册
3. 在 config.yaml 配置

### 4.2 添加新推送渠道

Cron 模式：
- 在 senders.py 添加发送函数
- 在 dispatcher.py 添加调度逻辑

Daemon 模式：
- 在 senders.py 添加发送函数
- 在 _send_notification() 添加调用

### 4.3 添加 AI 分析

Daemon 模式已预留：
```python
# NewsItemAnalyzer 接口
analyzer = create_news_item_analyzer(config)
result = await analyzer.analyze_item(item)
```

## 5. 设计原则

### 5.1 采用的原则

1. **最小侵入**: Daemon 是独立脚本，不修改原有主流程
2. **组件复用**: 尽可能复用 loader/runner/senders
3. **关注点分离**: Daemon 专注快讯场景，Cron 专注完整报告

### 5.2 权衡取舍

| 决策 | 原因 |
|------|------|
| Daemon 不使用 NotificationDispatcher | 避免复杂的 report_data 适配 |
| Daemon 自己实现邮件发送 | 原 send_to_email 需要文件路径 |
| Daemon 使用简化内容格式 | 即时推送不需要完整报告格式 |

## 6. 建议的使用方式

### 6.1 场景推荐

| 场景 | 推荐模式 |
|------|----------|
| 每日热点汇总 | Cron (daily) |
| 新闻增量监控 | Cron (incremental) |
| 快讯即时推送 | Daemon |
| 完整 AI 分析 | Cron |

### 6.2 部署建议

```yaml
# 方案 A: 仅 Daemon（快讯场景）
RUN_MODE=daemon
CRAWLER_POLL_INTERVAL=10

# 方案 B: 仅 Cron（传统场景）
RUN_MODE=cron
CRON_SCHEDULE=*/30 * * * *

# 方案 C: 双模式（未来可支持）
# 需要两个容器实例
```

---

*文档版本: v1.0 | 最后更新: 2026-01-31*
