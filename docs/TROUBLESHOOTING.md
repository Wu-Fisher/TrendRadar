# TrendRadar 问题解决方案清单

> 记录开发过程中遇到的问题及解决方案

---

## 1. 过滤标签全部显示"无匹配关键词"

### 问题描述
自定义爬虫数据在 HTML 报告中，所有条目的过滤标签都显示 `🚫 无匹配关键词`，即使爬虫层面已经正确过滤。

### 根本原因
**双重过滤问题**：数据经过两次过滤处理

1. **第一次过滤**（正确）：`CrawlerRunner.crawl_once()` 中的 `filter_news_items()`
   - 使用 `frequency_words.txt` 配置的关键词
   - 正确设置了 `filter_tag` 和 `filtered_out` 字段

2. **第二次过滤**（问题所在）：`_process_custom_data_by_mode()` 调用 `count_rss_frequency()`
   - 使用空的 `word_groups`（因为自定义爬虫没有配置）
   - 函数创建默认组 `{"required": [], "normal": [], "group_key": "全部 RSS"}`
   - 导致所有条目被视为"无匹配关键词"

### 数据流分析

```
CrawlerRunner.crawl_once()
    │
    ├── filter_news_items()
    │       ├── item.filter_tag = "✓ 地缘政治/能源"  ← 正确设置
    │       └── item.filtered_out = False
    │
    └── convert_to_rss_format()
            └── 保留 filter_tag 字段

_process_custom_data_by_mode()
    │
    └── count_rss_frequency(word_groups=[])  ← 问题！
            │
            ├── 创建默认组 {"group_key": "全部 RSS"}
            └── 所有条目被标记为"无匹配关键词"  ← 覆盖了原始标签
```

### 解决方案

**修改文件**: `trendradar/__main__.py:1488-1520`

```python
def _process_custom_data_by_mode(self, result: "CrawlResult") -> ...:
    # ...

    # 关键修改：自定义爬虫数据不使用 word_groups 过滤
    # 过滤已在爬虫层完成，这里只做展示
    word_groups = []
    filter_words = []
    global_filters = []

    stats, total_count = count_rss_frequency(
        items_to_process,
        word_groups=word_groups,      # 空列表
        filter_words=filter_words,    # 空列表
        global_filters=global_filters # 空列表
        # ...
    )
```

### 验证方法

```bash
# 测试过滤结果
python3 -c "
from trendradar.crawler.runner import CrawlerRunner
from trendradar.core.loader import load_config

config = load_config()
runner = CrawlerRunner(config)
result = runner.crawl_once()

passed = sum(1 for i in result.items if not i.get('filtered_out', True))
filtered = sum(1 for i in result.items if i.get('filtered_out', False))
print(f'通过: {passed}, 过滤: {filtered}')

for item in result.items[:5]:
    tag = item.get('filter_tag', 'N/A')
    print(f'  {tag}: {item[\"title\"][:30]}...')
"
```

---

## 2. 显示名称不正确

### 问题描述
HTML 报告中显示：
- 区域标题：`RSS 订阅更新` （应为 `自定义爬虫`）
- 分组名称：`全部 RSS` （应为 `同花顺快讯`）

### 解决方案

#### 2.1 区域标题自动检测

**修改文件**: `trendradar/report/html.py:1036-1048`

```python
def render_rss_stats_html(stats: List[Dict], title: str = "RSS 订阅更新") -> str:
    # 检测是否为自定义爬虫数据（有 filter_tag 字段）
    is_custom_crawler = False
    for stat in stats:
        for title_data in stat.get("titles", []):
            if title_data.get("filter_tag"):
                is_custom_crawler = True
                break
        if is_custom_crawler:
            break

    if is_custom_crawler:
        title = "自定义爬虫"  # 自动切换标题
```

#### 2.2 分组名称使用 feed_name

**修改文件**: `trendradar/__main__.py:1512`

```python
# 转换为 RSS 格式时设置 feed_name
"feed_name": item.get("source_name", "同花顺快讯"),
```

**修改文件**: `trendradar/core/analyzer.py:552-563`

```python
# count_rss_frequency() 中使用第一个条目的 feed_name 作为组名
default_group_name = "全部 RSS"
if rss_items:
    first_feed_name = rss_items[0].get("feed_name", "")
    if first_feed_name and first_feed_name != "RSS":
        default_group_name = first_feed_name  # 使用 "同花顺快讯"
```

---

## 3. Docker 权限问题

### 问题描述
运行 `docker ps` 报错：
```
permission denied while trying to connect to the Docker daemon socket
```

### 根本原因
用户已添加到 docker 组，但当前 shell 会话未生效。

### 解决方案

#### 方案一：新建 shell 会话
```bash
newgrp docker
docker ps  # 现在可以工作
```

#### 方案二：使用 sg 命令（推荐）
```bash
# 在当前会话中以 docker 组身份执行命令
sg docker -c "docker ps"
sg docker -c "docker compose up -d"
sg docker -c "docker logs trendradar"
```

#### 方案三：重新登录
```bash
# 完全注销并重新登录
exit
# 重新 SSH 或登录
```

### 验证
```bash
# 检查用户组
groups  # 应包含 docker

# 检查 docker 组是否激活
id  # 查看 gid 列表
```

---

## 4. 增量检测依赖热榜问题

### 问题描述
原有增量检测机制依赖热榜平台存在，当只启用自定义爬虫时无法正常工作。

### 解决方案

自定义爬虫使用独立的增量检测机制：

**文件**: `trendradar/crawler/custom/manager.py`

```python
class CrawlerManager:
    def __init__(self, ...):
        self.seen_items: Dict[str, Set[str]] = {}  # 按 source_id 分组

    def _detect_new_items(self, source_id: str, items: List) -> List:
        """基于 seq 序号的独立增量检测"""
        if source_id not in self.seen_items:
            self.seen_items[source_id] = set()

        new_items = []
        for item in items:
            seq = item.get("seq", "")
            if seq and seq not in self.seen_items[source_id]:
                self.seen_items[source_id].add(seq)
                new_items.append(item)

        return new_items
```

### 关键点
1. 每个数据源独立维护 `seen_items` 集合
2. 使用 `seq`（新闻序号）作为唯一标识
3. 首次运行时所有条目都是"新增"

---

## 5. JSONP 解析问题

### 问题描述
同花顺 API 返回非标准 JSON（JSONP 格式）：
```javascript
var defined_var = {
    summary:"...",
    data:[...]
}
```

### 问题点
1. 外层包裹 `var xxx = `
2. 属性名无引号（`summary:` 而非 `"summary":`）
3. 编码为 GBK

### 解决方案

**文件**: `trendradar/crawler/custom/ths.py`

```python
def _parse_jsonp(self, content: str) -> Dict:
    """解析非标准 JSONP"""
    # 1. 移除 var xxx =
    match = re.search(r"var\s+\w+\s*=\s*(\{.*\})", content, re.DOTALL)
    if not match:
        raise ParseError("无法提取 JSON 对象")

    json_str = match.group(1)

    # 2. 为无引号的属性名添加引号
    # summary: -> "summary":
    json_str = re.sub(r'(\w+):', r'"\1":', json_str)

    # 3. 解析 JSON
    return json.loads(json_str)
```

---

## 6. CDN 缓存问题

### 问题描述
多次请求同花顺 API 返回相同的旧数据。

### 原因
CDN 缓存了响应内容。

### 解决方案

```python
def fetch_news_list(self) -> CrawlResult:
    # 添加时间戳参数绕过缓存
    timestamp = int(time.time() * 1000)
    url = f"{self.api_url}?v={timestamp}"

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        # ...
    }

    response = requests.get(url, headers=headers)
```

---

## 7. news 域名页面无法获取内容

### 问题描述
部分新闻 URL 使用 `news.10jqka.com.cn` 域名，该页面是 Next.js SPA，无法直接爬取内容。

### 解决方案

自动转换为 `stock.10jqka.com.cn` 域名：

```python
def fetch_full_content(self, item: CrawlerNewsItem) -> Tuple[str, FetchStatus]:
    url = item.url

    # news 域名转换为 stock 域名
    if "news.10jqka.com.cn" in url:
        url = url.replace("news.10jqka.com.cn", "stock.10jqka.com.cn")

    # 继续获取内容...
```

---

## 8. 邮件发送失败

### 常见错误

#### 8.1 认证失败
```
SMTPAuthenticationError: (535, b'Error: authentication failed')
```

**解决**: 使用授权码而非密码
```yaml
# config/config.yaml
email:
  password: "xxxx"  # 163邮箱授权码，非登录密码
```

#### 8.2 连接超时
```
socket.timeout: timed out
```

**解决**: 检查网络/防火墙，或使用 SSL 端口
```yaml
email:
  smtp_server: "smtp.163.com"
  smtp_port: 465  # 使用 SSL 端口
  use_ssl: true
```

---

## 9. 常见配置错误

### 9.1 platforms.enabled: false 配置说明

**功能**: 设置 `enabled: false` 可禁用热榜平台抓取，同时保留 RSS 和自定义爬虫功能

**配置示例**:
```yaml
platforms:
  enabled: false                  # 禁用热榜
  sources:                        # 保留配置避免格式错误
    - id: "cls-hot"
      name: "财联社热门"
```

**运行效果**:
```
已启用数据源: RSS, 自定义爬虫
[热榜] 已禁用 (platforms.enabled: false)
```

### 9.2 CRON 执行间隔太短

**问题**: 任务未完成就开始下一次，日志报警告

**解决**: 间隔至少 2 分钟
```bash
# docker/.env
CRON_SCHEDULE=*/2 * * * *
```

---

## 10. 调试技巧

### 10.1 查看过滤详情
```bash
# 添加 DEBUG=true 环境变量
DEBUG=true python -m trendradar
```

### 10.2 单独测试爬虫
```bash
python3 scripts/test_crawler.py
```

### 10.3 检查数据库内容
```bash
sqlite3 output/news/crawler.db "SELECT title, filter_tag FROM news LIMIT 10;"
```

### 10.4 Docker 内调试
```bash
sg docker -c "docker exec -it trendradar python -c '
from trendradar.crawler.runner import CrawlerRunner
from trendradar.core.loader import load_config
config = load_config()
runner = CrawlerRunner(config)
result = runner.crawl_once()
print(f\"获取: {len(result.items)} 条, 新增: {result.new_count} 条\")
'"
```
