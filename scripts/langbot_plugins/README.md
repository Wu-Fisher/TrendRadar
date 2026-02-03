# LangBot 插件

本目录包含 TrendRadar 的 LangBot 插件源代码。

## 插件列表

### TrendRadar__push_queue

推送队列处理插件，监听 `.push_queue/` 目录并通过 LangBot 发送消息到飞书群。

**功能**:
- 轮询 `config/.push_queue/` 目录
- 解析 JSON 消息文件
- 通过 LangBot `send_message` API 发送到飞书
- 支持三种消息类型: raw (原始)、ai_analysis (AI分析)、daily_report (日报)

**配置** (在 LangBot 管理界面):
```yaml
bot_uuid: "your-bot-uuid"           # LangBot 中配置的飞书机器人 UUID
target_type: "group"                # 目标类型 (group/person)
target_id: "oc_xxx"                 # 飞书群/用户 ID
queue_dir: "/app/trendradar_config/.push_queue"  # 队列目录
poll_interval: 2                    # 轮询间隔 (秒)
```

## 部署方式

### 方式 1: 手动复制

```bash
# 复制插件到 LangBot 数据目录
cp -r scripts/langbot_plugins/TrendRadar__push_queue docker/langbot_data/plugins/

# 重启 plugin runtime
docker compose -f docker/docker-compose-langbot.yml restart langbot_plugin_runtime
```

### 方式 2: 使用部署脚本

```bash
cd docker
./deploy.sh restart
```

## 开发说明

1. 修改源代码后，需要同步到 `docker/langbot_data/plugins/`
2. 插件目录命名规范: `{author}__{plugin_name}` (双下划线)
3. 必须包含 `manifest.yaml` 和组件的 `.yaml` 描述文件

## 架构说明

详见 [架构原则文档](../docs/ARCHITECTURE_PRINCIPLES.md)
