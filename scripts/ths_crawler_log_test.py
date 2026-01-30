#!/usr/bin/env python3
"""
同花顺7x24小时要闻直播爬虫 - 详细日志测试
运行 10 分钟，30 秒间隔，输出详细日志到 txt 文件
"""

import requests
import json
import re
import time
from datetime import datetime
from typing import Optional
import pytz


class THSNewsCrawler:
    """同花顺实时新闻爬虫"""

    DATA_URL = "http://stock.10jqka.com.cn/thsgd/realtimenews.js"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://news.10jqka.com.cn/realtimenews.html",
        })
        self.seen_seqs: set[int] = set()
        self.latest_seq: Optional[int] = None
        self.tz = pytz.timezone('Asia/Shanghai')

    def get_cn_time(self) -> str:
        """获取中国时间字符串"""
        return datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')

    def fetch_raw_data(self) -> tuple[Optional[str], str]:
        """获取原始数据，返回 (数据, 状态信息)"""
        try:
            resp = self.session.get(self.DATA_URL, timeout=10)
            resp.encoding = 'gbk'
            return resp.text, f"HTTP {resp.status_code}, {len(resp.text)} bytes"
        except requests.exceptions.Timeout:
            return None, "请求超时"
        except requests.exceptions.ConnectionError as e:
            return None, f"连接错误: {e}"
        except Exception as e:
            return None, f"未知错误: {e}"

    def parse_jsonp(self, raw_data: str) -> tuple[Optional[dict], str]:
        """解析 JSONP 数据，返回 (数据, 状态信息)"""
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
            return data, f"解析成功, {item_count} 条新闻, 最新序号: {data.get('latestNewsSeq')}"
        except json.JSONDecodeError as e:
            return None, f"JSON 解析失败: {e}"

    def extract_news_item(self, item: dict) -> dict:
        """提取并处理单条新闻"""
        return {
            "seq": item.get("seq"),
            "title": item.get("title", "").strip(),
            "content": item.get("content", "").strip(),
            "url": item.get("url", ""),
            "pub_date": item.get("pubDate", ""),
            "source": item.get("source", ""),
            "stocks": item.get("stocks"),
            "stock_code": item.get("stockCode", ""),
            "category": item.get("category", ""),
            "implevel": item.get("implevel", ""),  # 重要程度
        }

    def get_all_news(self) -> tuple[list[dict], str, str]:
        """获取所有新闻，返回 (新闻列表, 获取状态, 解析状态)"""
        raw_data, fetch_status = self.fetch_raw_data()
        if not raw_data:
            return [], fetch_status, "未执行"

        data, parse_status = self.parse_jsonp(raw_data)
        if not data:
            return [], fetch_status, parse_status

        items = [self.extract_news_item(item) for item in data.get("item", [])]
        return items, fetch_status, parse_status

    def get_incremental_news(self) -> tuple[list[dict], list[dict], str, str]:
        """获取增量新闻，返回 (新增新闻, 全部新闻, 获取状态, 解析状态)"""
        all_items, fetch_status, parse_status = self.get_all_news()

        new_items = []
        for item in all_items:
            seq = item.get("seq")
            if seq and seq not in self.seen_seqs:
                self.seen_seqs.add(seq)
                new_items.append(item)

        return new_items, all_items, fetch_status, parse_status


def format_news_detail(item: dict) -> str:
    """格式化单条新闻的详细信息"""
    lines = []
    lines.append(f"    序号: {item['seq']}")
    lines.append(f"    标题: {item['title']}")
    lines.append(f"    发布时间: {item['pub_date']}")
    lines.append(f"    来源: {item['source']}")
    lines.append(f"    链接: {item['url']}")
    if item['stock_code']:
        lines.append(f"    相关股票: {item['stock_code']}")
    if item['implevel']:
        lines.append(f"    重要程度: {item['implevel']}")
    # 内容截取前 200 字符
    content = item['content']
    if len(content) > 200:
        content = content[:200] + "..."
    lines.append(f"    内容摘要: {content}")
    return "\n".join(lines)


def main():
    """主函数：运行 10 分钟的详细日志测试"""
    # 配置
    duration = 10 * 60  # 10 分钟
    interval = 30  # 30 秒间隔

    # 输出文件
    output_file = "/home/wufisher/ws/dev/TrendRadar/output/ths_crawler_test_log.txt"

    crawler = THSNewsCrawler()

    with open(output_file, 'w', encoding='utf-8') as f:
        def log(msg: str):
            """同时输出到文件和控制台"""
            print(msg, flush=True)
            f.write(msg + "\n")
            f.flush()

        log("=" * 80)
        log("同花顺 7x24 小时要闻直播 - 详细日志测试")
        log("=" * 80)
        log(f"开始时间: {crawler.get_cn_time()}")
        log(f"测试时长: {duration // 60} 分钟")
        log(f"检查间隔: {interval} 秒")
        log(f"数据源: {THSNewsCrawler.DATA_URL}")
        log(f"输出文件: {output_file}")
        log("=" * 80)
        log("")

        # ========== 首次获取（建立基线）==========
        log(f"[{crawler.get_cn_time()}] === 首次获取（建立基线）===")
        all_items, fetch_status, parse_status = crawler.get_all_news()
        log(f"  获取状态: {fetch_status}")
        log(f"  解析状态: {parse_status}")

        if all_items:
            log(f"  获取到 {len(all_items)} 条新闻")

            # 记录所有已见序号
            for item in all_items:
                if item.get("seq"):
                    crawler.seen_seqs.add(item["seq"])

            # 显示最新 5 条作为基线样本
            log("")
            log("  【基线样本 - 最新 5 条新闻】")
            log("-" * 60)
            for i, item in enumerate(all_items[:5], 1):
                log(f"  [{i}]")
                log(format_news_detail(item))
                log("-" * 60)

            # 显示序号范围
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

        # ========== 增量监控循环 ==========
        start_time = time.time()
        total_new_count = 0
        check_count = 0
        all_new_items = []  # 收集所有新增的新闻

        while time.time() - start_time < duration:
            time.sleep(interval)
            check_count += 1

            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed

            log(f"[{crawler.get_cn_time()}] === 第 {check_count} 次检查 (已运行 {elapsed}s, 剩余 {remaining}s) ===")

            new_items, all_items, fetch_status, parse_status = crawler.get_incremental_news()

            log(f"  获取状态: {fetch_status}")
            log(f"  解析状态: {parse_status}")
            log(f"  本次获取: {len(all_items)} 条, 其中新增: {len(new_items)} 条")
            log(f"  累计已知: {len(crawler.seen_seqs)} 条")

            if new_items:
                total_new_count += len(new_items)
                all_new_items.extend(new_items)
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

        # ========== 测试完成统计 ==========
        log("=" * 80)
        log("测试完成 - 统计摘要")
        log("=" * 80)
        log(f"结束时间: {crawler.get_cn_time()}")
        log(f"实际运行: {int(time.time() - start_time)} 秒")
        log(f"检查次数: {check_count} 次")
        log(f"新增消息: {total_new_count} 条")
        log(f"累计已知: {len(crawler.seen_seqs)} 条")
        log("")

        if all_new_items:
            log("【本次测试期间所有新增消息汇总】")
            log("-" * 60)
            for i, item in enumerate(all_new_items, 1):
                log(f"[{i}] [{item['pub_date']}] {item['title']}")
                log(f"    链接: {item['url']}")
                log(f"    序号: {item['seq']}")
            log("-" * 60)
        else:
            log("本次测试期间无新增消息")

        log("")
        log("=" * 80)
        log("日志结束")
        log("=" * 80)

    print(f"\n日志已保存到: {output_file}")


if __name__ == "__main__":
    main()
