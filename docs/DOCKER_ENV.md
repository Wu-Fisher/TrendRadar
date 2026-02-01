# Docker 环境变量配置说明

本文档说明 `docker/.env` 文件中各项环境变量的用途和配置方法。

---

## 目录

1. [运行模式配置](#运行模式配置)
2. [爬虫守护进程配置](#爬虫守护进程配置)
3. [AI 配置](#ai-配置)
4. [邮件配置](#邮件配置)
5. [即时通讯配置](#即时通讯配置)
6. [其他配置](#其他配置)

---

## 运行模式配置

```bash
# 运行模式：cron | once | daemon
# - cron: 定时任务模式（默认），按 CRON_SCHEDULE 执行
# - once: 单次执行后退出
# - daemon: 爬虫守护进程模式（推荐），10秒轮询，即时推送
RUN_MODE=daemon

# 定时任务表达式（仅 RUN_MODE=cron 时生效）
# 示例：*/30 * * * * = 每30分钟执行一次
CRON_SCHEDULE=*/1 * * * *

# 启动时立即执行一次（适用于 cron 和 daemon 模式）
IMMEDIATE_RUN=true
```

### 模式对比

| 模式 | 执行频率 | 推送方式 | 适用场景 |
|------|----------|----------|----------|
| `daemon` | 10秒轮询 | 即时推送 + AI增强 | 实时监控 |
| `cron` | 按计划执行 | 定时汇总 | 定期报告 |
| `once` | 执行一次 | 单次推送 | 调试/测试 |

---

## 爬虫守护进程配置

以下配置仅在 `RUN_MODE=daemon` 时生效：

```bash
# 轮询间隔（秒），默认 10
# 建议范围：5-60，太频繁可能被反爬
CRAWLER_POLL_INTERVAL=10

# 禁用推送通知（仅记录不推送）
# true: 只记录日志，不发送任何推送
# false: 正常推送（默认）
CRAWLER_NO_PUSH=false

# 详细输出（调试用）
# true: 显示每次轮询的详细信息
CRAWLER_VERBOSE=true

# 启用 AI 分析（Phase 2 增强推送）
# true: 新闻会进入 AI 分析队列，分析完成后再次推送
CRAWLER_ENABLE_AI=true

# 使用 CrewAI 分析器（默认使用 SimpleAnalyzer）
# true: 使用 CrewAI（更强大，需要更多资源）
# false: 使用 SimpleAnalyzer（轻量级）
CRAWLER_USE_CREWAI=true
```

### AI 分析器对比

| 分析器 | 特点 | 资源消耗 | 输出质量 |
|--------|------|----------|----------|
| SimpleAnalyzer | 单次 API 调用 | 低 | 基础分析 |
| CrewAI | 多 Agent 协作 | 高 | 深度分析 |

---

## AI 配置

```bash
# 是否启用 AI 分析（用于定时报告的 AI 分析区块）
# 注意：这与 CRAWLER_ENABLE_AI 是不同的配置
# - AI_ANALYSIS_ENABLED: 控制定时报告中的 AI 分析区块
# - CRAWLER_ENABLE_AI: 控制 daemon 模式的 AI 增强推送
AI_ANALYSIS_ENABLED=false

# AI API Key（必填，启用任何 AI 功能时需要）
# 支持 OpenAI、SiliconFlow、DeepSeek 等兼容 API
AI_API_KEY=sk-xxx

# 模型名称（LiteLLM 格式: provider/model_name）
# 常用模型：
#   - openai/gpt-4o
#   - openai/Pro/deepseek-ai/DeepSeek-V3.2 (SiliconFlow)
#   - deepseek/deepseek-chat
#   - gemini/gemini-2.5-flash
AI_MODEL=openai/Pro/deepseek-ai/DeepSeek-V3.2

# 自定义 API 端点（可选）
# 使用 SiliconFlow、国内代理等需要配置
AI_API_BASE=https://api.siliconflow.cn/v1
```

### 模型配置示例

```bash
# SiliconFlow + DeepSeek V3
AI_API_KEY=sk-bahnlunpwmtxslljfhtcygbvbvtpuytxxzyyqubmhtxlfujn
AI_MODEL=openai/Pro/deepseek-ai/DeepSeek-V3.2
AI_API_BASE=https://api.siliconflow.cn/v1

# OpenAI 官方
AI_API_KEY=sk-xxx
AI_MODEL=openai/gpt-4o
AI_API_BASE=  # 留空使用官方端点

# DeepSeek 官方
AI_API_KEY=sk-xxx
AI_MODEL=deepseek/deepseek-chat
AI_API_BASE=https://api.deepseek.com
```

---

## 邮件配置

```bash
# 发件人邮箱
EMAIL_FROM=your_email@163.com

# 邮箱授权码（不是登录密码！）
# 163邮箱：设置 → POP3/SMTP → 开启后获取授权码
# QQ邮箱：设置 → 账户 → POP3/SMTP → 生成授权码
EMAIL_PASSWORD=your_auth_code

# 收件人邮箱（支持多个，逗号分隔）
EMAIL_TO=recipient1@example.com,recipient2@example.com

# SMTP 服务器（可选，会自动识别常见邮箱）
EMAIL_SMTP_SERVER=smtp.163.com
EMAIL_SMTP_PORT=25
```

### 常见邮箱 SMTP 配置

| 邮箱 | SMTP 服务器 | 端口 |
|------|-------------|------|
| 163 | smtp.163.com | 25 / 465 |
| QQ | smtp.qq.com | 465 |
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 即时通讯配置

### 飞书

```bash
# 飞书机器人 Webhook URL（简单推送方式）
# 创建：群设置 → 群机器人 → 添加自定义机器人
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 飞书群聊 ID（用于 Feishu Push Service）
# 通过 LangBot 或飞书 API 获取
FEISHU_CHAT_IDS=oc_d29285f2dd1702ea24430464a43acc8c

# 飞书用户 open_id（可选，用于私聊推送）
FEISHU_OPEN_IDS=
```

### 钉钉

```bash
# 钉钉机器人 Webhook URL
# 创建：群设置 → 智能群助手 → 添加自定义机器人
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 企业微信

```bash
# 企业微信机器人 Webhook URL
WEWORK_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# 消息类型：markdown 或 text
WEWORK_MSG_TYPE=markdown
```

### Telegram

```bash
# Bot Token（通过 @BotFather 创建机器人获取）
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Chat ID（私聊或群组 ID）
# 获取方法：向机器人发消息后访问
# https://api.telegram.org/bot{TOKEN}/getUpdates
TELEGRAM_CHAT_ID=-1001234567890
```

---

## 其他配置

### Web 服务器

```bash
# 是否启用 Web 服务器托管 output 目录
ENABLE_WEBSERVER=true

# Web 服务器端口
WEBSERVER_PORT=8080
```

### 远程存储（S3 兼容）

```bash
# 用于备份输出文件到云存储
S3_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com
S3_BUCKET_NAME=trendradar-backup
S3_ACCESS_KEY_ID=xxx
S3_SECRET_ACCESS_KEY=xxx
S3_REGION=auto
```

---

## 完整配置示例

```bash
# ============================================
# TrendRadar Docker 环境变量示例
# ============================================

# --- 运行模式 ---
RUN_MODE=daemon
IMMEDIATE_RUN=true

# --- 守护进程配置 ---
CRAWLER_POLL_INTERVAL=10
CRAWLER_NO_PUSH=false
CRAWLER_VERBOSE=true
CRAWLER_ENABLE_AI=true
CRAWLER_USE_CREWAI=true

# --- AI 配置 ---
AI_ANALYSIS_ENABLED=false
AI_API_KEY=sk-xxx
AI_MODEL=openai/Pro/deepseek-ai/DeepSeek-V3.2
AI_API_BASE=https://api.siliconflow.cn/v1

# --- 邮件配置 ---
EMAIL_FROM=your_email@163.com
EMAIL_PASSWORD=your_auth_code
EMAIL_TO=recipient@example.com
EMAIL_SMTP_SERVER=smtp.163.com
EMAIL_SMTP_PORT=25

# --- 飞书配置 ---
FEISHU_CHAT_IDS=oc_xxx

# --- Web 服务器 ---
ENABLE_WEBSERVER=true
WEBSERVER_PORT=8080
```

---

## 配置生效

修改 `.env` 文件后，需要重启容器才能生效：

```bash
cd docker
docker compose restart trendradar
docker compose -f docker-compose-langbot.yml restart
```

---

最后更新: 2026-02-02
