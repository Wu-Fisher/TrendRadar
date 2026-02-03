# Claude Code 操作备忘录

本文档记录 Claude Code 在此项目中的特殊操作方式和测试信息，供后续参考。

---

## 1. Docker 命令执行

### 问题
Claude Code 运行环境中，当前用户 `wufisher` 虽然属于 `docker` 组，但会话中未激活该组权限，导致直接运行 `docker` 命令会报错：

```
permission denied while trying to connect to the Docker daemon socket
```

### 解决方案
使用 `sg docker -c "命令"` 切换到 docker 组后执行命令：

```bash
# 查看容器状态
sg docker -c "docker ps"

# 启动服务
sg docker -c "docker compose -f docker-compose-build.yml up -d"

# 查看日志
sg docker -c "docker logs -f trendradar"

# 重启容器
sg docker -c "docker restart trendradar"

# 执行容器内命令
sg docker -c "docker exec trendradar ls -la /app/scripts"
```

### 完整启动命令

**推荐使用部署脚本** (`docker/deploy.sh`)：

```bash
cd /home/wufisher/ws/dev/TrendRadar/docker

# 完整部署 (构建 + 启动所有服务)
./deploy.sh full

# 其他常用命令
./deploy.sh status    # 查看状态
./deploy.sh logs      # 查看日志
./deploy.sh restart   # 重启服务
./deploy.sh stop      # 停止服务
```

**手动命令** (Claude Code 需用 `sg docker -c`):

```bash
cd /home/wufisher/ws/dev/TrendRadar/docker

# 构建镜像
sg docker -c "docker compose -f docker-compose-build.yml build trendradar"

# 启动 LangBot + 插件系统
sg docker -c "docker compose -f docker-compose-langbot.yml up -d langbot langbot_plugin_runtime"

# 启动 TrendRadar + 飞书推送服务
sg docker -c "docker compose -f docker-compose-build.yml --profile feishu up -d"

# 停止所有服务
sg docker -c "docker compose -f docker-compose-build.yml --profile feishu down"
sg docker -c "docker compose -f docker-compose-langbot.yml down"
```

---

## 2. 常用调试命令

```bash
# 查看主服务日志
sg docker -c "docker logs --tail 100 trendradar"

# 查看飞书推送日志
sg docker -c "docker logs --tail 100 feishu_push"

# 清除爬虫缓存（触发重新推送）
sg docker -c "docker exec trendradar rm -f /app/output/crawler/crawler.db"
sg docker -c "docker restart trendradar"

# 查看推送队列
ls -la /home/wufisher/ws/dev/TrendRadar/config/.push_queue/

# 验证脚本版本
sg docker -c "docker exec trendradar wc -l /app/scripts/run_crawler_daemon.py"
```

---

## 3. 本地测试命令

### 语法检查
```bash
python3 -m py_compile scripts/run_crawler_daemon.py trendradar/core/loader.py trendradar/core/config_manager.py
```

### 测试 ConfigManager
```bash
python3 -c "
from trendradar.core import load_config, ConfigManager

config = load_config()
cfg = ConfigManager(config)

print('AI 模型:', cfg.ai.model)
print('AI 超时:', cfg.ai.timeout)
print('队列大小:', cfg.ai.queue.max_size)
print('飞书批次:', cfg.notification.feishu_batch_size)
print('时区:', cfg.app.timezone)
print('邮件启用:', cfg.notification.email_enabled)
"
```

### 测试 models 导入
```bash
python3 -c "
from trendradar.models import (
    NewsAnalysisResult,
    BatchAnalysisResult,
    TranslationResult,
    TaskStatus,
    QueueTask,
    get_mobile_url,
)
print('所有 models 导入成功')
print('TaskStatus:', list(TaskStatus))
"
```

### 测试 logging 模块
```bash
python3 -c "
from trendradar.logging import setup_logging, get_logger

setup_logging(level='DEBUG')
logger = get_logger('test')

logger.debug('调试信息')
logger.info('普通信息')
logger.warning('警告信息')
logger.error('错误信息')
"
```

### 测试 Daemon 启动（不执行爬取）
```bash
python3 -c "
from scripts.run_crawler_daemon import CrawlerDaemon
from trendradar.core import load_config

config = load_config()
daemon = CrawlerDaemon(
    config=config,
    poll_interval=10,
    enable_push=False,
    enable_ai=False,
    verbose=False
)
print('Daemon 初始化成功')
print('ConfigManager 可用:', hasattr(daemon, 'cfg'))
print('时区:', daemon.cfg.app.timezone)
"
```

---

## 4. Docker 内测试

```bash
# 验证配置加载
sg docker -c "docker exec trendradar python3 -c \"
from trendradar.core import load_config, ConfigManager
cfg = ConfigManager(load_config())
print('时区:', cfg.app.timezone)
print('邮件启用:', cfg.notification.email_enabled)
print('AI 模型:', cfg.ai.model)
\""

# 验证 models 模块
sg docker -c "docker exec trendradar python3 -c \"
from trendradar.models import NewsAnalysisResult, get_mobile_url
print('models 模块可用')
\""

# 单次运行测试
sg docker -c "docker exec trendradar python3 scripts/run_crawler_daemon.py --once --verbose"
```

---

## 5. 注意事项

1. **必须使用 `sg docker -c`** - 直接运行 docker 命令会失败
2. **sandbox 模式** - 某些操作可能需要 `dangerouslyDisableSandbox: true`
3. **超时设置** - 长时间操作需增加 timeout（如 180000ms）
4. **配置文件位置** - `/home/wufisher/ws/dev/TrendRadar/config/config.yaml`
5. **日志级别** - daemon 使用 `--verbose` 启用 DEBUG 级别

---

## 6. LangBot 插件集成

### 架构概览
```
┌────────────────────────────────────────────────────────────┐
│                     TrendRadar 推送架构                      │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  实时推送 (<1min):                                          │
│  TrendRadar ──▶ Push Queue ──▶ feishu_push ──▶ 飞书群聊    │
│  (daemon)       (.json 文件)    (2s 轮询)                   │
│                                                             │
│  定时日报 (每日):                                           │
│  TaskTimer ──▶ trendradar_push.py ──▶ LangBot ──▶ 飞书群聊 │
│  (APScheduler)   (读取 DB)                                  │
│                                                             │
│  命令交互:                                                  │
│  用户 ──▶ !tr 命令 ──▶ LangBot Plugin ──▶ 配置/状态查看    │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 部署的插件
| 插件 | 用途 | 状态 |
|------|------|------|
| trendradar | !tr 命令 (查看配置/状态) | ✅ 已部署 |
| TaskTimer | 定时任务 (日报推送) | ✅ 已配置 |
| WebSearch | AI 联网搜索 | 待启用 |
| LinkAnaly | 链接解析 | 待集成 |

### 命令说明
```bash
# 飞书群聊发送
!tr           # 显示帮助
!tr status    # 查看推送队列状态
!tr keywords  # 查看关键词配置
!tr prompt    # 查看 AI 分析提示词
```

### TaskTimer 日报配置
tasks.yaml 位置: `docker/langbot_data/plugins/sheetung__TaskTimer/config/tasks.yaml`

```yaml
tasks:
  - schedule: '0 9 * * *'         # 每天早上9点
    script: 'trendradar_push.py'
    enabled: true
    description: 'TrendRadar 财经日报'
    target_type: 'group'
    target_id: 'oc_xxx'           # 飞书群聊ID
    bot_uuid: 'xxx'               # LangBot Bot UUID
```

### 部署 LangBot 集成脚本
```bash
cd docker
./deploy.sh deploy-scripts    # 部署 TaskTimer 脚本
./deploy.sh restart           # 重启服务使配置生效
```

---

## 7. 项目特定信息

### 关键文件
| 文件 | 说明 |
|------|------|
| `scripts/run_crawler_daemon.py` | Daemon 入口，已使用 logging + ConfigManager |
| `trendradar/core/config_manager.py` | ConfigManager 类，12+ 个配置 dataclass |
| `trendradar/models/` | 统一数据模型目录 |
| `trendradar/logging.py` | 日志配置模块 |
| `trendradar/constants.py` | 项目常量定义 |

### 配置键名规范
- loader.py 输出全部为**大写键名**（如 `FEISHU_WEBHOOK_URL`）
- 嵌套配置也是大写（如 `AI.QUEUE.MAX_SIZE`）
- ConfigManager 将其映射为 snake_case 属性（如 `cfg.ai.queue.max_size`）

### 多账号配置格式
Webhook URL 支持分号分隔多个账号：
```yaml
FEISHU_WEBHOOK_URL: "https://url1;https://url2;https://url3"
```
最多支持 3 个账号（`Limits.MAX_ACCOUNTS_PER_CHANNEL`）

---

*更新时间: 2026-02-02 22:45*
