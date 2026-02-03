# LangBot 插件系统指南

> TrendRadar 项目与 LangBot 集成的插件配置和使用文档
> 最后更新: 2026-02-02

## 目录

- [插件概览](#插件概览)
- [核心插件详解](#核心插件详解)
- [TrendRadar 自定义插件](#trendradar-自定义插件)
- [插件交互流程](#插件交互流程)
- [配置指南](#配置指南)
- [开发路线](#开发路线)

---

## 插件概览

### 已安装/计划安装的插件

| 插件 | 作者 | 版本 | 组件类型 | 用途 | 状态 |
|------|------|------|----------|------|------|
| **WebSearch** | RockChinQ | 0.1.0 | Tool | LLM 联网搜索 | 待安装 |
| **ScheNotify** | langbot-team | 0.2.0 | Command+Tool | 自然语言日程提醒 | 待安装 |
| **TaskTimer** | sheetung | 0.1.9 | EventListener | 定时触发任务脚本 | 待安装 |
| **LinkAnaly** | sheetung | 1.0.5 | EventListener | 链接解析+截图 | 待安装 |
| **Markdowm2ing_Pro** | Typer_Body | 1.1.0 | EventListener | Markdown转图片 | 待安装 |
| **ContextKeeper** | hello-2066 | 1.2.2 | EventListener | 上下文持久化 | 待安装 |
| **Text2LangbotMsgChain** | shinelinxx | 1.0.0 | EventListener | 文本转消息链 | 待安装 |
| **RAGFlowRetriever** | langbot-team | 0.1.0 | KnowledgeRetriever | RAGFlow知识库检索 | 待安装 |
| **trendradar** | TrendRadar | 1.0.0 | Command | 配置查看 | 已安装 |

---

## 核心插件详解

### 1. WebSearch (联网搜索)

**功能**: 为 LLM 提供联网搜索能力

```
组件类型: Tool (供LLM调用)
安装量: 314+
仓库: langbot-app/langbot-plugin-demo
```

**与 TrendRadar 结合点**:
- AI 分析时可调用搜索补充上下文
- 实现 ROADMAP 中的"联网信息发散"功能
- 搜索相关公司/行业/政策信息增强分析

**配置参数**: (待确认)
- 搜索 API 密钥
- 搜索引擎选择

---

### 2. ScheNotify (日程提醒)

**功能**: 使用自然语言设置定时提醒

```
组件类型: Command (2) + Tool (2)
安装量: 125+
仓库: langbot-app/langbot-plugin-demo
```

**与 TrendRadar 结合点**:
- 用户可设置"每天早上8点推送今日财经要闻"
- 支持自然语言: "提醒我下午3点查看A股收盘情况"
- 定时触发 TrendRadar 分析任务

**使用示例**:
```
用户: 提醒我每天早上9点推送财经新闻摘要
LLM: 好的，已为您设置每日 9:00 的财经新闻推送提醒
```

---

### 3. TaskTimer (定时任务)

**功能**: 定时触发任务脚本

```
组件类型: EventListener (1)
安装量: 192+
仓库: sheetung/TaskTimer
```

**与 TrendRadar 结合点**:
- 定时触发新闻推送 (替代外部 cron)
- 定时生成日报/周报
- 定时执行 AI 分析任务

**关键能力**:
- 支持 cron 表达式
- 可执行自定义脚本
- 事件驱动触发

---

### 4. LinkAnaly (链接解析)

**功能**: 解析聊天中的链接，截图发送

```
组件类型: EventListener (1)
安装量: 379+ (最高)
仓库: sheetung/LinkAnalyPlugin
```

**与 TrendRadar 结合点**:
- 用户分享新闻链接时自动解析
- 提取链接内容供 AI 分析
- 生成新闻预览卡片

**使用场景**:
```
用户: [粘贴一个财经新闻链接]
机器人: [自动解析链接内容]
        [生成预览截图]
        [可选: 触发 AI 分析]
```

---

### 5. Markdowm2ing_Pro (Markdown转图片)

**功能**: 将 AI 回复中的 Markdown 转换为精美图片

```
组件类型: EventListener (1)
安装量: 161+
仓库: TyperBody/Langbot_M2Img_Pro
```

**功能特性**:
- 智能识别 Markdown 语法
- 自定义渲染样式 (ZIP配置)
- 异步处理，避免阻塞
- 支持链接提取

**与 TrendRadar 结合点**:
- AI 分析报告以图片形式发送 (更美观)
- 财经数据表格渲染
- 长文本分析结果可视化

**支持的 Markdown 语法**:
- 标题 (#, ##, ###)
- 粗体/斜体
- 代码块
- 列表/引用块
- 链接/图片
- 表格

---

### 6. ContextKeeper (上下文守护者)

**功能**: 持久化对话上下文，解决重启失忆问题

```
组件类型: EventListener (1)
安装量: 53+
```

**与 TrendRadar 结合点**:
- 保持用户订阅偏好
- 记住用户关注的关键词/股票
- 跨会话保持分析上下文

---

### 7. Text2LangbotMsgChain (文本转消息链)

**功能**: 将结构化文本响应转换为 LangBot 消息链

```
组件类型: EventListener (1)
安装量: 65+
仓库: shinelinxx/Text2LangbotMsgChain
```

**与 TrendRadar 结合点**:
- 将 TrendRadar 的结构化推送内容转为消息链
- 支持图文混排
- 支持卡片消息格式

---

### 8. RAGFlowRetriever (知识库检索)

**功能**: 从 RAGFlow 知识库检索知识

```
组件类型: KnowledgeRetriever (1)
安装量: 107+
```

**RAGFlow 简介**:
RAGFlow 是开源的 RAG (检索增强生成) 引擎，基于深度文档理解。

**与 TrendRadar 结合点**:
- 存储历史新闻和分析报告
- 实现 ROADMAP 中的"历史信息分析"
- 支持语义相似度搜索
- 构建财经知识库

---

## TrendRadar 自定义插件

### trendradar (配置查看)

**当前功能**:

| 命令 | 功能 | 状态 |
|------|------|------|
| `!tr` | 显示帮助 | 已实现 |
| `!tr help` | 显示帮助 | 已实现 |
| `!tr keywords` | 显示关键词配置 | 已实现 |
| `!tr prompt` | 显示 AI 提示词 | 已实现 |
| `!tr status` | 显示推送状态 | 已实现 |

**计划扩展**:

| 命令 | 功能 | 优先级 |
|------|------|--------|
| `!tr subscribe <关键词>` | 订阅关键词 | P1 |
| `!tr unsubscribe <关键词>` | 取消订阅 | P1 |
| `!tr search <查询>` | 搜索历史新闻 | P2 |
| `!tr report [daily/weekly]` | 生成报告 | P2 |
| `!tr analyze <链接>` | 分析指定新闻 | P2 |

---

## 插件交互流程

### 当前流程 (基础)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      当前消息处理流程                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户消息 ──▶ LangBot Pipeline ──▶ 命令解析                         │
│                                      │                               │
│                                      ▼                               │
│                              ┌──────────────┐                       │
│                              │ !tr 命令?    │                       │
│                              └──────┬───────┘                       │
│                                     │                               │
│                      ┌──────────────┼──────────────┐                │
│                      ▼              ▼              ▼                │
│               !tr keywords    !tr status    !tr prompt              │
│                      │              │              │                │
│                      └──────────────┼──────────────┘                │
│                                     ▼                               │
│                              返回配置信息                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 目标流程 (增强)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      增强消息处理流程                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户消息 ──▶ LinkAnaly ──▶ 链接检测 ──▶ 内容提取                   │
│      │                                      │                       │
│      │                                      ▼                       │
│      │                              WebSearch 补充信息               │
│      │                                      │                       │
│      ▼                                      ▼                       │
│  LangBot Pipeline ◀──────────────── 增强上下文                      │
│      │                                                               │
│      ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AI 处理 (LLM)                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ WebSearch   │  │ ScheNotify  │  │ RAGFlowRetriever   │  │   │
│  │  │ (联网搜索)  │  │ (设置提醒)  │  │ (知识库检索)       │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                               │
│      ▼                                                               │
│  Text2LangbotMsgChain ──▶ Markdowm2ing_Pro ──▶ 消息发送            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    后台任务                                   │   │
│  │  TaskTimer ──▶ TrendRadar Daemon ──▶ 新闻推送                │   │
│  │       │                                    │                 │   │
│  │       └────── ScheNotify 触发 ─────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ContextKeeper ──▶ 持久化用户偏好和上下文                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 配置指南

### 插件安装

通过 LangBot WebUI (http://localhost:5300) 安装:

1. 进入"插件管理"页面
2. 点击"从市场安装"
3. 搜索并安装所需插件

或通过命令行:
```bash
# 在飞书群聊中 (需管理员权限)
!plugin get https://github.com/xxx/xxx
```

### 推荐安装顺序

1. **基础功能**: ContextKeeper (解决重启失忆)
2. **输出美化**: Markdowm2ing_Pro + Text2LangbotMsgChain
3. **信息增强**: WebSearch + LinkAnaly
4. **定时任务**: TaskTimer + ScheNotify
5. **知识库**: RAGFlowRetriever (需部署 RAGFlow)

### Pipeline 配置

LangBot 4.x 支持不同 Pipeline 配置不同插件:

```yaml
# 示例: 财经分析 Pipeline
pipeline:
  name: finance-analysis
  plugins:
    - WebSearch
    - RAGFlowRetriever
    - trendradar
  mcp_servers: []
```

---

## 开发路线

### Phase 1: 基础集成 (当前)

- [x] trendradar 命令插件
- [ ] 安装核心插件 (WebSearch, TaskTimer, Markdowm2ing_Pro)
- [ ] 配置 Pipeline

### Phase 2: 功能增强

- [ ] 重构 trendradar 插件代码
- [ ] 实现 `!tr subscribe` 订阅功能
- [ ] 集成 TaskTimer 定时推送
- [ ] 集成 WebSearch 增强分析

### Phase 3: 高级功能

- [ ] 部署 RAGFlow 知识库
- [ ] 实现历史新闻检索
- [ ] 实现交易信号生成
- [ ] 用户偏好持久化

---

## 参考链接

- [LangBot 插件市场](https://space.langbot.app/market)
- [LangBot 插件开发教程](https://docs.langbot.app/zh/plugin/dev/tutor)
- [LangBot GitHub](https://github.com/langbot-app/LangBot)

---

*文档维护: Claude Code*
*版本: 1.0.0*
