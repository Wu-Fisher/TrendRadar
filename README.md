# StockTrendRadar

> 智能财经新闻雷达 —— 实时抓取、AI 分析、即时推送

基于 [TrendRadar](https://github.com/sansan0/TrendRadar) 深度定制的股票财经新闻监控系统，专注于：
- **超低延迟**：10 秒轮询，快人一步获取市场资讯
- **AI 智能分析**：CrewAI 多 Agent 架构，深度解读新闻影响
- **精准过滤**：关键词 + 正则表达式，只看你关心的内容

## 项目架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        StockTrendRadar                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据采集层 (Crawlers)                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ RSS Fetcher │  │  NewsNow    │  │  同花顺 TAPP API    │  │   │
│  │  │ (Atom/RSS)  │  │  (热榜聚合)  │  │  (7x24 快讯) ⭐     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    数据处理层 (Processing)                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ 去重过滤    │──│ 关键词匹配  │──│ 重要性评分          │  │   │
│  │  │ (历史对比)  │  │ (正则支持)  │  │ (热度权重)          │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AI 分析层 (Analyzers)                      │   │
│  │  ┌─────────────────────┐  ┌─────────────────────────────┐   │   │
│  │  │   SimpleAnalyzer    │  │      CrewAI Analyzer ⭐     │   │   │
│  │  │   (直接 LLM 调用)   │  │  ┌───────────────────────┐  │   │   │
│  │  │   - 快速分析        │  │  │ Single Agent Mode     │  │   │   │
│  │  │   - 摘要/关键词     │  │  │ - 财经新闻分析师      │  │   │   │
│  │  └─────────────────────┘  │  └───────────────────────┘  │   │   │
│  │                           │  ┌───────────────────────┐  │   │   │
│  │                           │  │ Multi-Agent Mode      │  │   │   │
│  │                           │  │ - 市场影响分析师      │  │   │   │
│  │                           │  │ - 风险评估师          │  │   │   │
│  │                           │  └───────────────────────┘  │   │   │
│  │                           └─────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    推送层 (Notification)                      │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ Phase 1: 即时推送                                    │    │   │
│  │  │ 新消息 ──▶ 关键词匹配 ──▶ 立即发送                  │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ Phase 2: AI 增强推送                                 │    │   │
│  │  │ 新消息 ──▶ AI 队列 ──▶ 分析完成 ──▶ 深度报告        │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │                                                             │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │ 统一网关: LangBot (所有消息经由 LangBot 发送)       │    │   │
│  │  │ daemon ──▶ .push_queue/ ──▶ PushQueue 插件 ──▶ 飞书 │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据流管线

| 管线 | 数据源 | 状态 | 说明 |
|------|--------|------|------|
| **TAPP API 管线** ⭐ | 同花顺 7x24 快讯 | **当前激活** | 10 秒轮询，超低延迟，专业财经数据 |
| NewsNow 管线 | 多平台热榜聚合 | 可用 | 知乎/微博/头条等 11+ 平台 |
| RSS 管线 | 自定义 RSS 源 | 可用 | 支持 Atom/RSS 格式 |

### AI 分析器

| 分析器 | 框架 | 状态 | 特点 |
|--------|------|------|------|
| **CrewAnalyzer** ⭐ | CrewAI | **当前激活** | Agent 架构，可扩展 |
| SimpleAnalyzer | LiteLLM | 备用 | 直接 API 调用，轻量 |
| MultiAgentCrewAnalyzer | CrewAI | 可用 | 多 Agent 深度分析 |

## 快速开始

### 环境要求

- Python 3.10+
- Docker (推荐)

### Docker 部署 (推荐)

1. **克隆项目**
   ```bash
   git clone https://github.com/your-repo/StockTrendRadar.git
   cd StockTrendRadar
   ```

2. **配置环境变量**
   ```bash
   cd docker
   cp .env.example .env
   # 编辑 .env 文件，配置 AI API Key 和推送渠道
   ```

3. **一键部署** (使用部署脚本)
   ```bash
   cd docker
   ./deploy.sh full    # 构建镜像 + 启动所有服务
   ```

   > 部署脚本会自动启动以下服务：
   > - `trendradar` - 爬虫守护进程 + AI 分析
   > - `langbot` - 飞书机器人主服务
   > - `langbot_plugin_runtime` - 插件系统 (含 PushQueue 推送、`!tr` 命令)
   >
   > **推送架构**: TrendRadar daemon → `.push_queue/` → PushQueue 插件 → LangBot → 飞书

4. **常用命令**
   ```bash
   ./deploy.sh status   # 查看服务状态
   ./deploy.sh logs     # 查看所有日志
   ./deploy.sh restart  # 重启所有服务
   ./deploy.sh stop     # 停止所有服务
   ./deploy.sh help     # 显示帮助
   ```

5. **飞书交互命令**
   ```
   !tr           # 显示帮助
   !tr status    # 查看推送状态
   !tr keywords  # 查看关键词配置
   !tr prompt    # 查看 AI 提示词
   ```

### 关键配置

#### 运行模式 (.env)

```bash
# 运行模式：cron/once/daemon
RUN_MODE=daemon           # 守护进程模式（推荐）

# 守护进程配置
CRAWLER_POLL_INTERVAL=10  # 轮询间隔（秒）
CRAWLER_ENABLE_AI=true    # 启用 AI 分析
CRAWLER_USE_CREWAI=true   # 使用 CrewAI 分析器
CRAWLER_VERBOSE=true      # 详细日志
```

#### AI 配置 (.env)

```bash
# AI API 配置
AI_API_KEY=sk-your-api-key
AI_MODEL=openai/Pro/deepseek-ai/DeepSeek-V3.2
AI_API_BASE=https://api.siliconflow.cn/v1
```

#### 推送配置 (.env)

```bash
# 邮件推送
EMAIL_FROM=your@email.com
EMAIL_PASSWORD=your-password
EMAIL_TO=recipient@email.com

# 或其他渠道
FEISHU_WEBHOOK_URL=https://...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## 可配置项

### 1. 关键词配置

**文件**: `config/frequency_words.txt`

```txt
# 关键词组 1：AI 相关
AI
人工智能
ChatGPT
+发布      # 必须词：必须同时包含
!广告      # 过滤词：排除包含此词的

# 关键词组 2：新能源车
特斯拉
比亚迪
/\b新能源\b/ => 新能源汽车    # 正则匹配 + 显示名称
@10        # 最多显示 10 条

[GLOBAL_FILTER]
# 全局过滤（所有组生效）
震惊
标题党
```

### 2. 分析 Prompt 配置

**文件**: `trendradar/ai/prompts/analyze.txt`

可自定义 AI 分析的角色、输出格式、分析维度等。

### 3. 平台配置

**文件**: `config/config.yaml`

```yaml
platforms:
  enabled: true
  sources:
    - id: "ths-realtime"
      name: "同花顺7x24"
      api: "tapp"          # 使用 TAPP API
```

### 4. 高级配置

| 配置项 | 位置 | 说明 |
|--------|------|------|
| 热度权重算法 | config.yaml | rank/frequency/hotness 权重 |
| 推送时间窗口 | config.yaml | 指定推送时间段 |
| AI 队列参数 | config.yaml | 工作线程数、重试次数 |
| 存储后端 | config.yaml | 本地 SQLite / S3 云存储 |

## 项目结构

```
StockTrendRadar/
├── trendradar/                 # 核心库
│   ├── ai/                     # AI 分析模块
│   │   ├── analyzers/          # 分析器实现
│   │   │   ├── simple.py       # SimpleAnalyzer
│   │   │   └── crew_analyzer.py # CrewAI 分析器
│   │   ├── queue/              # AI 任务队列
│   │   └── prompts/            # Prompt 模板
│   ├── crawler/                # 爬虫模块
│   │   ├── custom/             # 自定义爬虫
│   │   │   ├── ths.py          # 同花顺爬虫
│   │   │   ├── ths_tapp.py     # TAPP API 爬虫
│   │   │   └── filter.py       # 关键词过滤
│   │   └── rss/                # RSS 爬虫
│   ├── notification/           # 推送模块
│   │   └── senders.py          # 各渠道发送器
│   └── storage/                # 存储模块
├── scripts/
│   └── run_crawler_daemon.py   # 守护进程入口
├── docker/
│   ├── Dockerfile
│   ├── docker-compose-langbot.yml  # LangBot 服务编排
│   ├── deploy.sh               # 部署脚本
│   ├── langbot_data/           # LangBot 数据目录
│   │   └── plugins/            # LangBot 插件
│   │       ├── trendradar/     # TrendRadar 交互插件 (!tr 命令)
│   │       └── TrendRadar__push_queue/  # 推送队列处理插件
│   └── .env                    # 环境配置
└── config/
    ├── config.yaml             # 主配置
    ├── frequency_words.txt     # 关键词配置
    └── .push_queue/            # 推送队列目录
```

## 开发路线图

详见 [docs/ROADMAP.md](docs/ROADMAP.md)

### 近期计划

- [ ] 历史数据分析与趋势预测
- [ ] 接入 pywencai 专业数据源
- [ ] Web 管理界面

### 中期计划

- [ ] 多数据源交叉验证
- [ ] 自动化交易信号生成
- [ ] 知识图谱构建

## 参考文档

### 核心文档 (按需检索)

| 文档 | 说明 | 适用场景 |
|------|------|----------|
| **[系统总览](docs/SYSTEM_OVERVIEW.md)** | 架构、流程、数据流向 | 🔰 首次了解系统 |
| **[架构原则](docs/ARCHITECTURE_PRINCIPLES.md)** | 核心设计原则与决策 | 了解系统架构理念 |
| **[Docker 配置](docs/DOCKER_ENV.md)** | 环境变量详解 | 修改运行模式、AI配置 |
| **[关键词过滤](docs/KEYWORD_FILTER.md)** | 过滤规则语法 | 添加/修改监控关键词 |
| **[AI 提示词](docs/AI_PROMPT_GUIDE.md)** | AI 分析原理详解 | 理解/自定义 AI 分析风格 |
| **[飞书配置](docs/LANGBOT_FEISHU_SETUP.md)** | LangBot + 飞书设置 | 配置飞书机器人 |
| **[飞书推送](docs/LANGBOT_PUSH_GUIDE.md)** | 飞书 API 推送指南 | 启用飞书实时推送 |
| **[故障排查](docs/TROUBLESHOOTING.md)** | 常见问题解决 | 遇到问题时查阅 |
| **[架构设计](docs/ARCHITECTURE.md)** | 技术架构细节 | 深入了解代码结构 |

### 配置文件快速索引

| 文件 | 用途 | 常见操作 |
|------|------|----------|
| `docker/.env` | 运行配置 | 修改模式、API Key、推送渠道 |
| `config/config.yaml` | 主配置 | 数据源、显示区域、推送时间窗口 |
| `config/frequency_words.txt` | 关键词过滤 | 添加监控关键词 |
| `config/ai_analysis_prompt.txt` | AI 提示词 | 自定义分析风格 |

### 常用命令

```bash
cd docker

# 使用部署脚本 (推荐)
./deploy.sh status              # 查看服务状态
./deploy.sh logs                # 查看所有日志
./deploy.sh logs trendradar     # 查看爬虫日志
./deploy.sh logs plugin         # 查看插件日志
./deploy.sh restart             # 重启所有服务
./deploy.sh stop                # 停止所有服务
./deploy.sh full                # 重新构建并启动

# 手动执行一次 (调试)
docker exec trendradar python scripts/run_crawler_daemon.py --once --verbose
```

---

- [原版 TrendRadar 文档](README-TrendRadar-Archive.md) - 历史参考

## 许可证

GPL-3.0 License
