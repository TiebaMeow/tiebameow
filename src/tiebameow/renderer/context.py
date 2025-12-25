from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

import yarl

from ..client import Client
from ..models.dto import BaseUserDTO, PostDTO, ThreadDTO
from ..utils.logger import logger


class ContextBase(ABC):
    """
    渲染上下文基类

    在类中共享资源，如 HTTP 客户端等。
    如果有在渲染过程中产生临时的资源，在实例中清理
    """

    @classmethod
    @abstractmethod
    async def close(cls) -> None:
        """
        关闭并释放资源
        """
        raise NotImplementedError

    @abstractmethod
    async def __aenter__(self) -> ContextBase:
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_portrait_url(self, data: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s") -> str:
        """
        获取头像

        Args:
            data: 头像标识符，或包含头像信息的 ThreadDTO 或 BaseUserDTO 实例
            size: 头像尺寸，可选值为 "s", "m", "l"

        Returns:
            renderer可用的头像url
        """
        raise NotImplementedError

    @abstractmethod
    async def get_image_url_list(
        self, data: ThreadDTO | PostDTO | list[str], size: Literal["s", "m", "l"] = "s", max_count: int | None = None
    ) -> list[str]:
        """
        获取内容所包含的图片

        Args:
            data: 包含图片信息的 ThreadDTO、PostDTO 实例或图片哈希列表
            size: 图片尺寸，可选值为 "s", "m", "l"
            max_count: 最大获取图片数量，默认为 None（获取所有图片）

        Returns:
            renderer可用的图片url列表
        """
        raise NotImplementedError


async def get_portrait(
    client: Client, data: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s"
) -> bytes:
    if isinstance(data, ThreadDTO):
        portrait = data.author.portrait
    elif isinstance(data, BaseUserDTO):
        portrait = data.portrait
    else:
        portrait = data

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


async def get_image(client: Client, image_hash: str, size: Literal["s", "m", "l"] = "s") -> bytes:
    if not image_hash:
        return b""

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


async def get_images(
    client: Client,
    data: ThreadDTO | PostDTO | list[str],
    size: Literal["s", "m", "l"] = "s",
    max_count: int | None = None,
) -> list[bytes]:
    if isinstance(data, (ThreadDTO, PostDTO)):
        image_hash_list = [img.hash for img in data.images]
    else:
        image_hash_list = data

    if max_count is not None:
        image_hash_list = image_hash_list[:max_count]

    images_bytes = await asyncio.gather(*[get_image(client, image_hash, size=size) for image_hash in image_hash_list])

    return images_bytes


class Base64Context(ContextBase):
    """
    渲染上下文，使用 Base64 编码的图片数据作为资源
    """

    client: Client | None = None

    @staticmethod
    def bytes2base64(data: bytes) -> str:
        return base64.b64encode(data).decode("utf-8")

    @classmethod
    async def get_client(cls) -> Client:
        if cls.client is None:
            cls.client = Client()
            await cls.client.__aenter__()
        return cls.client

    @classmethod
    async def close(cls) -> None:
        if cls.client is not None:
            await cls.client.__aexit__(None, None, None)
            cls.client = None

    async def __aenter__(self) -> Base64Context:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        pass

    async def get_portrait_url(self, data: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s") -> str:
        portrait_bytes = await get_portrait(await self.get_client(), data, size=size)
        return f"data:image/jpeg;base64,{self.bytes2base64(portrait_bytes)}"

    async def get_image_url_list(
        self, data: ThreadDTO | PostDTO | list[str], size: Literal["s", "m", "l"] = "s", max_count: int | None = None
    ) -> list[str]:
        images_bytes = await get_images(await self.get_client(), data, size=size, max_count=max_count)
        image_urls = [f"data:image/jpeg;base64,{self.bytes2base64(img_bytes)}" for img_bytes in images_bytes]
        return image_urls


class FileContext(ContextBase):
    """
    渲染上下文，使用本地临时文件作为资源

    *注意：使用此上下文时，需确保 PlaywrightCore 启用了本地文件访问权限 (enable_local_file_access=True)*
    """

    # TODO use async method

    base_dir = Path(tempfile.gettempdir()) / "tiebameow_renderer"
    client: Client | None = None

    def __init__(self) -> None:
        self.task_dir = self.base_dir / uuid4().hex
        if not self.task_dir.exists():
            self.task_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    async def close(cls) -> None:
        if cls.base_dir.exists():
            shutil.rmtree(cls.base_dir, ignore_errors=True)
        if cls.client is not None:
            await cls.client.__aexit__(None, None, None)
            cls.client = None

    @classmethod
    async def get_client(cls) -> Client:
        if cls.client is None:
            cls.client = Client()
            await cls.client.__aenter__()
        return cls.client

    async def __aenter__(self) -> FileContext:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        if self.task_dir.exists():
            shutil.rmtree(self.task_dir, ignore_errors=True)

    async def get_portrait_url(self, data: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s") -> str:
        if isinstance(data, ThreadDTO):
            portrait = data.author.portrait
        elif isinstance(data, BaseUserDTO):
            portrait = data.portrait
        else:
            portrait = data
        portrait_bytes = await get_portrait(await self.get_client(), portrait, size=size)
        file_path = self.task_dir / f"portrait_{portrait}_{size}.jpg"
        with file_path.open("wb") as f:
            f.write(portrait_bytes)
        return file_path.as_uri()

    async def get_image_url_list(
        self, data: ThreadDTO | PostDTO | list[str], size: Literal["s", "m", "l"] = "s", max_count: int | None = None
    ) -> list[str]:
        images_bytes = await get_images(await self.get_client(), data, size=size, max_count=max_count)
        image_urls = []
        for idx, img_bytes in enumerate(images_bytes):
            file_path = self.task_dir / f"image_{uuid4().hex if isinstance(data, list) else data.pid}_{idx}_{size}.jpg"
            with file_path.open("wb") as f:
                f.write(img_bytes)
            image_urls.append(file_path.as_uri())
        return image_urls
