# TrendRadar 自定义爬虫集成 - 开发进度

> Version: 1.3.0
> Date: 2026-01-31
> Status: **Phase 1.5 Complete** (延迟优化)

## 1. 需求清单

| # | 需求 | 优先级 | 状态 | 说明 |
|---|------|--------|------|------|
| 1 | 可扩展爬虫架构 | P0 | **已完成** | BaseCrawler 抽象类 + 注册机制 |
| 2 | 10秒轮询频率 | P0 | **已完成** | 可配置，默认10秒 |
| 3 | 异步完整内容获取 | P0 | **已完成** | 列表获取后立即推送，内容后台获取 |
| 4 | 三层过滤 (标题+摘要+内容) | P0 | **已完成** | 支持正则，filter_tag 标记 |
| 5 | 集成到主流程 | P0 | **已完成** | `_crawl_custom_data()` |
| 6 | 修复增量检测bug | P0 | **已完成** | 独立增量检测，不依赖热榜 |
| 7 | 禁用 GitHub 版本检查 | P0 | **已完成** | 配置 `check_update: false` |
| 8 | 网页显示改造 | P0 | **已完成** | 自定义爬虫区/同花顺快讯/过滤标签 |
| 9 | 邮箱推送 | P0 | **已完成** | 复用现有通知模块 |
| 10 | 飞书/机器人推送 | P1 | **待测试** | 框架已支持，需配置测试 |
| 11 | 过滤前/后数据库分离 | P1 | **已完成** | `crawler.db` 独立存储 |
| 12 | AI 分析接口预留 | P2 | **已完成** | `NewsItemAnalyzer` 接口 |
| 13 | **TAPP JSON API** | P0 | **已完成** | 替代 JSONP，更稳定 |
| 14 | **守护进程模式** | P0 | **已完成** | 10秒轮询，即时推送 |
| 15 | MCP 集成 | P2 | 待实现 | 支持 AI 助手查询 |

---

## 2. Phase 1.5: 延迟优化 (2026-01-31)

### 2.1 优化效果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| **轮询间隔** | 60s (Cron) | 10s (Daemon) | **-50s** |
| **API 格式** | JSONP+GBK | JSON+UTF-8 | 更稳定 |
| **推送延迟** | 等全流程 | 即时推送 | **即时** |
| **预期中位数** | 2 分钟 | **1.2 分钟** | **-40%** |

### 2.2 新增文件

```
trendradar/
├── crawler/custom/
│   └── ths_tapp.py          # TAPP JSON API 爬虫
├── ai/
│   └── item_analyzer.py     # 新闻条目 AI 分析器（预留）
scripts/
└── run_crawler_daemon.py    # 爬虫守护进程脚本
```

### 2.3 配置更新

```yaml
# config/config.yaml
crawler_custom:
  api_type: "tapp"    # 新增: tapp (推荐) 或 jsonp (旧版)
```

```bash
# docker/.env
RUN_MODE=daemon              # 新增: daemon 模式
CRAWLER_POLL_INTERVAL=10     # 轮询间隔
```

---

## 3. 已完成功能

### 2.1 核心爬虫模块

```
trendradar/crawler/custom/
├── __init__.py       # 模块入口
├── base.py           # BaseCrawler 抽象类
├── ths.py            # 同花顺7x24爬虫
├── manager.py        # 爬虫管理器
├── filter.py         # 三层过滤模块
└── storage.py        # 独立存储管理
```

### 2.2 主流程集成

- **入口**: `trendradar/__main__.py:_crawl_custom_data()`
- **模式支持**: daily / incremental / current
- **数据流**: CrawlerRunner → count_rss_frequency → HTML 报告

### 2.3 显示优化

| 组件 | 原名称 | 新名称 |
|------|--------|--------|
| 区域标题 | RSS 订阅更新 | **自定义爬虫** |
| 分组名称 | 全部 RSS | **同花顺快讯** |
| 过滤标签 | (无) | `✓ 关键词` / `🚫 无匹配` |

---

## 3. 配置说明

### 3.1 启用自定义爬虫 (`config/config.yaml`)

```yaml
# ===============================================================
# 自定义爬虫配置
# ===============================================================
crawler_custom:
  enabled: true
  poll_interval: 10

  sources:
    - id: "ths-realtime"
      name: "同花顺7x24"
      type: "ths"
      enabled: true

  full_content:
    enabled: true
    async_mode: true
    timeout: 10

  filter:
    use_frequency_words: true
    levels: ["title", "summary", "content"]
```

### 3.2 关键词配置 (`config/frequency_words.txt`)

```
[WORD_GROUPS]
[地缘政治/能源]
石油
伊朗
美国

[科技/AI]
人工智能
芯片
半导体
```

### 3.3 Docker 环境变量 (`docker/.env`)

```bash
CRON_SCHEDULE=*/2 * * * *    # 执行频率
CHECK_UPDATE=false           # 禁用版本检查
```

---

## 4. 测试验证

### 4.1 Docker 测试结果 (2026-01-31)

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 容器启动 | **通过** | trendradar + trendradar-mcp |
| 数据获取 | **通过** | 100 条新闻 |
| 三层过滤 | **通过** | 21 通过, 79 过滤 |
| 增量检测 | **通过** | 4 条新增 |
| HTML 报告 | **通过** | 显示名称正确 |
| 邮件推送 | **通过** | 发送成功 |

### 4.2 验证命令

```bash
# 本地测试
python3 scripts/test_crawler.py

# Docker 测试
sg docker -c "docker compose up -d"
sg docker -c "docker logs trendradar --tail 50"
sg docker -c "curl -s http://localhost:8080"
```

---

## 5. 相关提交

| 提交 | 说明 |
|------|------|
| `2ff6d68` | feat: 实现自定义爬虫框架（同花顺7x24新闻） |
| `e2ff2b7` | feat: 集成自定义爬虫到主流程 |
| `98c4a71` | fix: 修复过滤标签显示并优化显示名称 |

---

## 6. 后续计划

### Phase 2: 扩展功能
- [ ] 添加更多数据源（财联社、新浪财经）
- [ ] 飞书/企业微信推送测试
- [ ] MCP 集成（AI 助手查询）

### Phase 3: 优化
- [ ] 错误告警机制
- [ ] 历史数据分析
- [ ] 性能监控

---

## 7. 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 架构设计 | `docs/CRAWLER_DESIGN.md` | 爬虫模块设计文档 |
| 问题解决 | `docs/TROUBLESHOOTING.md` | 问题解决方案清单 |
| 部署指南 | `DEPLOYMENT_NOTES.md` | 部署配置说明 |
| 开发进度 | `docs/DEVELOPMENT_STATUS.md` | 本文档 |
