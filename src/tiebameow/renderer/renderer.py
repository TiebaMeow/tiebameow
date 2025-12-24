from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

import jinja2
from aiotieba.typing import Thread
from pydantic import BaseModel

from ..parser import convert_aiotieba_thread
from .config import Config
from .context import ContextBase, DefaultContext
from .core import PlaywrightCore

if TYPE_CHECKING:
    from datetime import datetime

    from ..models.dto import ThreadDTO
    from .core.base import CoreBase


def bytes2base64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


class Renderer:
    def __init__(
        self, core: CoreBase | None = None, context: ContextBase | None = None, config: Config | None = None
    ) -> None:
        if core is None:
            core = PlaywrightCore()
        self.core = core

        if context is None:
            context = DefaultContext()
        self.context = context

        if config is None:
            config = Config()
        self.config = config

        self.env = jinja2.Environment(loader=jinja2.PackageLoader("tiebameow.renderer", "templates"), enable_async=True)
        self.env.filters["format_date"] = format_date

    async def close(self) -> None:
        await self.core.close()
        await self.context.close()

    async def __aenter__(self) -> Renderer:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        await self.close()

    async def _render_html(self, template_name: str, data: BaseModel | dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        if isinstance(data, BaseModel):
            data = data.model_dump()
        html = await template.render_async(**data)
        return html

    async def _render_image(
        self, template_name: str, config: Config | None = None, data: BaseModel | dict[str, Any] | None = None
    ) -> bytes:
        html = await self._render_html(template_name, data or {})
        image_bytes = await self.core.render(html, config or self.config)
        return image_bytes

    async def render_thread(
        self,
        thread: ThreadDTO | Thread,
        *,
        width: int = 550,
        max_image_count: int = 9,
        prefix: str | None = None,
        suffix: str | None = None,
        **config: Any,
    ) -> bytes:
        """
        渲染帖子为图像

        Args:
            thread: 要渲染的帖子，可以是 ThreadDTO 实例或 aiotieba 的 Thread 实例
            width: 渲染图像的原始宽度，默认为 550 (px)
            max_image_count: 最大包含的图片数量，默认为 9
            prefix: 帖子文本前缀，可选，支持 HTML
            suffix: 帖子文本后缀，可选，支持 HTML
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """

        render_config = self.config.model_copy(
            update={
                "width": width,
                **config,
            }
        )

        if isinstance(thread, Thread):
            thread = convert_aiotieba_thread(thread)

        portrait_bytes = await self.context.get_portrait(thread.author.portrait, size="m")
        image_bytes_list = await self.context.get_content_images(thread, size="s", max_count=max_image_count)

        remain_image_count = max(0, len(thread.images) - len(image_bytes_list))

        data = {
            "portrait_base64": bytes2base64(portrait_bytes),
            "thread": thread.model_dump(),
            "images_base64s": [bytes2base64(img) for img in image_bytes_list],
            "remain_image_count": remain_image_count,
            "prefix": prefix,
            "suffix": suffix,
            "text": thread.text,
        }

        image_bytes = await self._render_image("thread.html", config=render_config, data=data)
        return image_bytes
