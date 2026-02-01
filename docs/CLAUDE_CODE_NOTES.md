# Claude Code 操作备忘录

本文档记录 Claude Code 在此项目中的特殊操作方式，供后续参考。

---

## Docker 命令执行

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

```bash
# 启动 TrendRadar + 飞书推送服务
cd /home/wufisher/ws/dev/TrendRadar/docker
sg docker -c "docker compose -f docker-compose-build.yml --profile feishu up -d --force-recreate"

# 只启动 TrendRadar（不含飞书）
sg docker -c "docker compose -f docker-compose-build.yml up -d trendradar"
```

---

## 常用调试命令

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

## 注意事项

1. **必须使用 `sg docker -c`** - 直接运行 docker 命令会失败
2. **sandbox 模式需禁用** - `dangerouslyDisableSandbox: true`
3. **超时设置** - 长时间操作需增加 timeout（如 180000ms）
