# coding=utf-8
"""
pytest 配置文件

禁用 ROS 相关插件，避免与系统环境冲突
"""

import pytest


# 禁用 ROS/ament 相关插件
collect_ignore_glob = ["**/ros/**"]


def pytest_configure(config):
    """配置 pytest，添加自定义标记"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试收集行为"""
    # 可以在这里添加跳过特定测试的逻辑
    pass


# 禁用 ROS 插件的列表
pytest_plugins = []


def pytest_ignore_collect(collection_path, config):
    """忽略 ROS 相关的测试收集"""
    path_str = str(collection_path)
    if "/ros/" in path_str.lower() or "ament" in path_str.lower():
        return True
    return False
