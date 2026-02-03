# TrendRadar + LangBot 开发计划 (最终版)

> 版本: 3.0 Final
> 日期: 2026-02-02
> 基于: 插件代码实际分析 + 集成测试

---

## 一、核心发现

### 1.1 已安装插件清单

| 插件 | 组件类型 | 核心能力 | 集成价值 |
|------|----------|----------|----------|
| **TaskTimer** | EventListener | cron定时 + 脚本执行 + 消息发送 | ⭐⭐⭐ 定时推送 |
| **WebSearch** | Tool | LLM联网搜索 | ⭐⭐⭐ AI分析增强 |
| **LinkAnaly** | EventListener | 链接解析 + 截图 | ⭐⭐ 新闻链接预览 |
| **ScheNotify** | Command+Tool | 自然语言日程 | ⭐⭐ 用户自定义提醒 |
| **ContextKeeper** | EventListener | 上下文持久化 | ⭐⭐ 用户偏好保存 |
| **Markdowm2ing_Pro** | EventListener | Markdown转图片 | ⭐⭐ 报告美化 |
| **RAGFlowRetriever** | KnowledgeRetriever | 知识库检索 | ⭐ 历史分析(需部署) |
| **GoogleSearch** | Tool | Google搜索 | ⭐ 备用搜索 |
| **SysStatPlugin** | - | 系统状态 | - 运维监控 |

### 1.2 关键代码洞察

**TaskTimer 核心机制** (`default.py:166-230`):
```python
# 关键发现: 可以通过 plugin.send_message() 主动推送
await self.plugin.send_message(
    bot_uuid=self.bot_uuid,
    target_type='group',      # group 或 person
    target_id='群聊ID',
    message_chain=MessageChain([...])
)
```

**LinkAnaly 链接处理模式** (`default.py:24-29`):
```python
# 关键发现: 使用正则匹配 + handler 分发
for platform in self.link_handlers.values():
    match = self._match_link(msg, platform["patterns"])
    if match:
        await platform["handler"](event_context, match)
        return
```

---

## 二、开发路线 (精简版)

### Phase 1: 即刻可用 (本周)

| 任务 | 说明 | 依赖 | 工作量 |
|------|------|------|--------|
| **1.1 部署 TaskTimer 推送脚本** | 已创建 `trendradar_push.py` | TaskTimer | 10min |
| **1.2 配置飞书群聊定时推送** | 修改 tasks.yaml | 1.1 | 5min |
| **1.3 重构 trendradar 命令插件** | 消除重复代码 | - | 30min |

**1.1 部署命令**:
```bash
# 复制脚本到 TaskTimer 插件目录
sudo cp scripts/langbot_integrations/trendradar_push.py \
    docker/langbot_data/plugins/sheetung__TaskTimer/func/

# 编辑 tasks.yaml 添加任务
```

**1.2 tasks.yaml 配置**:
```yaml
tasks:
  - schedule: '0 9 * * *'      # 每天早上9点
    script: 'trendradar_push.py'
    enabled: true
    description: 'TrendRadar 财经早报'
    target_type: 'group'
    target_id: 'oc_d29285f2dd1702ea24430464a43acc8c'  # 飞书群聊ID
```

### Phase 2: 功能增强 (下周)

| 任务 | 说明 | 依赖 | 工作量 |
|------|------|------|--------|
| **2.1 财经链接解析** | 仿照 LinkAnaly 添加同花顺链接解析 | trendradar 插件 | 2h |
| **2.2 WebSearch 集成** | AI 分析时自动搜索补充信息 | WebSearch 启用 | 1h |
| **2.3 ScheNotify 联动** | "每天9点推送XX板块新闻" | ScheNotify + TaskTimer | 1h |

**2.1 财经链接解析示例**:
```python
# 添加到 trendradar 插件
self.link_handlers = {
    "ths_news": {
        "patterns": [r"10jqka\.com\.cn/(\d+)\.shtml"],
        "handler": self.handle_ths_news
    },
    "eastmoney": {
        "patterns": [r"eastmoney\.com/a/(\d+)\.html"],
        "handler": self.handle_eastmoney
    }
}
```

### Phase 3: 高级功能 (月度)

| 任务 | 说明 | 依赖 | 工作量 |
|------|------|------|--------|
| **3.1 订阅系统** | `!tr subscribe AI` 订阅关键词 | ContextKeeper | 4h |
| **3.2 AI 报告图片化** | 分析报告自动转精美图片 | Markdowm2ing_Pro | 2h |
| **3.3 历史检索** | "上次央行降准后市场反应?" | RAGFlow 部署 | 8h+ |

---

## 三、架构演进

### 当前架构 (简单但有效)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           当前架构                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  TrendRadar Daemon ──▶ Push Queue ──▶ feishu_push ──▶ 飞书群聊      │
│       │                                                              │
│       └──────────────── 邮件/钉钉/TG 等渠道                          │
│                                                                      │
│  LangBot ──▶ !tr 命令 ──▶ 查看配置/状态                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 目标架构 (插件协同)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         目标架构 (插件协同)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 TrendRadar Core (不变)                       │   │
│  │  Crawler ──▶ AI Analyzer ──▶ Push Queue                     │   │
│  └───────────────────────────────┬─────────────────────────────┘   │
│                                  │                                  │
│                                  ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 LangBot 插件层 (新增)                        │   │
│  │                                                              │   │
│  │  ┌───────────────┐   ┌───────────────┐   ┌──────────────┐  │   │
│  │  │  TaskTimer    │   │  trendradar   │   │  LinkAnaly   │  │   │
│  │  │  定时推送      │   │  命令+链接    │   │  扩展解析    │  │   │
│  │  └───────┬───────┘   └───────┬───────┘   └──────┬───────┘  │   │
│  │          │                   │                   │          │   │
│  │          ▼                   ▼                   ▼          │   │
│  │  ┌─────────────────────────────────────────────────────┐   │   │
│  │  │               plugin.send_message()                  │   │   │
│  │  └─────────────────────────────────────────────────────┘   │   │
│  └───────────────────────────────┬─────────────────────────────┘   │
│                                  │                                  │
│                                  ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │               LangBot Core (Bot Manager)                     │   │
│  │                      │                                       │   │
│  │          ┌───────────┼───────────┐                          │   │
│  │          ▼           ▼           ▼                          │   │
│  │      飞书Bot      QQ Bot     钉钉Bot                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 辅助插件 (按需启用)                           │   │
│  │                                                              │   │
│  │  WebSearch ─── AI分析时联网补充信息                          │   │
│  │  ScheNotify ── 用户自然语言设置提醒                          │   │
│  │  ContextKeeper ── 保存用户订阅偏好                           │   │
│  │  Markdown2Img ── AI报告转精美图片                            │   │
│  │  RAGFlowRetriever ── 历史新闻检索 (需部署RAGFlow)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、关键洞察

### 4.1 复用而非重造

| 需求 | 原计划 | 使用插件 |
|------|--------|----------|
| 定时推送 | 外部 cron | **TaskTimer** (内置 APScheduler) |
| 联网搜索 | 自己实现 API 调用 | **WebSearch** (LLM 自动调用) |
| 链接预览 | 自己实现 | **LinkAnaly** (扩展 handler) |
| 日程提醒 | 自己实现 | **ScheNotify** (自然语言) |
| 用户偏好 | 数据库存储 | **ContextKeeper** (自动持久化) |

### 4.2 插件启发的新功能

| 灵感来源 | 新功能想法 |
|----------|------------|
| LinkAnaly 的链接匹配 | 财经新闻链接自动解析摘要 |
| TaskTimer 的 send_message | 直接通过 LangBot 推送，无需 feishu_push 中间件 |
| WebSearch 的 Tool 模式 | TrendRadar 数据查询也可封装为 Tool |
| ScheNotify 的自然语言 | "帮我关注比亚迪相关新闻" |

### 4.3 简化推送架构

**发现**: TaskTimer 的 `plugin.send_message()` 可以直接发送消息到群聊，这意味着：

```
旧方案: TrendRadar ──▶ Push Queue ──▶ feishu_push ──▶ 飞书
新方案: TrendRadar ──▶ TaskTimer 脚本 ──▶ LangBot ──▶ 飞书
```

新方案优势：
- 减少一个中间服务 (feishu_push)
- 统一走 LangBot 消息通道
- 可利用 Markdown2Img 美化输出

---

## 五、立即行动清单

### 已完成 ✅

- [x] 检查实时推送机制 (feishu_push 服务正常运行)
- [x] 重构 trendradar 命令插件 (消除重复代码，添加日志)
- [x] 更新 docker-compose-langbot.yml (添加 output 目录挂载)
- [x] 创建 trendradar_push.py 日报脚本
- [x] 更新 deploy.sh 添加 deploy-scripts 命令

### 待配置

- [ ] 在 TaskTimer tasks.yaml 添加 TrendRadar 日报任务
- [ ] 重启 langbot_plugin_runtime 容器生效配置
- [ ] 添加财经链接解析功能 (仿照 LinkAnaly)
- [ ] 在 Pipeline 中启用 WebSearch

### 验证命令

```bash
# 部署脚本到 TaskTimer
cd docker
./deploy.sh deploy-scripts

# 重启插件运行时使配置生效
./deploy.sh restart

# 测试日报脚本 (本地)
TRENDRADAR_CONFIG_DIR=../config TRENDRADAR_OUTPUT_DIR=../output \
  python3 ../scripts/langbot_integrations/trendradar_push.py

# 查看 TaskTimer 日志
docker logs langbot_plugin_runtime 2>&1 | grep -i tasktimer
```

---

## 六、文件索引

| 文件 | 说明 |
|------|------|
| `docs/LANGBOT_PLUGINS_GUIDE.md` | 插件系统指南 (详细) |
| `docs/LANGBOT_INTEGRATION_REPORT.md` | 集成研究报告 (技术) |
| `scripts/langbot_integrations/trendradar_push.py` | TaskTimer 日报脚本 |
| `docker/langbot_data/plugins/trendradar/` | TrendRadar 命令插件 |
| `docker/langbot_data/plugins/sheetung__TaskTimer/` | TaskTimer 插件 |
| `docker/docker-compose-langbot.yml` | LangBot Docker 配置 |
| `docker/deploy.sh` | 部署脚本 (含 deploy-scripts 命令) |

---

*报告完成 | Claude Code | 2026-02-02*
*最后更新: 2026-02-02 22:45*
