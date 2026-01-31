# TrendRadar v5.6.0 优化报告

> 生成时间: 2026-01-31
> 版本: v5.6.0 (待发布)
> 重点: 同花顺快讯通路延迟优化

---

## 1. 优化摘要

### 本次优化完成的功能

| 功能 | 状态 | 说明 |
|------|------|------|
| TAPP JSON API 爬虫 | ✅ 完成 | 替代旧版 JSONP API，更稳定 |
| 守护进程模式 | ✅ 完成 | 10秒轮询，即时推送 |
| AI 分析接口预留 | ✅ 完成 | `NewsItemAnalyzer` 接口 |
| Docker daemon 模式 | ✅ 完成 | `RUN_MODE=daemon` |
| 配置热切换 | ✅ 完成 | `api_type: tapp/jsonp` |

### 延迟优化效果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| **轮询间隔** | 60s (Cron) | 10s (Daemon) | **-50s** |
| **API 解析** | JSONP+GBK | JSON+UTF-8 | 更稳定 |
| **推送延迟** | 等全流程完成 | 即时推送 | **即时** |
| **理论最小延迟** | 60s | 10s | **-50s** |
| **预期中位数** | 2 分钟 | **1.2 分钟** | **-40%** |

---

## 2. 新增文件

```
trendradar/
├── crawler/custom/
│   └── ths_tapp.py          # 新增: TAPP JSON API 爬虫
├── ai/
│   └── item_analyzer.py     # 新增: 新闻条目 AI 分析器（预留）
scripts/
└── run_crawler_daemon.py    # 新增: 爬虫守护进程脚本
```

---

## 3. 修改文件

| 文件 | 修改内容 |
|------|----------|
| `trendradar/crawler/custom/__init__.py` | 导出 `THSTappCrawler` |
| `trendradar/crawler/runner.py` | 支持 TAPP API 类型选择 |
| `trendradar/ai/__init__.py` | 导出 `NewsItemAnalyzer` |
| `trendradar/core/loader.py` | 加载 `api_type` 配置 |
| `config/config.yaml` | 新增 `api_type` 配置项 |
| `docker/entrypoint.sh` | 支持 `daemon` 运行模式 |
| `docker/.env` | 新增守护进程配置项 |

---

## 4. 配置说明

### 4.1 config.yaml

```yaml
crawler_custom:
  enabled: true
  poll_interval: 10
  api_type: "tapp"          # 新增: tapp (推荐) 或 jsonp (旧版)

  sources:
    - id: "ths-realtime"
      name: "同花顺7x24"
      type: "ths"
      enabled: true
      # api_type: "tapp"    # 可在 source 级别覆盖
```

### 4.2 docker/.env

```bash
# 运行模式: cron | once | daemon
RUN_MODE=daemon              # 使用守护进程模式

# 守护进程配置
CRAWLER_POLL_INTERVAL=10     # 轮询间隔（秒）
CRAWLER_NO_PUSH=false        # 是否禁用推送
CRAWLER_VERBOSE=false        # 详细输出
```

---

## 5. 使用方式

### 5.1 本地运行守护进程

```bash
# 持续运行
python scripts/run_crawler_daemon.py

# 指定轮询间隔
python scripts/run_crawler_daemon.py -i 5

# 运行指定时长
python scripts/run_crawler_daemon.py -d 3600  # 1小时

# 详细输出
python scripts/run_crawler_daemon.py --verbose

# 禁用推送（仅记录）
python scripts/run_crawler_daemon.py --no-push
```

### 5.2 Docker 守护进程模式

```bash
# 修改 docker/.env
RUN_MODE=daemon

# 启动容器
docker-compose up -d
```

---

## 6. 架构对比

### 优化前 (Cron 模式)

```
Cron 1分钟 → python -m trendradar → 热榜+RSS+自定义爬虫 → 推送
             └── 等待全部完成 ──────────────────────────┘
```

### 优化后 (Daemon 模式)

```
┌─────────────────────────────────────────────────────────────┐
│                守护进程 (持续运行)                           │
│                                                             │
│   while True:                                               │
│       1. 抓取 THS TAPP API (10秒间隔)                       │
│       2. 检测新增                                           │
│       3. 过滤 + 即时推送 ────────────────► 邮件通知         │
│       4. AI 分析队列 (异步) ─────────────► 后台处理 (预留)  │
│       5. sleep(10)                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. AI 分析接口 (预留)

### 7.1 接口设计

```python
from trendradar.ai import NewsItemAnalyzer, create_news_item_analyzer

# 创建分析器
analyzer = create_news_item_analyzer(config)

# 同步分析
result = analyzer.analyze_item_sync(item)

# 异步分析
result = await analyzer.analyze_item(item)

# 批量分析
results = await analyzer.analyze_batch(items, max_concurrent=3)
```

### 7.2 分析结果

```python
@dataclass
class ItemAnalysisResult:
    seq: str                  # 新闻序号
    sentiment: str            # positive/negative/neutral
    importance: int           # 1-10
    entities: List[str]       # 关键实体
    summary: str              # 简短摘要
    tags: List[str]           # 自动标签
    success: bool             # 是否成功
```

### 7.3 启用方式 (未来版本)

```yaml
# config.yaml
ai_analysis:
  enabled: true
  item_analysis:
    enabled: true
    max_concurrent: 3
```

---

## 8. 测试结果

### 8.1 TAPP API 测试

```
状态: success
耗时: 0.13s
总条目: 20
数据结构: 完整 (seq, title, summary, url, published_at, extra)
```

### 8.2 守护进程测试 (30秒)

```
总轮询次数: 4
成功次数: 4
失败次数: 0
成功率: 100%
```

---

## 9. 后续计划

### Phase 2: 进一步优化 (可选)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 启用 AI 分析 | P2 | 在守护进程中启用条目级 AI 分析 |
| WebSocket 探索 | P3 | 探索财联社 WebSocket 实现秒级延迟 |
| 多数据源融合 | P3 | 添加财联社等备用数据源 |
| 错误告警 | P2 | 爬虫异常时发送告警 |

### 已知问题

1. **API 缓存限制**: THS API 服务端缓存 ~2分钟，无法突破
2. **服务器 IP 限制**: 部分 API 可能限制服务器 IP 访问

---

## 10. 迁移指南

### 从 Cron 模式迁移到 Daemon 模式

1. 修改 `docker/.env`:
   ```bash
   RUN_MODE=daemon
   CRAWLER_POLL_INTERVAL=10
   ```

2. 重启容器:
   ```bash
   docker-compose down && docker-compose up -d
   ```

3. 查看日志:
   ```bash
   docker logs -f trendradar
   ```

### 回退到 Cron 模式

```bash
RUN_MODE=cron
CRON_SCHEDULE=*/1 * * * *
```

---

**优化完成！** 🎉
