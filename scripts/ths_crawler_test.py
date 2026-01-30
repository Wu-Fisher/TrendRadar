#!/usr/bin/env python3
"""
同花顺7x24小时要闻直播爬虫 - 改进版详细日志测试
修复：添加缓存绕过机制
功能：获取新闻列表 + 抓取每条新闻的完整内容
输出：详细日志 + 完整消息列表（用于与原网页对比）
"""

import requests
import json
import re
import time
from datetime import datetime
from typing import Optional
import pytz

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("警告: 未安装 beautifulsoup4，无法获取新闻完整内容")
    print("安装命令: pip install beautifulsoup4")


class THSNewsCrawler:
    """同花顺实时新闻爬虫（带缓存绕过）"""

    BASE_URL = "http://stock.10jqka.com.cn/thsgd/realtimenews.js"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://news.10jqka.com.cn/realtimenews.html",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })
        self.seen_seqs: set[int] = set()
        self.all_news: dict[int, dict] = {}  # seq -> news item，收集所有新闻
        self.tz = pytz.timezone('Asia/Shanghai')

    def get_cn_time(self) -> str:
        """获取中国时间字符串"""
        return datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')

    def fetch_raw_data(self) -> tuple[Optional[str], str]:
        """获取原始数据（带缓存绕过）"""
        try:
            # 添加时间戳参数绕过缓存
            url = f"{self.BASE_URL}?v={int(time.time() * 1000)}"
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'
            return resp.text, f"HTTP {resp.status_code}, {len(resp.text)} bytes"
        except requests.exceptions.Timeout:
            return None, "请求超时"
        except requests.exceptions.ConnectionError as e:
            return None, f"连接错误: {e}"
        except Exception as e:
            return None, f"未知错误: {e}"

    def fetch_full_content(self, url: str) -> tuple[Optional[str], str]:
        """获取新闻详情页的完整内容"""
        if not HAS_BS4:
            return None, "未安装 beautifulsoup4"

        if not url:
            return None, "URL 为空"

        # 尝试的 URL 列表（原始 URL + 可能的备选 URL）
        urls_to_try = [url]

        # 如果是 news.10jqka.com.cn 域名（Next.js SPA，无法直接解析）
        # 尝试转换为 stock.10jqka.com.cn
        if 'news.10jqka.com.cn' in url:
            alt_url = url.replace('news.10jqka.com.cn', 'stock.10jqka.com.cn')
            urls_to_try.append(alt_url)

        last_error = ""
        for try_url in urls_to_try:
            content, status = self._fetch_content_from_url(try_url)
            if content:
                return content, status
            last_error = status

        return None, last_error

    def _fetch_content_from_url(self, url: str) -> tuple[Optional[str], str]:
        """从指定 URL 获取内容的内部方法"""
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 找正文容器 (class="main-text" 或 class="atc-content")
            content_div = soup.find('div', class_='main-text')
            if not content_div:
                content_div = soup.find('div', class_='atc-content')

            if not content_div:
                return None, "未找到正文容器"

            # 移除脚本和样式标签
            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()

            # 提取所有 p 标签的文本
            paragraphs = content_div.find_all('p')
            if paragraphs:
                # 过滤掉广告和无关内容
                texts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    # 跳过常见的广告/无关文本
                    if text and not text.startswith('关注同花顺财经') and len(text) > 5:
                        texts.append(text)
                if texts:
                    # 去重（有时内容会重复）
                    seen = set()
                    unique_texts = []
                    for t in texts:
                        if t not in seen:
                            seen.add(t)
                            unique_texts.append(t)
                    full_text = '\n'.join(unique_texts)
                    return full_text, "成功"

            # 如果没有 p 标签，直接提取文本
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                return text, "成功(直接提取)"

            return None, "正文为空"

        except requests.exceptions.Timeout:
            return None, "请求超时"
        except requests.exceptions.ConnectionError as e:
            return None, f"连接错误"
        except Exception as e:
            return None, f"错误: {e}"

    def parse_jsonp(self, raw_data: str) -> tuple[Optional[dict], str]:
        """解析 JSONP 数据"""
        try:
            json_str = raw_data.strip()

            start = json_str.find('{')
            if start == -1:
                return None, "无法找到 JSON 起始位置"

            end = json_str.rfind('};')
            if end != -1:
                json_str = json_str[start:end+1]
            else:
                end = json_str.rfind('}')
                if end != -1:
                    json_str = json_str[start:end+1]
                else:
                    json_str = json_str[start:]

            # 给外层属性名加双引号
            json_str = re.sub(r'(\{)\s*(pubDate):', r'\1"\2":', json_str)
            json_str = re.sub(r',\s*(latestNewsSeq):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(counter):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(item):', r',"\1":', json_str)

            data = json.loads(json_str)
            item_count = len(data.get("item", []))
            return data, f"解析成功, {item_count} 条, 数据时间: {data.get('pubDate')}, 最新序号: {data.get('latestNewsSeq')}"
        except json.JSONDecodeError as e:
            return None, f"JSON 解析失败: {e}"

    def extract_news_item(self, item: dict) -> dict:
        """提取并处理单条新闻"""
        return {
            "seq": item.get("seq"),
            "title": item.get("title", "").strip(),
            "content": item.get("content", "").strip(),  # 摘要
            "full_content": "",  # 完整内容（需要单独获取）
            "url": item.get("url", ""),
            "pub_date": item.get("pubDate", ""),
            "source": item.get("source", ""),
            "stocks": item.get("stocks"),
            "stock_code": item.get("stockCode", ""),
            "category": item.get("category", ""),
            "implevel": item.get("implevel", ""),
        }

    def get_incremental_news(self) -> tuple[list[dict], list[dict], str, str, str]:
        """获取增量新闻
        返回: (新增新闻, 全部新闻, 获取状态, 解析状态, 数据发布时间)
        """
        raw_data, fetch_status = self.fetch_raw_data()
        if not raw_data:
            return [], [], fetch_status, "未执行", ""

        data, parse_status = self.parse_jsonp(raw_data)
        if not data:
            return [], [], fetch_status, parse_status, ""

        data_pub_time = data.get("pubDate", "")
        all_items = [self.extract_news_item(item) for item in data.get("item", [])]

        new_items = []
        for item in all_items:
            seq = item.get("seq")
            if seq:
                # 收集到总库
                if seq not in self.all_news:
                    self.all_news[seq] = item

                # 检查是否新增
                if seq not in self.seen_seqs:
                    self.seen_seqs.add(seq)
                    new_items.append(item)

        return new_items, all_items, fetch_status, parse_status, data_pub_time

    def fetch_all_full_contents(self, delay: float = 0.3, log_func=None) -> dict:
        """批量获取所有新闻的完整内容

        Args:
            delay: 每次请求之间的延迟（秒），避免请求过快
            log_func: 日志输出函数，可选

        Returns:
            统计信息 {"success": 成功数, "failed": 失败数, "skipped": 跳过数}
        """
        if not HAS_BS4:
            if log_func:
                log_func("  ⚠️ 未安装 beautifulsoup4，跳过获取完整内容")
            return {"success": 0, "failed": 0, "skipped": len(self.all_news)}

        stats = {"success": 0, "failed": 0, "skipped": 0}
        total = len(self.all_news)

        for i, (seq, item) in enumerate(self.all_news.items(), 1):
            # 如果已经有完整内容，跳过
            if item.get("full_content"):
                stats["skipped"] += 1
                continue

            url = item.get("url", "")
            if not url:
                stats["skipped"] += 1
                continue

            if log_func:
                log_func(f"  [{i}/{total}] 获取 seq={seq} ...", end="")

            full_content, status = self.fetch_full_content(url)

            if full_content:
                item["full_content"] = full_content
                stats["success"] += 1
                if log_func:
                    log_func(f" ✓ ({len(full_content)}字)")
            else:
                stats["failed"] += 1
                if log_func:
                    log_func(f" ✗ ({status})")

            # 延迟，避免请求过快
            if i < total:
                time.sleep(delay)

        return stats


def format_news_detail(item: dict, indent: str = "    ") -> str:
    """格式化单条新闻的详细信息"""
    lines = []
    lines.append(f"{indent}序号: {item['seq']}")
    lines.append(f"{indent}标题: {item['title']}")
    lines.append(f"{indent}发布时间: {item['pub_date']}")
    lines.append(f"{indent}来源: {item['source']}")
    lines.append(f"{indent}链接: {item['url']}")
    if item['stock_code']:
        lines.append(f"{indent}相关股票: {item['stock_code']}")
    if item['implevel']:
        lines.append(f"{indent}重要程度: {item['implevel']}")
    content = item['content']
    if len(content) > 200:
        content = content[:200] + "..."
    lines.append(f"{indent}内容摘要: {content}")
    return "\n".join(lines)


def format_news_simple(item: dict) -> str:
    """格式化单条新闻的简洁信息（用于对比列表）"""
    stock_info = f" [股票:{item['stock_code']}]" if item['stock_code'] else ""
    return f"[{item['pub_date']}] seq={item['seq']}{stock_info} {item['title']}\n  链接: {item['url']}"


def main():
    """主函数"""
    # 配置
    duration = 10 * 60  # 10 分钟
    interval = 30  # 30 秒间隔

    # 输出文件
    log_file = "/home/wufisher/ws/dev/TrendRadar/output/ths_crawler_test_log_v2.txt"
    news_list_file = "/home/wufisher/ws/dev/TrendRadar/output/ths_crawler_news_list.txt"

    crawler = THSNewsCrawler()

    with open(log_file, 'w', encoding='utf-8') as f:
        def log(msg: str):
            print(msg, flush=True)
            f.write(msg + "\n")
            f.flush()

        log("=" * 80)
        log("同花顺 7x24 小时要闻直播 - 改进版详细日志测试")
        log("=" * 80)
        log(f"开始时间: {crawler.get_cn_time()}")
        log(f"测试时长: {duration // 60} 分钟")
        log(f"检查间隔: {interval} 秒")
        log(f"数据源: {THSNewsCrawler.BASE_URL}")
        log(f"日志文件: {log_file}")
        log(f"消息列表: {news_list_file}")
        log("改进: 添加缓存绕过（时间戳参数 + Cache-Control 头）")
        log("=" * 80)
        log("")

        # ========== 首次获取 ==========
        log(f"[{crawler.get_cn_time()}] === 首次获取（建立基线）===")
        new_items, all_items, fetch_status, parse_status, data_time = crawler.get_incremental_news()
        log(f"  获取状态: {fetch_status}")
        log(f"  解析状态: {parse_status}")

        if all_items:
            log(f"  获取到 {len(all_items)} 条新闻（全部标记为已知）")

            # 显示最新 5 条
            log("")
            log("  【基线样本 - 最新 5 条新闻】")
            log("-" * 60)
            for i, item in enumerate(all_items[:5], 1):
                log(f"  [{i}]")
                log(format_news_detail(item))
                log("-" * 60)

            seqs = [item['seq'] for item in all_items if item.get('seq')]
            if seqs:
                log(f"  序号范围: {min(seqs)} ~ {max(seqs)}")
        else:
            log("  ✗ 首次获取失败")

        log("")
        log(f"基线建立完成，已记录 {len(crawler.seen_seqs)} 条新闻")
        log("")
        log("=" * 80)
        log("开始增量监控...")
        log("=" * 80)
        log("")

        # ========== 增量监控 ==========
        start_time = time.time()
        total_new_count = 0
        check_count = 0
        incremental_news = []  # 测试期间新增的消息

        while time.time() - start_time < duration:
            time.sleep(interval)
            check_count += 1

            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed

            log(f"[{crawler.get_cn_time()}] === 第 {check_count} 次检查 (已运行 {elapsed}s, 剩余 {remaining}s) ===")

            new_items, all_items, fetch_status, parse_status, data_time = crawler.get_incremental_news()

            log(f"  获取状态: {fetch_status}")
            log(f"  解析状态: {parse_status}")
            log(f"  本次获取: {len(all_items)} 条, 新增: {len(new_items)} 条")
            log(f"  累计已知: {len(crawler.seen_seqs)} 条, 总库: {len(crawler.all_news)} 条")

            if new_items:
                total_new_count += len(new_items)
                incremental_news.extend(new_items)
                log("")
                log(f"  🆕 【发现 {len(new_items)} 条新消息】")
                log("-" * 60)
                for i, item in enumerate(new_items, 1):
                    log(f"  [新增 {i}]")
                    log(format_news_detail(item))
                    log("-" * 60)
            else:
                log("  无新消息")

            log("")

        # ========== 统计 ==========
        log("=" * 80)
        log("测试完成 - 统计摘要")
        log("=" * 80)
        log(f"结束时间: {crawler.get_cn_time()}")
        log(f"实际运行: {int(time.time() - start_time)} 秒")
        log(f"检查次数: {check_count} 次")
        log(f"新增消息: {total_new_count} 条")
        log(f"总收集: {len(crawler.all_news)} 条不重复新闻")
        log("")

        if incremental_news:
            log("【测试期间新增消息汇总】")
            log("-" * 60)
            for i, item in enumerate(incremental_news, 1):
                log(f"[{i}] {format_news_simple(item)}")
            log("-" * 60)
        else:
            log("测试期间无新增消息")

        log("")

        # ========== 获取完整内容 ==========
        log("=" * 80)
        log("开始获取新闻完整内容...")
        log("=" * 80)

        def log_inline(msg: str, end: str = "\n"):
            """支持不换行的日志"""
            print(msg, end=end, flush=True)
            f.write(msg + end)
            f.flush()

        stats = crawler.fetch_all_full_contents(delay=0.3, log_func=log_inline)
        log("")
        log(f"获取完成: 成功 {stats['success']} 条, 失败 {stats['failed']} 条, 跳过 {stats['skipped']} 条")

        log("")
        log("=" * 80)
        log(f"完整消息列表已输出到: {news_list_file}")
        log("=" * 80)

    # ========== 输出完整消息列表（用于与原网页对比）==========
    with open(news_list_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("同花顺 7x24 小时要闻 - 完整消息列表（用于与原网页对比）\n")
        f.write("=" * 80 + "\n")
        f.write(f"导出时间: {crawler.get_cn_time()}\n")
        f.write(f"总条数: {len(crawler.all_news)} 条\n")
        f.write("排序: 按序号从大到小（最新在前）\n")
        f.write("=" * 80 + "\n\n")

        # 按序号排序（从大到小 = 最新在前）
        sorted_news = sorted(crawler.all_news.values(), key=lambda x: x.get('seq', 0), reverse=True)

        for i, item in enumerate(sorted_news, 1):
            f.write(f"[{i:03d}] ----------------------------------------\n")
            f.write(f"序号: {item['seq']}\n")
            f.write(f"时间: {item['pub_date']}\n")
            f.write(f"标题: {item['title']}\n")
            f.write(f"链接: {item['url']}\n")
            if item['stock_code']:
                f.write(f"股票: {item['stock_code']}\n")
            if item['implevel']:
                f.write(f"重要: {item['implevel']}\n")
            # 优先使用完整内容，如果没有则使用摘要
            content = item.get('full_content') or item.get('content', '')
            f.write(f"内容: {content}\n")
            f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("列表结束\n")
        f.write("=" * 80 + "\n")

    print(f"\n日志已保存到: {log_file}")
    print(f"消息列表已保存到: {news_list_file}")


if __name__ == "__main__":
    main()
