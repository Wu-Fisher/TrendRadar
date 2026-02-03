# coding=utf-8
"""
消息发送器模块单元测试

测试 senders.py 中的异常处理、超时处理和基本功能
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import requests

from trendradar.notification.senders import (
    send_to_feishu,
    send_to_dingtalk,
    send_to_wework,
    send_to_telegram,
    send_to_slack,
    send_to_generic_webhook,
    send_to_ntfy,
    send_to_bark,
)
from trendradar.constants import Timeouts


# === 测试 Timeouts 常量 ===

def test_timeouts_http_request_value():
    """测试 HTTP 请求超时常量值"""
    assert Timeouts.HTTP_REQUEST == 30


# === 飞书发送器测试 ===

class TestSendToFeishu:
    """飞书发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        """返回单批次内容的分批函数"""
        def split_func(*args, **kwargs):
            return ["Test content batch 1"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        """基本测试参数"""
        return {
            "webhook_url": "https://open.feishu.cn/test",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_send_success(self, mock_post, basic_params):
        """测试成功发送"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StatusCode": 0}
        mock_post.return_value = mock_response

        result = send_to_feishu(**basic_params)

        assert result is True
        mock_post.assert_called_once()
        # 验证使用了 Timeouts 常量
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs.get("timeout") == Timeouts.HTTP_REQUEST

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_feishu(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_feishu(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = send_to_feishu(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_generic_exception(self, mock_post, basic_params):
        """测试通用异常处理"""
        mock_post.side_effect = Exception("Unexpected error")

        result = send_to_feishu(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_api_error_response(self, mock_post, basic_params):
        """测试 API 返回错误"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StatusCode": 1, "msg": "Invalid webhook"}
        mock_post.return_value = mock_response

        result = send_to_feishu(**basic_params)

        assert result is False


# === 钉钉发送器测试 ===

class TestSendToDingtalk:
    """钉钉发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "webhook_url": "https://oapi.dingtalk.com/test",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_dingtalk(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_dingtalk(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_dingtalk(**basic_params)

        assert result is False


# === 企业微信发送器测试 ===

class TestSendToWework:
    """企业微信发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "webhook_url": "https://qyapi.weixin.qq.com/test",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_wework(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_wework(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_text_mode(self, mock_post, basic_params):
        """测试 text 模式"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0}
        mock_post.return_value = mock_response

        result = send_to_wework(**basic_params, msg_type="text")

        assert result is True


# === Telegram 发送器测试 ===

class TestSendToTelegram:
    """Telegram 发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "bot_token": "123456:ABC",
            "chat_id": "-1001234567890",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_telegram(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_telegram(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_telegram(**basic_params)

        assert result is False


# === Slack 发送器测试 ===

class TestSendToSlack:
    """Slack 发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "webhook_url": "https://hooks.slack.com/services/test",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_slack(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_slack(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_slack(**basic_params)

        assert result is False


# === 通用 Webhook 发送器测试 ===

class TestSendToGenericWebhook:
    """通用 Webhook 发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "webhook_url": "https://example.com/webhook",
            "payload_template": None,
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_generic_webhook(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_generic_webhook(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_generic_webhook(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_custom_template(self, mock_post, basic_params):
        """测试自定义模板"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        basic_params["payload_template"] = '{"message": "{content}", "type": "{title}"}'

        result = send_to_generic_webhook(**basic_params)

        assert result is True


# === ntfy 发送器测试 ===

class TestSendToNtfy:
    """ntfy 发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "server_url": "https://ntfy.sh",
            "topic": "test-topic",
            "token": None,
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_ntfy(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_ntfy(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_ntfy(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_rate_limit_429(self, mock_post, basic_params):
        """测试速率限制处理"""
        # 第一次返回 429，第二次返回 200
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        mock_post.side_effect = [mock_response_429, mock_response_200]

        result = send_to_ntfy(**basic_params)

        assert result is True
        assert mock_post.call_count == 2


# === Bark 发送器测试 ===

class TestSendToBark:
    """Bark 发送器测试"""

    @pytest.fixture
    def mock_split_func(self):
        def split_func(*args, **kwargs):
            return ["Test content"]
        return split_func

    @pytest.fixture
    def basic_params(self, mock_split_func):
        return {
            "bark_url": "https://api.day.app/test-device-key",
            "report_data": {"stats": []},
            "report_type": "测试报告",
            "split_content_func": mock_split_func,
        }

    @patch("trendradar.notification.senders.requests.post")
    def test_connect_timeout(self, mock_post, basic_params):
        """测试连接超时处理"""
        mock_post.side_effect = requests.exceptions.ConnectTimeout()

        result = send_to_bark(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_read_timeout(self, mock_post, basic_params):
        """测试读取超时处理"""
        mock_post.side_effect = requests.exceptions.ReadTimeout()

        result = send_to_bark(**basic_params)

        assert result is False

    @patch("trendradar.notification.senders.requests.post")
    def test_connection_error(self, mock_post, basic_params):
        """测试连接错误处理"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_to_bark(**basic_params)

        assert result is False

    def test_invalid_url_no_device_key(self, mock_split_func):
        """测试无效 URL（无 device_key）"""
        result = send_to_bark(
            bark_url="https://api.day.app/",
            report_data={"stats": []},
            report_type="测试报告",
            split_content_func=mock_split_func,
        )

        assert result is False


# === 版本解析函数测试 ===

class TestParseVersion:
    """版本解析函数测试"""

    def test_parse_valid_version(self):
        """测试解析有效版本号"""
        from trendradar.__main__ import _parse_version

        assert _parse_version("1.2.3") == (1, 2, 3)
        assert _parse_version("0.0.1") == (0, 0, 1)
        assert _parse_version("10.20.30") == (10, 20, 30)

    def test_parse_invalid_version(self):
        """测试解析无效版本号"""
        from trendradar.__main__ import _parse_version

        # 这些应该返回 (0, 0, 0) 而不是抛出异常
        assert _parse_version("") == (0, 0, 0)
        assert _parse_version("1.2") == (0, 0, 0)
        assert _parse_version("abc") == (0, 0, 0)
        assert _parse_version(None) == (0, 0, 0)

    def test_parse_version_with_extra_parts(self):
        """测试解析带额外部分的版本号"""
        from trendradar.__main__ import _parse_version

        # 有三个或更多部分时应该正常解析前三个
        assert _parse_version("1.2.3.4") == (1, 2, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
