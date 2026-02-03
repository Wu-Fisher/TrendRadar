# coding=utf-8
"""
批次处理模块单元测试

测试 batch.py 中的批次头部生成、截断和添加功能
"""

import pytest

from trendradar.notification.batch import (
    get_batch_header,
    get_max_batch_header_size,
    truncate_to_bytes,
    add_batch_headers,
)


class TestGetBatchHeader:
    """批次头部生成测试"""

    def test_telegram_format(self):
        """测试 Telegram HTML 格式"""
        header = get_batch_header("telegram", 1, 3)
        assert "<b>[第 1/3 批次]</b>" in header
        assert header.endswith("\n\n")

    def test_slack_format(self):
        """测试 Slack mrkdwn 格式"""
        header = get_batch_header("slack", 2, 5)
        assert "*[第 2/5 批次]*" in header

    def test_wework_text_format(self):
        """测试企业微信文本格式"""
        header = get_batch_header("wework_text", 1, 2)
        assert "[第 1/2 批次]" in header
        # 不应该有 markdown 标记
        assert "**" not in header
        assert "<b>" not in header

    def test_bark_format(self):
        """测试 Bark 纯文本格式"""
        header = get_batch_header("bark", 3, 3)
        assert "[第 3/3 批次]" in header
        assert "**" not in header

    def test_feishu_markdown_format(self):
        """测试飞书 markdown 格式"""
        header = get_batch_header("feishu", 1, 2)
        assert "**[第 1/2 批次]**" in header

    def test_dingtalk_markdown_format(self):
        """测试钉钉 markdown 格式"""
        header = get_batch_header("dingtalk", 5, 10)
        assert "**[第 5/10 批次]**" in header

    def test_ntfy_markdown_format(self):
        """测试 ntfy markdown 格式"""
        header = get_batch_header("ntfy", 1, 1)
        assert "**[第 1/1 批次]**" in header

    def test_wework_markdown_format(self):
        """测试企业微信 markdown 格式（默认）"""
        header = get_batch_header("wework", 2, 4)
        assert "**[第 2/4 批次]**" in header


class TestGetMaxBatchHeaderSize:
    """最大批次头部大小测试"""

    def test_returns_positive_integer(self):
        """测试返回正整数"""
        for format_type in ["telegram", "slack", "feishu", "dingtalk", "wework", "bark", "ntfy"]:
            size = get_max_batch_header_size(format_type)
            assert isinstance(size, int)
            assert size > 0

    def test_consistent_with_actual_header(self):
        """测试与实际头部大小一致"""
        for format_type in ["telegram", "slack", "feishu"]:
            max_size = get_max_batch_header_size(format_type)
            # 生成最大批次的头部
            actual_header = get_batch_header(format_type, 99, 99)
            actual_size = len(actual_header.encode("utf-8"))
            assert max_size == actual_size


class TestTruncateToBytes:
    """字节截断测试"""

    def test_no_truncation_needed(self):
        """测试无需截断的情况"""
        text = "Hello World"
        result = truncate_to_bytes(text, 100)
        assert result == text

    def test_truncate_ascii(self):
        """测试截断 ASCII 文本"""
        text = "Hello World"
        result = truncate_to_bytes(text, 5)
        assert len(result.encode("utf-8")) <= 5

    def test_truncate_unicode_safely(self):
        """测试安全截断 Unicode 文本"""
        text = "你好世界"  # 每个中文字符 3 字节
        # 截断到 7 字节应该保留 2 个字符（6 字节）
        result = truncate_to_bytes(text, 7)
        assert len(result.encode("utf-8")) <= 7
        # 应该是完整的字符，不应该出现解码错误
        result.encode("utf-8").decode("utf-8")

    def test_truncate_mixed_text(self):
        """测试截断混合文本"""
        text = "Hello 你好"
        result = truncate_to_bytes(text, 10)
        assert len(result.encode("utf-8")) <= 10
        # 验证是有效的 UTF-8
        result.encode("utf-8").decode("utf-8")

    def test_exact_boundary(self):
        """测试精确边界"""
        text = "ABC"
        result = truncate_to_bytes(text, 3)
        assert result == "ABC"

    def test_empty_result_on_zero_bytes(self):
        """测试零字节限制"""
        text = "Hello"
        result = truncate_to_bytes(text, 0)
        assert result == ""


class TestAddBatchHeaders:
    """添加批次头部测试"""

    def test_single_batch_no_header(self):
        """测试单批次不添加头部"""
        batches = ["Only one batch"]
        result = add_batch_headers(batches, "feishu", 4096)
        assert result == batches

    def test_multiple_batches_with_headers(self):
        """测试多批次添加头部"""
        batches = ["Batch 1", "Batch 2", "Batch 3"]
        result = add_batch_headers(batches, "feishu", 4096)

        assert len(result) == 3
        assert "**[第 1/3 批次]**" in result[0]
        assert "**[第 2/3 批次]**" in result[1]
        assert "**[第 3/3 批次]**" in result[2]

    def test_content_preserved(self):
        """测试内容被保留"""
        original_content = "Important message content"
        batches = [original_content, "Second batch"]
        result = add_batch_headers(batches, "telegram", 4096)

        assert original_content in result[0]

    def test_truncation_when_exceeds_limit(self):
        """测试超出限制时截断"""
        # 创建一个接近限制的大内容
        large_content = "X" * 100
        batches = [large_content]
        # 设置一个很小的限制
        result = add_batch_headers(batches, "feishu", 50)

        # 单批次不添加头部，所以不会被截断
        assert result == batches

    def test_empty_batches(self):
        """测试空批次列表"""
        result = add_batch_headers([], "feishu", 4096)
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
