# coding=utf-8
"""
TrendRadar 日志模块

提供统一的日志配置和获取接口。

使用方式:
    from trendradar.logging import get_logger

    logger = get_logger(__name__)
    logger.info("这是一条日志")
    logger.error("发生错误: %s", error)
"""

import logging
import sys
from typing import Optional


# 日志格式
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 简化格式（用于控制台）
SIMPLE_FORMAT = "[%(levelname)s] [%(name)s] %(message)s"


def setup_logging(
    level: str = "INFO",
    format_style: str = "simple",
    log_file: Optional[str] = None,
) -> None:
    """
    配置全局日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_style: 格式风格 ('simple' 或 'full')
        log_file: 日志文件路径（可选）
    """
    # 选择格式
    log_format = SIMPLE_FORMAT if format_style == "simple" else LOG_FORMAT

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, LOG_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 添加文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        root_logger.addHandler(file_handler)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("crewai").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称（通常使用 __name__）

    Returns:
        Logger 实例
    """
    # 简化模块名称
    if name.startswith("trendradar."):
        name = name[len("trendradar."):]

    return logging.getLogger(name)


# 模块级别的快捷日志器
_default_logger: Optional[logging.Logger] = None


def _get_default_logger() -> logging.Logger:
    """获取默认日志器"""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_logger("trendradar")
    return _default_logger


def debug(msg: str, *args, **kwargs) -> None:
    """快捷 debug 日志"""
    _get_default_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """快捷 info 日志"""
    _get_default_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """快捷 warning 日志"""
    _get_default_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """快捷 error 日志"""
    _get_default_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """快捷 critical 日志"""
    _get_default_logger().critical(msg, *args, **kwargs)
