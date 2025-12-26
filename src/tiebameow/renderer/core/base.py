from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config


class CoreBase(ABC):
    @staticmethod
    @abstractmethod
    def check_installed() -> bool:
        """
        检查Core所需的依赖是否已安装。

        Returns:
            如果依赖已安装则返回True，否则返回False
        """
        raise NotImplementedError

    @abstractmethod
    async def launch(self) -> None:
        """
        启动Core。
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """
        关闭Core。
        """
        raise NotImplementedError

    @abstractmethod
    async def render(self, html: str, config: Config) -> bytes:
        """
        将HTML渲染为图像。

        Args:
            html: 要渲染的HTML内容
            config: 渲染设置

        Returns:
            生成的bytes
        """
        raise NotImplementedError
