# LangBot + 飞书（Lark）部署与配置指南

本文档记录如何部署 LangBot 并配置飞书机器人，实现消息收发。

## 前置条件

- Docker 环境已就绪
- 飞书开发者账号（https://open.feishu.cn）
- 无需公网 IP（使用 WebSocket 长连接模式）

## 一、部署 LangBot

### 1. 启动容器

```bash
cd docker
echo 'docker compose -f docker-compose-langbot.yml up -d' | newgrp docker
```

> 如果 Docker 权限正常，直接 `docker compose -f docker-compose-langbot.yml up -d` 即可。

### 2. 验证服务

- WebUI: http://localhost:5300
- 插件运行时: http://localhost:5401

容器列表：
- `langbot` — 主服务（WebUI + 平台连接）
- `langbot_plugin_runtime` — 插件独立进程

## 二、创建飞书应用

### Step 1: 创建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)
2. 点击「创建企业自建应用」
3. 填写应用名称和描述，完成创建

### Step 2: 获取凭证

在应用的「凭证与基础信息」页面，记录：
- **App ID**
- **App Secret**

### Step 3: 添加机器人能力

1. 进入应用 → 「添加应用能力」
2. 选择「机器人」，点击添加

### Step 4: 配置权限

进入「权限管理」，可通过「批量开通」粘贴以下 JSON 一次性添加所有权限：

```json
[
  {
    "key": "im:message",
    "type": 1
  },
  {
    "key": "im:message:send_as_bot",
    "type": 1
  },
  {
    "key": "im:message.group_at_msg",
    "type": 1
  },
  {
    "key": "im:message.group_at_msg:readonly",
    "type": 1
  },
  {
    "key": "im:message.p2p_msg",
    "type": 1
  },
  {
    "key": "im:message.p2p_msg:readonly",
    "type": 1
  },
  {
    "key": "im:resource",
    "type": 1
  }
]
```

### Step 5: 发布应用

1. 进入「版本管理与发布」
2. 创建版本 → 填写版本号和更新说明
3. 提交审核（企业管理员审核通过后生效）
4. 审核通过后，在飞书客户端搜索机器人名称确认可见

### Step 6: 配置 LangBot（WebUI）

**重要：此步骤必须在配置飞书 WebSocket 之前完成。**

1. 打开 LangBot WebUI: http://localhost:5300
2. 进入「平台设置」→ 飞书
3. 填入 **App ID** 和 **App Secret**
4. 保存配置

### Step 7: 配置飞书 WebSocket 长连接

**必须在 Step 6 之后执行**，因为飞书平台要求应用先通过 App ID/Secret 完成一次认证调用后，才允许启用 WebSocket。

1. 回到飞书开放平台 → 应用 → 「事件与回调」
2. 选择「长连接」模式（WebSocket）
3. 如果提示不可选择，请确认 Step 6 已完成且 LangBot 已成功连接一次

### Step 8: 订阅事件

在飞书开放平台 → 应用 → 「事件与回调」→ 「事件订阅」中添加：

| 事件 | 事件名称 |
|------|----------|
| im.message.receive_v1 | 接收消息 |

### Step 9: 配置 LangBot 大模型

在 LangBot WebUI 的「模型设置」中配置 AI 模型：

- **Provider**: OpenAI Compatible
- **API Base**: `https://api.siliconflow.cn/v1`
- **API Key**: 你的 SiliconFlow API Key
- **Model**: `Pro/deepseek-ai/DeepSeek-V3.2`

> 注意：LangBot 的模型配置独立于 StockTrendRadar 的 `config/config.yaml` 中的 AI 配置。两者各自管理自己的模型。

### Step 10: 测试消息收发

1. 在飞书客户端找到机器人
2. 发送一条测试消息
3. 确认机器人回复正常

## 三、架构说明

```
飞书用户 ←WebSocket→ 飞书平台 ←WebSocket→ LangBot (port 5300)
                                              ↓
                                         LangBot Plugin Runtime (port 5401)
                                              ↓
                                    共享配置卷 ../config (读写)
                                              ↓
                                    StockTrendRadar 配置文件
```

- **LangBot** 负责消息交互层（飞书消息收发、对话管理）
- **StockTrendRadar Daemon** 负责数据采集和推送（独立运行，不受 LangBot 影响）
- 两者通过共享配置文件卷实现解耦协作

## 四、常用命令

```bash
# 启动
docker compose -f docker-compose-langbot.yml up -d

# 查看日志
docker logs -f langbot

# 停止
docker compose -f docker-compose-langbot.yml down

# 重启
docker compose -f docker-compose-langbot.yml restart
```
