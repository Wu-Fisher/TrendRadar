# coding=utf-8
"""
同花顺7x24小时要闻爬虫

基于测试脚本优化的生产级实现。
"""

import json
import re
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
    NetworkError,
    ParseError,
    ContentFetchError,
)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class THSCrawler(BaseCrawler):
    """同花顺7x24小时实时新闻爬虫

    数据源: http://stock.10jqka.com.cn/thsgd/realtimenews.js
    """

    BASE_URL = "http://stock.10jqka.com.cn/thsgd/realtimenews.js"
    SOURCE_ID = "ths-realtime"
    SOURCE_NAME = "同花顺7x24"

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(self.get_request_headers())
        self.tz = pytz.timezone(config.get("timezone", "Asia/Shanghai") if config else "Asia/Shanghai")
        self.timeout = config.get("timeout", 10) if config else 10
        self.content_fetch_delay = config.get("content_fetch_delay", 0.3) if config else 0.3

    def get_source_id(self) -> str:
        return self.SOURCE_ID

    def get_source_name(self) -> str:
        return self.SOURCE_NAME

    def get_request_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://news.10jqka.com.cn/realtimenews.html",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

    def fetch_news_list(self) -> CrawlResult:
        """获取新闻列表"""
        try:
            # 带缓存绕过的请求
            url = f"{self.BASE_URL}?v={int(time.time() * 1000)}"
            resp = self.session.get(url, timeout=self.timeout)
            resp.encoding = 'gbk'

            if resp.status_code != 200:
                return CrawlResult(
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    items=[],
                    status=FetchStatus.NETWORK_ERROR,
                    error_message=f"HTTP {resp.status_code}",
                )

            # 解析 JSONP 数据
            data, parse_status, error_msg = self._parse_jsonp(resp.text)
            if parse_status != FetchStatus.SUCCESS:
                return CrawlResult(
                    source_id=self.SOURCE_ID,
                    source_name=self.SOURCE_NAME,
                    items=[],
                    status=parse_status,
                    error_message=error_msg,
                )

            # 提取新闻条目
            items = self._extract_news_items(data)
            data_time = data.get("pubDate", "")

            return CrawlResult(
                source_id=self.SOURCE_ID,
                source_name=self.SOURCE_NAME,
                items=items,
                status=FetchStatus.SUCCESS,
                data_time=data_time,
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

    def _parse_jsonp(self, raw_data: str) -> Tuple[Optional[Dict], FetchStatus, str]:
        """解析 JSONP 数据

        Returns:
            (解析后的数据, 状态, 错误信息)
        """
        try:
            json_str = raw_data.strip()

            # 找到 JSON 起始位置
            start = json_str.find('{')
            if start == -1:
                return None, FetchStatus.PARSE_ERROR, "无法找到 JSON 起始位置"

            # 找到 JSON 结束位置
            end = json_str.rfind('};')
            if end != -1:
                json_str = json_str[start:end+1]
            else:
                end = json_str.rfind('}')
                if end != -1:
                    json_str = json_str[start:end+1]
                else:
                    json_str = json_str[start:]

            # 修复 JSONP 格式：给属性名加双引号
            json_str = re.sub(r'(\{)\s*(pubDate):', r'\1"\2":', json_str)
            json_str = re.sub(r',\s*(latestNewsSeq):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(counter):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(item):', r',"\1":', json_str)

            data = json.loads(json_str)
            return data, FetchStatus.SUCCESS, ""

        except json.JSONDecodeError as e:
            return None, FetchStatus.PARSE_ERROR, f"JSON 解析失败: {str(e)[:100]}"
        except Exception as e:
            return None, FetchStatus.PARSE_ERROR, f"解析错误: {str(e)[:100]}"

    def _extract_news_items(self, data: Dict) -> List[CrawlerNewsItem]:
        """从解析的数据中提取新闻条目"""
        items = []
        for item in data.get("item", []):
            seq = item.get("seq")
            if not seq:
                continue

            # 提取扩展信息
            extra = {}
            if item.get("stockCode"):
                extra["stock_code"] = item.get("stockCode")
            if item.get("stocks"):
                extra["stocks"] = item.get("stocks")
            if item.get("category"):
                extra["category"] = item.get("category")
            if item.get("implevel"):
                extra["importance_level"] = item.get("implevel")

            news_item = CrawlerNewsItem(
                seq=str(seq),
                title=item.get("title", "").strip(),
                summary=item.get("content", "").strip(),  # 原始 content 作为摘要
                url=item.get("url", ""),
                published_at=item.get("pubDate", ""),
                source=item.get("source", "同花顺"),
                extra=extra,
            )
            items.append(news_item)

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

        last_error = ""
        for try_url in urls_to_try:
            content, status = self._fetch_content_from_url(try_url)
            if status == FetchStatus.SUCCESS and content:
                return content, status
            last_error = f"URL: {try_url}"

        return "", FetchStatus.EMPTY_RESULT

    def _fetch_content_from_url(self, url: str) -> Tuple[str, FetchStatus]:
        """从指定 URL 获取内容"""
        try:
            resp = self.session.get(url, timeout=self.timeout)
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
                    # 过滤广告和无关内容
                    if text and not text.startswith('关注同花顺财经') and len(text) > 5:
                        texts.append(text)

                if texts:
                    # 去重
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
        except Exception as e:
            return "", FetchStatus.UNKNOWN_ERROR

    def fetch_full_content_batch(
        self,
        items: List[CrawlerNewsItem],
        delay: float = None,
        callback=None
    ) -> Dict[str, Tuple[str, FetchStatus]]:
        """批量获取完整内容

        Args:
            items: 新闻条目列表
            delay: 请求间隔（秒）
            callback: 每获取一条后的回调函数，接收 (item, content, status) 参数

        Returns:
            {seq: (content, status)} 字典
        """
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
