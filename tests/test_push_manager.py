# coding=utf-8
"""
推送记录管理模块单元测试

测试 push_manager.py 中的时间范围判断和推送记录功能
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytz

from trendradar.notification.push_manager import PushRecordManager


class TestPushRecordManager:
    """推送记录管理器测试"""

    @pytest.fixture
    def mock_storage_backend(self):
        """创建模拟存储后端"""
        backend = MagicMock()
        backend.backend_name = "MockStorage"
        backend.timezone = "Asia/Shanghai"
        backend.has_pushed_today.return_value = False
        backend.record_push.return_value = True
        return backend

    @pytest.fixture
    def manager(self, mock_storage_backend):
        """创建管理器实例"""
        return PushRecordManager(mock_storage_backend)

    def test_init_with_storage_backend(self, mock_storage_backend):
        """测试使用存储后端初始化"""
        manager = PushRecordManager(mock_storage_backend)
        assert manager.storage_backend == mock_storage_backend

    def test_has_pushed_today_delegates_to_backend(self, manager, mock_storage_backend):
        """测试 has_pushed_today 委托给后端"""
        mock_storage_backend.has_pushed_today.return_value = True

        result = manager.has_pushed_today()

        assert result is True
        mock_storage_backend.has_pushed_today.assert_called_once()

    def test_record_push_delegates_to_backend(self, manager, mock_storage_backend):
        """测试 record_push 委托给后端"""
        result = manager.record_push("测试报告")

        assert result is True
        mock_storage_backend.record_push.assert_called_once_with("测试报告")


class TestIsInTimeRange:
    """时间范围判断测试"""

    @pytest.fixture
    def mock_storage_backend(self):
        backend = MagicMock()
        backend.backend_name = "MockStorage"
        backend.timezone = "Asia/Shanghai"
        return backend

    def test_within_range(self, mock_storage_backend):
        """测试在时间范围内"""
        # 模拟当前时间为 10:30
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 10, 30, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("09:00", "12:00")

        assert result is True

    def test_outside_range_before(self, mock_storage_backend):
        """测试在时间范围之前"""
        # 模拟当前时间为 08:30
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 8, 30, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("09:00", "12:00")

        assert result is False

    def test_outside_range_after(self, mock_storage_backend):
        """测试在时间范围之后"""
        # 模拟当前时间为 13:00
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 13, 0, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("09:00", "12:00")

        assert result is False

    def test_exact_start_time(self, mock_storage_backend):
        """测试精确开始时间"""
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 9, 0, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("09:00", "12:00")

        assert result is True

    def test_exact_end_time(self, mock_storage_backend):
        """测试精确结束时间"""
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 12, 0, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("09:00", "12:00")

        assert result is True

    def test_time_normalization_single_digit(self, mock_storage_backend):
        """测试单位数时间标准化"""
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 9, 5, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        # 使用单位数格式
        result = manager.is_in_time_range("9:0", "12:0")

        assert result is True

    def test_midnight_range(self, mock_storage_backend):
        """测试午夜时间范围"""
        def mock_get_time():
            tz = pytz.timezone("Asia/Shanghai")
            return datetime(2024, 1, 1, 0, 30, tzinfo=tz)

        manager = PushRecordManager(mock_storage_backend, get_time_func=mock_get_time)

        result = manager.is_in_time_range("00:00", "01:00")

        assert result is True


class TestDefaultGetTime:
    """默认时间获取函数测试"""

    def test_uses_storage_timezone(self):
        """测试使用存储后端的时区"""
        backend = MagicMock()
        backend.backend_name = "MockStorage"
        backend.timezone = "America/New_York"

        manager = PushRecordManager(backend)

        # 调用默认时间函数
        result = manager._default_get_time()

        # 应该返回带时区的 datetime
        assert result.tzinfo is not None

    def test_fallback_to_shanghai(self):
        """测试回退到上海时区"""
        backend = MagicMock()
        backend.backend_name = "MockStorage"
        # 删除 timezone 属性，使 getattr 回退到默认值
        del backend.timezone

        manager = PushRecordManager(backend)

        # 即使没有 timezone 属性，也应该能获取时间（回退到 Asia/Shanghai）
        result = manager._default_get_time()

        assert result is not None
        assert result.tzinfo is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
