# LangBot 集成与飞书推送指南

本文档说明 TrendRadar 与 LangBot 的集成，实现飞书实时推送和配置查看功能。

## 系统架构

```
┌─────────────────────┐     ┌─────────────────────┐
│  TrendRadar Daemon  │────▶│   Push Queue        │
│  (爬虫 + AI 分析)    │     │ config/.push_queue/ │
└─────────────────────┘     └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  Feishu Push Service │
                            │  (feishu_push 容器)  │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │    飞书群聊/用户     │
                            │   (Feishu API)      │
                            └─────────────────────┘
```

## 服务组件

| 容器 | 端口 | 功能 |
|------|------|------|
| `trendradar` | 8080 | 爬虫守护进程，抓取新闻 + AI 分析 |
| `langbot` | 5300 | LangBot WebUI + 飞书 WebSocket 连接 |
| `langbot_plugin_runtime` | 5401 | LangBot 插件运行时 |
| `feishu_push` | - | 监听推送队列，发送到飞书 |

## 启动服务

```bash
cd /home/wufisher/ws/dev/TrendRadar/docker

# 启动 TrendRadar (如果未运行)
docker compose up -d trendradar

# 启动 LangBot + 飞书推送
docker compose -f docker-compose-langbot.yml up -d
```

## 推送流程

### Phase 1: 原始新闻推送
当 TrendRadar 发现新新闻时：
1. 通过邮件/飞书webhook/钉钉等渠道推送
2. 同时写入 `config/.push_queue/*.json`
3. Feishu Push Service 读取队列并推送到飞书群聊

### Phase 2: AI 分析推送
当 AI 分析完成时：
1. 邮件推送 AI 分析报告 (主题: `[AI分析] xxx`)
2. 写入推送队列 (type: `ai_analysis`)
3. Feishu Push Service 推送到飞书

## 配置

### 飞书推送目标

编辑 `docker/.env` 或 `docker-compose-langbot.yml`:

```bash
# 群聊 ID (逗号分隔支持多个)
FEISHU_CHAT_IDS=oc_d29285f2dd1702ea24430464a43acc8c

# 用户 open_id (可选)
FEISHU_OPEN_IDS=
```

### 飞书凭证来源

Feishu Push Service 自动从 LangBot 数据库读取飞书凭证:
- 数据库路径: `docker/langbot_data/langbot.db`
- 表: `bots` (adapter = 'lark')

## LangBot 插件 (配置查看)

插件位置: `docker/langbot_data/plugins/trendradar/`

### 支持的命令

在飞书中与机器人对话:

| 命令 | 功能 |
|------|------|
| `!keywords` / `查看关键词` | 显示关键词过滤配置 |
| `!prompt` / `查看分析prompt` | 显示 AI 分析提示词 |
| `!status` / `查看状态` | 显示推送队列状态 |
| `!help` / `帮助` | 显示帮助信息 |

**注意**: LangBot 插件需要 LangBot 的插件系统支持。如果插件无法加载，可直接使用飞书推送功能。

## 测试

### 测试飞书推送

```bash
# 创建测试推送消息
cat > config/.push_queue/test.json << 'EOF'
{
  "id": "test-001",
  "timestamp": "2026-02-02T01:00:00",
  "type": "raw",
  "subject": "测试消息",
  "text_content": "这是测试内容",
  "items": [],
  "status": "pending"
}
EOF

# 查看 feishu_push 日志
docker logs -f feishu_push
```

### 验证邮件 AI 推送

邮件 AI 推送已修复，当有新闻触发 AI 分析时会自动发送:
- 邮件主题: `[AI分析] xxx`
- 包含: 摘要、关键词、情感、重要性评分

## 日志查看

```bash
# TrendRadar 爬虫日志
docker logs -f trendradar

# 飞书推送日志
docker logs -f feishu_push

# LangBot 日志
docker logs -f langbot
```

## 常见问题

### Q: 飞书推送失败
A: 检查:
1. LangBot 是否已配置飞书应用 (WebUI: http://localhost:5300)
2. 飞书应用是否有发送消息权限
3. chat_id 是否正确

### Q: 邮件收不到 AI 分析
A: 确认:
1. `CRAWLER_ENABLE_AI=true` 已设置
2. AI API Key 已配置且有效
3. 查看 trendradar 日志确认 AI 分析是否完成

### Q: 推送队列堆积
A: 检查 feishu_push 容器是否正常运行:
```bash
docker ps -a | grep feishu_push
docker logs feishu_push
```

## 文件结构

```
TrendRadar/
├── config/
│   ├── config.yaml              # 主配置
│   ├── frequency_words.txt      # 关键词过滤
│   ├── ai_analysis_prompt.txt   # AI 分析提示词
│   └── .push_queue/             # 推送队列目录
│       └── .processed/          # 已处理消息
├── docker/
│   ├── docker-compose.yml       # TrendRadar 主服务
│   ├── docker-compose-langbot.yml # LangBot + 飞书推送
│   └── langbot_data/
│       ├── langbot.db           # LangBot 数据库
│       └── plugins/
│           └── trendradar/      # 配置查看插件
└── scripts/
    ├── run_crawler_daemon.py    # 爬虫守护进程
    └── feishu_push_service.py   # 飞书推送服务
```

---

最后更新: 2026-02-02
