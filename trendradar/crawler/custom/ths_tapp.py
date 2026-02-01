# coding=utf-8
"""
同花顺 TAPP JSON API 爬虫

使用 https://news.10jqka.com.cn/tapp/news/push/stock/ 端点

优势：
- 原生 JSON 格式，无需 JSONP 解析
- UTF-8 编码，无需 GBK 转换
- 响应更新频率更高 (~15秒刷新)
- 结构化字段更丰富 (tags, stock, field, import)
"""

import time
import requests
from datetime import datetime
from typing import Optional, Tuple, Dict, List
import pytz

from .base import (
    BaseCrawler,
    CrawlerNewsItem,
    CrawlResult,
    FetchStatus,
)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class THSTappCrawler(BaseCrawler):
    """同花顺 TAPP JSON API 爬虫

    使用原生 JSON API，比 JSONP 更稳定可靠。
    """

    BASE_URL = "https://news.10jqka.com.cn/tapp/news/push/stock/"
    SOURCE_ID = "ths-realtime"
    SOURCE_NAME = "同花顺7x24"

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(self.get_request_headers())
        self.tz = pytz.timezone(config.get("timezone", "Asia/Shanghai") if config else "Asia/Shanghai")
        self.timeout = config.get("timeout", 10) if config else 10
        self.content_fetch_delay = config.get("content_fetch_delay", 0.3) if config else 0.3
        self.page_size = config.get("page_size", 100) if config else 100

    def get_source_id(self) -> str:
        return self.SOURCE_ID

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_request_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://news.10jqka.com.cn/7x24/",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
        }

    def fetch_news_list(self) -> CrawlResult:
        """获取新闻列表"""
        try:
            params = {
                "page_size": self.page_size,
                "track": "website",
                "sub_tag": "7x24",
            }

            resp = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )

            if resp.status_code != 200:
                return CrawlResult(
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    items=[],
                    status=FetchStatus.NETWORK_ERROR,
                    error_message=f"HTTP {resp.status_code}",
                )

            data = resp.json()

            if data.get("code") != "200":
                return CrawlResult(
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    items=[],
                    status=FetchStatus.PARSE_ERROR,
                    error_message=f"API 错误: {data.get('msg', 'unknown')}",
                )

            # 提取新闻条目
            items = self._extract_news_items(data)
            api_time = data.get("time", "")

            return CrawlResult(
                source_id=self.SOURCE_ID,
                source_name=self.SOURCE_NAME,
                items=items,
                status=FetchStatus.SUCCESS,
                data_time=api_time,
                total_count=len(items),
            )

        except requests.exceptions.Timeout:
            return CrawlResult(
                source_id=self.SOURCE_ID,
                source_name=self.SOURCE_NAME,
                items=[],
                status=FetchStatus.TIMEOUT,
                error_message="请求超时",
            )
        except requests.exceptions.ConnectionError as e:
            return CrawlResult(
                source_id=self.SOURCE_ID,
                source_name=self.SOURCE_NAME,
                items=[],
                status=FetchStatus.NETWORK_ERROR,
                error_message=f"连接错误: {str(e)[:100]}",
            )
        except Exception as e:
            return CrawlResult(
                source_id=self.SOURCE_ID,
                source_name=self.SOURCE_NAME,
                items=[],
                status=FetchStatus.UNKNOWN_ERROR,
                error_message=f"未知错误: {str(e)[:100]}",
            )

    def _extract_news_items(self, data: Dict) -> List[CrawlerNewsItem]:
        """从 API 响应提取新闻条目"""
        items = []
        news_list = data.get("data", {}).get("list", [])

        for item in news_list:
            seq = item.get("seq")
            if not seq:
                continue

            # 转换时间戳
            ctime = item.get("ctime", 0)
            published_at = ""
            if ctime:
                try:
                    dt = datetime.fromtimestamp(int(ctime), tz=self.tz)
                    published_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    published_at = ""

            # 提取扩展信息
            extra = {}

            # 股票信息
            stocks = item.get("stock", [])
            if stocks:
                extra["stocks"] = [
                    {"name": s.get("name"), "code": s.get("stockCode"), "market": s.get("stockMarket")}
                    for s in stocks
                ]

            # 板块信息
            fields = item.get("field", [])
            if fields:
                extra["fields"] = [
                    {"name": f.get("name"), "code": f.get("stockCode")}
                    for f in fields
                ]

            # 标签
            tags = item.get("tags", [])
            if tags:
                extra["tags"] = [t.get("name") for t in tags]

            # 重要性等级 (0-3)
            importance = item.get("import", 0)
            try:
                importance = int(importance) if importance else 0
            except (ValueError, TypeError):
                importance = 0
            if importance:
                extra["importance"] = importance

            # 颜色标记 (1=普通, 2=重要)
            color = item.get("color", 1)
            try:
                color = int(color) if color else 1
            except (ValueError, TypeError):
                color = 1
            if color > 1:
                extra["highlight"] = True

            # 保存原始 ctime 用于排序
            extra["_ctime"] = int(ctime) if ctime else 0

            news_item = CrawlerNewsItem(
                seq=str(seq),
                title=item.get("title", "").strip(),
                summary=item.get("digest", item.get("short", "")).strip(),
                url=item.get("url", ""),
                published_at=published_at,
                source=item.get("source", "") or "同花顺",
                extra=extra,
            )
            items.append(news_item)

        # 按时间降序排序（最新的在前面）
        items.sort(key=lambda x: x.extra.get("_ctime", 0), reverse=True)

        return items

    def fetch_full_content(self, item: CrawlerNewsItem) -> Tuple[str, FetchStatus]:
        """获取新闻完整内容"""
        if not HAS_BS4:
            return "", FetchStatus.UNKNOWN_ERROR

        if not item.url:
            return "", FetchStatus.EMPTY_RESULT

        # 尝试的 URL 列表
        urls_to_try = [item.url]

        # 如果是 news.10jqka.com.cn 域名，尝试转换为 stock.10jqka.com.cn
        if 'news.10jqka.com.cn' in item.url:
            alt_url = item.url.replace('news.10jqka.com.cn', 'stock.10jqka.com.cn')
            urls_to_try.append(alt_url)

        for try_url in urls_to_try:
            content, status = self._fetch_content_from_url(try_url)
            if status == FetchStatus.SUCCESS and content:
                return content, status

        return "", FetchStatus.EMPTY_RESULT

    def _fetch_content_from_url(self, url: str) -> Tuple[str, FetchStatus]:
        """从指定 URL 获取内容"""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.encoding = 'utf-8'

            # 尝试检测编码
            if 'charset=gbk' in resp.text.lower() or 'charset=gb2312' in resp.text.lower():
                resp.encoding = 'gbk'

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 找正文容器
            content_div = soup.find('div', class_='main-text')
            if not content_div:
                content_div = soup.find('div', class_='atc-content')

            if not content_div:
                return "", FetchStatus.PARSE_ERROR

            # 移除脚本和样式
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()

            # 提取段落文本
            paragraphs = content_div.find_all('p')
            if paragraphs:
                texts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and not text.startswith('关注同花顺财经') and len(text) > 5:
                        texts.append(text)

                if texts:
                    seen = set()
                    unique_texts = []
                    for t in texts:
                        if t not in seen:
                            seen.add(t)
                            unique_texts.append(t)
                    return '\n'.join(unique_texts), FetchStatus.SUCCESS

            # 如果没有段落，直接提取文本
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                return text, FetchStatus.SUCCESS

            return "", FetchStatus.EMPTY_RESULT

        except requests.exceptions.Timeout:
            return "", FetchStatus.TIMEOUT
        except requests.exceptions.ConnectionError:
            return "", FetchStatus.NETWORK_ERROR
        except Exception:
            return "", FetchStatus.UNKNOWN_ERROR

    def fetch_full_content_batch(
        self,
        items: List[CrawlerNewsItem],
        delay: float = None,
        callback=None
    ) -> Dict[str, Tuple[str, FetchStatus]]:
        """批量获取完整内容"""
        if not HAS_BS4:
            return {item.seq: ("", FetchStatus.UNKNOWN_ERROR) for item in items}

        delay = delay or self.content_fetch_delay
        results = {}

        for i, item in enumerate(items):
            if item.content_fetched:
                results[item.seq] = (item.full_content, FetchStatus.SUCCESS)
                continue

            if not item.url:
                results[item.seq] = ("", FetchStatus.EMPTY_RESULT)
                continue

            content, status = self.fetch_full_content(item)
            results[item.seq] = (content, status)

            # 更新 item
            item.full_content = content
            item.content_fetched = status == FetchStatus.SUCCESS
            item.content_fetch_time = datetime.now().isoformat()
            if status != FetchStatus.SUCCESS:
                item.content_fetch_error = status.value

            # 回调
            if callback:
                callback(item, content, status)

            # 延迟
            if i < len(items) - 1 and delay > 0:
                time.sleep(delay)

        return results

    def cleanup(self) -> None:
        """清理资源"""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None
