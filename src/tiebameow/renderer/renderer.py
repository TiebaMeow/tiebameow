from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jinja2
from aiotieba.typing import Thread
from pydantic import BaseModel

from ..models.dto import ThreadDTO
from ..parser import convert_aiotieba_thread
from .config import Config
from .context import Base64Context, ContextBase
from .core import PlaywrightCore
from .param import ThreadRenderParam

if TYPE_CHECKING:
    from datetime import datetime

    from .core.base import CoreBase


def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


class Renderer:
    """
    渲染器，用于将数据渲染为图像

    Args:
        core: 渲染核心实例，若为 None 则使用默认的 PlaywrightCore
        context: 渲染上下文类，若为 None 则使用默认的 Base64Context
        config: 渲染配置，若为 None 则使用默认配置
    """

    def __init__(
        self, core: CoreBase | None = None, context: type[ContextBase] | None = None, config: Config | None = None
    ) -> None:
        if core is None:
            core = PlaywrightCore()
        self.core = core

        if context is None:
            context = Base64Context
        # 检查是否是实例，如果是，则取其类
        elif not isinstance(context, type):
            context = context.__class__

        self.context: type[ContextBase] = context

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
        import asyncio
        html = await self._render_html(template_name, data or {})
        image_bytes = await self.core.render(html, config or self.config)
        await asyncio.sleep(0.5)  # 让出控制权，防止某些情况下的死锁
        return image_bytes

    async def render_thread(
        self,
        thread: ThreadDTO | Thread | ThreadRenderParam,
        *,
        width: int = 550,
        max_image_count: int = 9,
        prefix_html: str | None = None,
        suffix_html: str | None = None,
        **config: Any,
    ) -> bytes:
        """
        渲染帖子为图像

        Args:
            thread: 要渲染的帖子，可以是 ThreadDTO 实例、aiotieba 的 Thread 实例或 ThreadRenderParam 实例
            width: 渲染图像的原始宽度，默认为 550 (px)
            max_image_count: 最大包含的图片数量，默认为 9
            prefix_html: 帖子文本前缀，可选，支持 HTML
            suffix_html: 帖子文本后缀，可选，支持 HTML
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
        if isinstance(thread, ThreadDTO):
            data = ThreadRenderParam(
                title=thread.title,
                text=thread.text,
                create_time=thread.create_time,
                nick_name=thread.author.nick_name or thread.author.user_name or f"uid:{thread.author.user_id}",
                level=thread.author.level,
                portrait=thread.author.portrait,
                image_hash_list=[img.hash for img in thread.images],
            )
        else:
            data = thread

        if prefix_html:
            data.prefix_html = prefix_html
        if suffix_html:
            data.suffix_html = suffix_html

        if data.portrait_url and data.image_url_list:
            data.remain_image_count = max(0, len(data.image_hash_list) - len(data.image_url_list))
            image_bytes = await self._render_image("thread.html", config=render_config, data=data.model_dump())
            return image_bytes

        async with self.context() as ctx:
            if not data.portrait_url:
                if data.portrait:
                    data.portrait_url = await ctx.get_portrait_url(data.portrait, size="m")
                else:
                    data.portrait_url = ""

            if not data.image_url_list and data.image_hash_list:
                data.image_url_list = await ctx.get_image_url_list(
                    data.image_hash_list, size="s", max_count=max_image_count
                )

            data.remain_image_count = max(0, len(data.image_hash_list) - len(data.image_url_list))

            image_bytes = await self._render_image("thread.html", config=render_config, data=data.model_dump())
            return image_bytes
