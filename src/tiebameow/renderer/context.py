from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Literal, cast

import yarl

from ..client import Client
from ..models.dto import BaseUserDTO, PostDTO, ThreadDTO
from ..utils.logger import logger


class ContextBase(ABC):
    @abstractmethod
    async def close(self) -> None:
        """
        关闭并释放资源
        """
        raise NotImplementedError

    @abstractmethod
    async def get_portrait(self, portrait: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s") -> bytes:
        """
        获取头像

        Args:
            portrait: 头像标识符，或包含头像信息的 ThreadDTO 或 BaseUserDTO 实例
            size: 头像尺寸，可选值为 "s", "m", "l"

        Returns:
            头像的字节数据
        """
        raise NotImplementedError

    @abstractmethod
    async def get_content_images(
        self, content: ThreadDTO | PostDTO, size: Literal["s", "m", "l"] = "s", max_count: int | None = None
    ) -> list[bytes]:
        """
        获取内容所包含的图片

        Args:
            content: 包含图片信息的 ThreadDTO 或 PostDTO 实例
            size: 图片尺寸，可选值为 "s", "m", "l"
            max_count: 最大获取图片数量，默认为 None（获取所有图片）

        Returns:
            图片字节数据列表
        """
        raise NotImplementedError


class DefaultContext(ContextBase):
    def __init__(self) -> None:
        self.client: Client | None = None

    async def get_client(self) -> Client:
        if self.client is None:
            self.client = Client()
            await self.client.__aenter__()
        return self.client

    async def close(self) -> None:
        if self.client is not None:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def get_portrait(self, portrait: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s") -> bytes:
        client = await self.get_client()

        if isinstance(portrait, ThreadDTO):
            portrait = portrait.author.portrait
        elif isinstance(portrait, BaseUserDTO):
            portrait = portrait.portrait

        if not portrait:
            return b""

        if size == "s":
            path = "n"
        elif size == "m":
            path = ""
        elif size == "l":
            path = "h"
        else:
            raise ValueError("Size must be one of 's', 'm', or 'l'.")

        img_url = yarl.URL.build(scheme="http", host="tb.himg.baidu.com", path=f"/sys/portrait{path}/item/{portrait}")
        try:
            response = await client.get_image_bytes(str(img_url))
        except Exception as e:
            logger.error(f"Failed to get portrait image from {img_url}: {e}")
            return b""
        return cast("bytes", response.data)

    async def _get_image(self, image_hash: str, size: Literal["s", "m", "l"] = "s") -> bytes:
        if not image_hash:
            return b""

        client = await self.get_client()

        if size == "s":
            img_url = yarl.URL.build(
                scheme="http", host="imgsrc.baidu.com", path=f"/forum/w=720;q=60;g=0/sign=__/{image_hash}.jpg"
            )
        elif size == "m":
            img_url = yarl.URL.build(
                scheme="http", host="imgsrc.baidu.com", path=f"/forum/w=960;q=60;g=0/sign=__/{image_hash}.jpg"
            )
        elif size == "l":
            img_url = yarl.URL.build(scheme="http", host="imgsrc.baidu.com", path=f"/forum/pic/item/{image_hash}.jpg")
        else:
            raise ValueError("Size must be one of 's', 'm', or 'l'.")

        try:
            response = await client.get_image_bytes(str(img_url))
            return cast("bytes", response.data)
        except Exception as e:
            logger.error(f"Failed to get image from {img_url}: {e}")
            return b""

    async def get_content_images(
        self, content: ThreadDTO | PostDTO, size: Literal["s", "m", "l"] = "s", max_count: int | None = None
    ) -> list[bytes]:
        images = content.images
        if max_count is not None:
            images = images[:max_count]

        images_bytes = await asyncio.gather(*[self._get_image(image.hash, size=size) for image in images])

        return images_bytes
