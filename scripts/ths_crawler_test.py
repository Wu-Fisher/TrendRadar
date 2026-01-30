#!/usr/bin/env python3
"""
同花顺7x24小时要闻直播爬虫测试脚本

数据源: http://stock.10jqka.com.cn/thsgd/realtimenews.js
功能: 每隔一定时间抓取新闻，检测并输出增量消息
"""

import requests
import json
import re
import time
from datetime import datetime
from typing import Optional


class THSNewsCrawler:
    """同花顺实时新闻爬虫"""

    DATA_URL = "http://stock.10jqka.com.cn/thsgd/realtimenews.js"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://news.10jqka.com.cn/realtimenews.html",
        })
        # 已见过的新闻序号集合
        self.seen_seqs: set[int] = set()
        # 最新的新闻序号
        self.latest_seq: Optional[int] = None

    def fetch_raw_data(self) -> Optional[str]:
        """获取原始 JS 数据"""
        try:
            resp = self.session.get(self.DATA_URL, timeout=10)
            resp.encoding = 'gbk'  # 同花顺使用 GBK 编码
            return resp.text
        except Exception as e:
            print(f"[ERROR] 获取数据失败: {e}")
            return None

    def parse_jsonp(self, raw_data: str) -> Optional[dict]:
        """解析 JSONP 数据 (var thsRss = {...})"""
        try:
            # 去掉 var thsRss = 前缀
            json_str = raw_data.strip()

            # 找到 JSON 对象的起始位置
            start = json_str.find('{')
            if start == -1:
                print("[ERROR] 无法找到 JSON 起始位置")
                return None

            # 找到 JSON 对象的结束位置 (最后一个 }; 或 }])
            # 尾部可能有 JSONP 回调: if ( typeof(ths_rss_news_callback) ...
            end = json_str.rfind('};')
            if end != -1:
                json_str = json_str[start:end+1]
            else:
                # 备选：找最后一个 }
                end = json_str.rfind('}')
                if end != -1:
                    json_str = json_str[start:end+1]
                else:
                    json_str = json_str[start:]

            # 外层属性名没有双引号，需要添加
            # pubDate, latestNewsSeq, counter, item 这些外层key需要加引号
            json_str = re.sub(r'(\{)\s*(pubDate):', r'\1"\2":', json_str)
            json_str = re.sub(r',\s*(latestNewsSeq):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(counter):', r',"\1":', json_str)
            json_str = re.sub(r',\s*(item):', r',"\1":', json_str)

            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 解析失败: {e}")
            # 显示出错位置附近的内容
            if e.pos:
                print(f"[DEBUG] 出错位置附近内容: ...{json_str[max(0, e.pos-50):e.pos+50]}...")
            return None

    def extract_news_items(self, data: dict) -> list[dict]:
        """提取新闻条目"""
        items = data.get("item", [])
        result = []
        for item in items:
            result.append({
                "seq": item.get("seq"),
                "title": item.get("title", "").strip(),
                "content": item.get("content", "").strip(),
                "url": item.get("url", ""),
                "pub_date": item.get("pubDate", ""),
                "source": item.get("source", ""),
                "stocks": item.get("stocks"),
                "stock_code": item.get("stockCode", ""),
            })
        return result

    def get_incremental_news(self) -> list[dict]:
        """获取增量新闻（只返回新出现的）"""
        raw_data = self.fetch_raw_data()
        if not raw_data:
            return []

        data = self.parse_jsonp(raw_data)
        if not data:
            return []

        all_items = self.extract_news_items(data)
        new_items = []

        for item in all_items:
            seq = item.get("seq")
            if seq and seq not in self.seen_seqs:
                self.seen_seqs.add(seq)
                new_items.append(item)

        # 更新最新序号
        if data.get("latestNewsSeq"):
            self.latest_seq = int(data["latestNewsSeq"])

        return new_items

    def format_news(self, item: dict) -> str:
        """格式化单条新闻输出"""
        lines = []
        lines.append(f"📰 {item['title']}")
        if item['content']:
            # 截取内容摘要
            content = item['content'][:200] + "..." if len(item['content']) > 200 else item['content']
            lines.append(f"   {content}")
        lines.append(f"   🔗 {item['url']}")
        lines.append(f"   ⏰ {item['pub_date']} | 来源: {item['source']}")
        if item['stock_code']:
            lines.append(f"   📊 相关股票: {item['stock_code']}")
        return "\n".join(lines)


def main():
    """主函数：运行 5 分钟的增量监控测试"""
    print("=" * 60)
    print("同花顺 7x24 小时要闻直播 - 增量爬虫测试")
    print("=" * 60)
    print(f"数据源: {THSNewsCrawler.DATA_URL}")
    print(f"测试时长: 5 分钟")
    print(f"检查间隔: 10 秒")
    print("=" * 60)

    crawler = THSNewsCrawler()

    # 第一次获取，建立基线
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 首次获取数据，建立基线...")
    raw_data = crawler.fetch_raw_data()
    if raw_data:
        data = crawler.parse_jsonp(raw_data)
        if data:
            items = crawler.extract_news_items(data)
            print(f"  ✓ 获取到 {len(items)} 条新闻")
            print(f"  ✓ 最新序号: {data.get('latestNewsSeq')}")
            print(f"  ✓ 发布时间: {data.get('pubDate')}")

            # 将所有已有新闻标记为已见
            for item in items:
                if item.get("seq"):
                    crawler.seen_seqs.add(item["seq"])

            # 显示最新 3 条作为样例
            print("\n  最新 3 条新闻样例:")
            print("-" * 50)
            for item in items[:3]:
                print(crawler.format_news(item))
                print("-" * 50)

    print(f"\n基线建立完成，已记录 {len(crawler.seen_seqs)} 条新闻")
    print("开始增量监控...\n")

    # 增量监控循环
    start_time = time.time()
    duration = 5 * 60  # 5 分钟
    interval = 10  # 10 秒检查一次
    new_count = 0
    check_count = 0

    try:
        while time.time() - start_time < duration:
            time.sleep(interval)
            check_count += 1

            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed

            new_items = crawler.get_incremental_news()

            if new_items:
                new_count += len(new_items)
                print(f"\n🆕 [{datetime.now().strftime('%H:%M:%S')}] 发现 {len(new_items)} 条新消息!")
                print("-" * 50)
                for item in new_items:
                    print(crawler.format_news(item))
                    print("-" * 50)
            else:
                # 简单的进度提示
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查 #{check_count} - 无新消息 (剩余 {remaining}s)", end="\r")

    except KeyboardInterrupt:
        print("\n\n用户中断测试")

    # 统计
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print(f"运行时长: {int(time.time() - start_time)} 秒")
    print(f"检查次数: {check_count}")
    print(f"新增消息: {new_count} 条")
    print(f"已知消息: {len(crawler.seen_seqs)} 条")


if __name__ == "__main__":
    main()
