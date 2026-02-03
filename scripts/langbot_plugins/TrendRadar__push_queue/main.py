# TrendRadar PushQueue Plugin
# 监听推送队列，通过 LangBot 发送消息
from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class PushQueuePlugin(BasePlugin):

    async def initialize(self) -> None:
        """插件初始化"""
        pass

    def __del__(self) -> None:
        """插件销毁"""
        pass
