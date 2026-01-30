# TrendRadar 部署指南

## 当前配置

| 配置项 | 值 |
|--------|-----|
| 数据源 | 财联社热门 + 同花顺RSS |
| RSS 地址 | `https://rsshub.rssforever.com/10jqka/realtimenews` |
| 执行频率 | 每 2 分钟 |
| 推送模式 | incremental（增量更新，只推送新内容） |
| 版本检查 | 已禁用 |
| AI 分析 | 已禁用 |
| Web 查看 | http://localhost:8080 |

---

## 新机器部署

### 1. 安装 Docker
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# 重新登录生效
```

### 2. 复制项目
```
TrendRadar/
├── config/
│   ├── config.yaml
│   └── frequency_words.txt
├── docker/
│   ├── docker-compose.yml
│   └── .env
├── trendradar/           # 代码目录（本地开发需要）
└── output/               # 数据目录（可不复制）
```

### 3. 启动服务
```bash
cd TrendRadar/docker
docker compose pull trendradar
docker compose up -d trendradar
```

### 4. 验证
```bash
# 查看日志
docker logs -f trendradar

# 浏览器访问
http://localhost:8080
```

---

## 常用命令

| 操作 | 命令 |
|------|------|
| 启动 | `docker compose up -d trendradar` |
| 停止 | `docker compose down` |
| 重启 | `docker compose restart trendradar` |
| 日志 | `docker logs -f trendradar` |
| 手动执行 | `docker exec -it trendradar python manage.py run` |

---

## 配置说明

### 执行频率 (`docker/.env`)
```bash
CRON_SCHEDULE=*/2 * * * *   # 每2分钟
# CRON_SCHEDULE=*/5 * * * * # 每5分钟
# CRON_SCHEDULE=*/30 * * * * # 每30分钟
```

### 数据源 (`config/config.yaml`)

**热榜平台**（第32-36行）：
```yaml
platforms:
  enabled: false              # 不启用（但需保留一个避免报错）
  sources:
    - id: "cls-hot"
      name: "财联社热门"
```

**RSS 订阅**（第70-74行）：
```yaml
feeds:
  - id: "10jqka-realtime"
    name: "同花顺实时快讯"
    url: "https://rsshub.rssforever.com/10jqka/realtimenews"
    max_age_days: 0
```

### 显示区域 (`config/config.yaml` 第157-166行)
```yaml
regions:
  hotlist: false        # 热榜区域
  new_items: false      # 新增热点
  rss: false            # RSS关键词分析
  standalone: true      # 独立展示区（完整显示）
  ai_analysis: false    # AI分析
```

---

## 备用 RSS 镜像

如果当前镜像超时，可替换：
- `https://rss.shab.fun/10jqka/realtimenews`
- `https://rsshub.pseudoyu.com/10jqka/realtimenews`

> 注：`rsshub.app` 已限制访问，不推荐使用

---

## 已知问题

1. **`platforms.enabled: false` 不生效**
   程序 bug，热榜仍会抓取。需保留至少一个平台避免报错。

2. **执行间隔太短会冲突**
   如果任务执行超过间隔时间，会出现警告。建议至少 2 分钟。

---

## 开发记录

### 2025-01-29: RSS 时区转换功能

**问题**：RSS 时间显示原始 ISO 格式（如 `2025-01-29T08:20:00+00:00`），不直观。

**解决**：修改 `rss_html.py`，使用 `format_iso_time_friendly()` 转换为配置时区的友好格式。

**修改文件**：
- `trendradar/report/rss_html.py` - 添加时区参数，调用转换函数
- `trendradar/__main__.py` - 传入 timezone 配置

**效果**：时间显示为北京时间，格式 `01-29 16:20`。

### 2025-01-29: 推送模式改为增量

**修改**：`config/config.yaml` 中 `report.mode` 从 `current` 改为 `incremental`。

**效果**：只推送新出现的新闻，避免重复。

### 2025-01-29: Docker 挂载代码目录

**问题**：本地代码修改不生效，容器使用镜像自带代码。

**解决**：`docker/docker-compose.yml` 添加代码目录挂载：
```yaml
volumes:
  - ../trendradar:/app/trendradar:ro
```

**注意**：修改后需要重建容器：
```bash
docker compose down && docker compose up -d trendradar
```

### 2025-01-30: 同花顺7x24爬虫开发

**背景**：RSS 订阅不稳定，直接爬取同花顺7x24小时要闻。

**数据源**：
- 列表接口：`http://stock.10jqka.com.cn/thsgd/realtimenews.js`
- 格式：JSONP + GBK 编码
- 返回：100 条最新新闻

**开发文件**：`scripts/ths_crawler_test.py`

**功能**：
| 功能 | 状态 |
|------|------|
| JSONP 解析（非标准 JSON） | ✅ |
| CDN 缓存绕过（时间戳参数） | ✅ |
| 增量新闻检测（seq 序号） | ✅ |
| 完整内容获取（详情页爬取） | ✅ |
| news 域名兼容（自动转换 stock） | ✅ |
| 集成到主项目 | ⏳ 待做 |
| 接入通知模块 | ⏳ 待做 |

**使用方法**：
```bash
# 安装依赖
pip install beautifulsoup4

# 运行测试（默认10分钟）
python scripts/ths_crawler_test.py

# 输出文件
output/ths_crawler_test_log_v2.txt   # 详细日志
output/ths_crawler_news_list.txt     # 完整消息列表
```

**技术要点**：
1. **缓存绕过**：URL 添加 `?v={timestamp}` + Cache-Control 头
2. **JSON 修复**：外层属性名无引号，用正则添加
3. **域名兼容**：`news.10jqka.com.cn` 是 Next.js SPA，需转换到 `stock.10jqka.com.cn`

**相关提交**：
- `94d7022` feat: 添加同花顺7x24小时要闻爬虫测试脚本
- `bae5fa8` refactor: 清理爬虫脚本，只保留可用版本
- `774e1b1` feat: 添加新闻完整内容获取功能
- `35068eb` fix: 优化 news 域名页面的内容获取
