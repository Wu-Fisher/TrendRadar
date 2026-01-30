# coding=utf-8
"""
爬虫新闻过滤器

提供三层过滤机制：标题 -> 摘要 -> 完整内容
复用 TrendRadar 的关键词配置。
"""

import re
from typing import List, Dict, Tuple, Optional
from .base import CrawlerNewsItem


def filter_news_item(
    item: CrawlerNewsItem,
    word_groups: List[Dict],
    filter_words: List[str],
    global_filters: List[str],
    match_mode: str = "any"  # any: 任一层匹配即可, all: 所有层都匹配
) -> Tuple[bool, List[str], str]:
    """
    三层过滤：标题 -> 摘要 -> 完整内容

    Args:
        item: 新闻条目
        word_groups: 关键词组列表
        filter_words: 过滤词列表
        global_filters: 全局过滤词列表
        match_mode: 匹配模式

    Returns:
        (是否通过, 匹配的关键词列表, 过滤原因)
    """
    matched_keywords = []
    filter_reason = ""

    # 1. 检查全局过滤词（任一内容匹配则排除）
    all_content = f"{item.title} {item.summary} {item.full_content}"
    for filter_word in global_filters:
        if filter_word and filter_word.lower() in all_content.lower():
            return False, [], f"全局过滤词匹配: {filter_word}"

    # 2. 三层关键词匹配
    texts_to_check = [
        ("title", item.title),
        ("summary", item.summary),
        ("full_content", item.full_content),
    ]

    for layer_name, text in texts_to_check:
        if not text:
            continue

        for group in word_groups:
            match_result = _matches_word_group(text, group, filter_words)
            if match_result:
                keyword = group.get("display_name") or _get_group_name(group)
                if keyword and keyword not in matched_keywords:
                    matched_keywords.append(keyword)

    # 3. 判断是否通过
    passed = len(matched_keywords) > 0
    if not passed:
        filter_reason = "无匹配关键词"

    return passed, matched_keywords, filter_reason


def filter_news_items(
    items: List[CrawlerNewsItem],
    word_groups: List[Dict],
    filter_words: List[str],
    global_filters: List[str],
    match_mode: str = "any"
) -> Tuple[List[CrawlerNewsItem], List[CrawlerNewsItem]]:
    """
    批量过滤新闻条目

    Args:
        items: 新闻条目列表
        word_groups: 关键词组列表
        filter_words: 过滤词列表
        global_filters: 全局过滤词列表
        match_mode: 匹配模式

    Returns:
        (通过过滤的条目列表, 被过滤的条目列表)
    """
    passed_items = []
    filtered_items = []

    for item in items:
        passed, keywords, reason = filter_news_item(
            item, word_groups, filter_words, global_filters, match_mode
        )

        item.matched_keywords = keywords
        item.filtered_out = not passed
        item.filter_reason = reason

        if passed:
            passed_items.append(item)
        else:
            filtered_items.append(item)

    return passed_items, filtered_items


def _matches_word_group(
    text: str,
    group: Dict,
    filter_words: List[str]
) -> bool:
    """
    检查文本是否匹配关键词组

    关键词组格式:
    {
        "words": ["word1", "word2"],  # 普通词（任一匹配）
        "required": ["+word3"],       # 必须词（全部匹配）
        "excluded": ["!word4"],       # 排除词（任一匹配则排除）
        "patterns": ["/regex/"],      # 正则表达式
        "display_name": "显示名称"
    }
    """
    text_lower = text.lower()

    # 1. 检查排除词
    excluded = group.get("excluded", [])
    for ex in excluded:
        word = ex.lstrip("!")
        if word.lower() in text_lower:
            return False

    # 2. 检查必须词
    required = group.get("required", [])
    for req in required:
        word = req.lstrip("+")
        if word.lower() not in text_lower:
            return False

    # 3. 检查普通词（任一匹配）
    words = group.get("words", [])
    word_matched = False
    for word in words:
        if word.lower() in text_lower:
            word_matched = True
            break

    # 4. 检查正则表达式
    patterns = group.get("patterns", [])
    pattern_matched = False
    for pattern in patterns:
        # 去除 / 包裹
        if pattern.startswith("/") and pattern.endswith("/"):
            pattern = pattern[1:-1]
        try:
            if re.search(pattern, text, re.IGNORECASE):
                pattern_matched = True
                break
        except re.error:
            continue

    # 5. 判断结果
    # 如果有必须词，必须全部匹配
    # 如果有普通词或正则，至少一个匹配
    if required and not all(r.lstrip("+").lower() in text_lower for r in required):
        return False

    if words or patterns:
        return word_matched or pattern_matched

    # 只有必须词的情况
    return len(required) > 0


def _get_group_name(group: Dict) -> str:
    """获取关键词组的显示名称"""
    if group.get("display_name"):
        return group["display_name"]
    words = group.get("words", [])
    if words:
        return words[0]
    required = group.get("required", [])
    if required:
        return required[0].lstrip("+")
    return "未知"


def load_frequency_words_for_crawler(
    filepath: str = "config/frequency_words.txt"
) -> Tuple[List[Dict], List[str], List[str]]:
    """
    从 frequency_words.txt 加载关键词配置

    复用 TrendRadar 的配置格式

    Returns:
        (word_groups, filter_words, global_filters)
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return [], [], []

    word_groups = []
    filter_words = []
    global_filters = []

    current_group = None
    in_global_filter = False

    for line in content.splitlines():
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith("#"):
            continue

        # 检查区域标记
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if section_name.upper() == "GLOBAL_FILTER":
                in_global_filter = True
                current_group = None
            else:
                in_global_filter = False
                # 新的关键词组
                current_group = {
                    "name": section_name,
                    "display_name": section_name,
                    "words": [],
                    "required": [],
                    "excluded": [],
                    "patterns": [],
                }
                word_groups.append(current_group)
            continue

        # 处理全局过滤词
        if in_global_filter:
            global_filters.append(line)
            continue

        # 处理关键词
        if current_group is None:
            # 没有分组时，创建默认组
            current_group = {
                "name": "default",
                "display_name": "",
                "words": [],
                "required": [],
                "excluded": [],
                "patterns": [],
            }
            word_groups.append(current_group)

        # 解析关键词行
        # 格式: word | +required | !excluded | /pattern/ | word => display_name
        if " => " in line:
            parts = line.split(" => ", 1)
            word_part = parts[0].strip()
            display_name = parts[1].strip()
            current_group["display_name"] = display_name
            line = word_part

        if line.startswith("+"):
            current_group["required"].append(line)
        elif line.startswith("!"):
            current_group["excluded"].append(line)
            filter_words.append(line.lstrip("!"))
        elif line.startswith("/") and line.endswith("/"):
            current_group["patterns"].append(line)
        else:
            current_group["words"].append(line)

    return word_groups, filter_words, global_filters


def format_filter_result(
    passed_items: List[CrawlerNewsItem],
    filtered_items: List[CrawlerNewsItem]
) -> str:
    """格式化过滤结果为文本"""
    lines = []
    lines.append(f"=== 过滤结果 ===")
    lines.append(f"通过: {len(passed_items)} 条")
    lines.append(f"过滤: {len(filtered_items)} 条")
    lines.append("")

    if passed_items:
        lines.append("--- 通过的条目 ---")
        for item in passed_items[:10]:
            keywords = ", ".join(item.matched_keywords) if item.matched_keywords else "无"
            lines.append(f"  [{item.seq}] {item.title[:50]}... | 关键词: {keywords}")
        if len(passed_items) > 10:
            lines.append(f"  ... 还有 {len(passed_items) - 10} 条")
        lines.append("")

    if filtered_items:
        lines.append("--- 被过滤的条目 ---")
        for item in filtered_items[:10]:
            lines.append(f"  [{item.seq}] {item.title[:50]}... | 原因: {item.filter_reason}")
        if len(filtered_items) > 10:
            lines.append(f"  ... 还有 {len(filtered_items) - 10} 条")

    return "\n".join(lines)
