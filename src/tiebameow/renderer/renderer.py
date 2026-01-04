from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jinja2
from aiotieba.typing import Post, Thread
from pydantic import BaseModel

from ..models.dto import PostDTO, ThreadDTO
from ..parser import convert_aiotieba_thread
from .config import Config
from .context import Base64Context, ContextBase
from .core import PlaywrightCore
from .param import BaseContent, PostContent, RenderContentParam, RenderThreadDetailParam, ThreadContent
from .style import FONT_STYLE

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
        html = await self._render_html(template_name, data or {})
        image_bytes = await self.core.render(html, config or self.config)
        return image_bytes

    async def _fill_content_urls(self, ctx: ContextBase, content: BaseContent, max_image_count: int) -> None:
        if not content.portrait_url:
            if content.portrait:
                content.portrait_url = await ctx.get_portrait_url(content.portrait, size="m")
            else:
                content.portrait_url = ""

        if not content.image_url_list and content.image_hash_list:
            content.image_url_list = await ctx.get_image_url_list(
                content.image_hash_list, size="s", max_count=max_image_count
            )

        content.remain_image_count = max(0, len(content.image_hash_list) - len(content.image_url_list))

    async def _fill_forum_icon_url(self, ctx: ContextBase, param: RenderThreadDetailParam) -> None:
        if param.need_fill_url:
            icon_url = await ctx.get_forum_icon_url(param.forum)
            param.forum_icon_url = icon_url

    async def render_content(
        self,
        content: ThreadDTO | Thread | PostDTO | Post | RenderContentParam,
        *,
        max_image_count: int = 9,
        prefix_html: str | None = None,
        suffix_html: str | None = None,
        title: str = "",
        **config: Any,
    ) -> bytes:
        """
        渲染内容（帖子或回复）为图像

        Args:
            content: 要渲染的内容，可以是 Thread/Post 相关对象
            width: 渲染图像的原始宽度，默认为 500 (px)
            max_image_count: 最大包含的图片数量，默认为 9
            prefix_html: 文本前缀，可选，支持 HTML
            suffix_html: 文本后缀，可选，支持 HTML
            title: 覆盖标题，可选
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """

        render_config = self.config.model_copy(update=config)

        if isinstance(content, RenderContentParam):
            param = content
        else:
            param = RenderContentParam.from_dto(content)

        if title and isinstance(param.content, ThreadContent):
            param.content.title = title

        if prefix_html:
            param.prefix_html = prefix_html
        if suffix_html:
            param.suffix_html = suffix_html

        async with self.context() as ctx:
            await self._fill_content_urls(ctx, param.content, max_image_count)

            data = {
                **param.model_dump(),
                "style_list": [FONT_STYLE],
            }

            image_bytes = await self._render_image("thread.html", config=render_config, data=data)
            return image_bytes

    async def render_thread_detail(
        self,
        thread_or_param: ThreadDTO | Thread | ThreadContent | RenderThreadDetailParam,
        posts: list[PostDTO | Post | PostContent] | None = None,
        *,
        max_image_count: int = 9,
        prefix_html: str | None = None,
        suffix_html: str | None = None,
        ignore_first_floor: bool = True,
        show_thread_info: bool = True,
        show_link: bool = True,
        **config: Any,
    ) -> bytes:
        """
        渲染帖子详情（包含回复）为图像

        Args:
            thread_or_param: 要渲染的帖子，或包含帖子与回复的渲染参数对象
            posts: 要渲染的回复列表
            width: 渲染图像的原始宽度，默认为 500 (px)
            max_image_count: 每个楼层最大包含的图片数量，默认为 9
            prefix_html: 帖子文本前缀，可选，支持 HTML
            suffix_html: 帖子文本后缀，可选，支持 HTML
            show_thread_info: 是否显示帖子信息（转发、点赞、回复数），默认为 False
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """
        render_config = self.config.model_copy(update=config)

        thread: ThreadDTO | Thread | ThreadContent
        if isinstance(thread_or_param, RenderThreadDetailParam):
            param = thread_or_param
            thread = param.thread
        else:
            thread = thread_or_param
            param = RenderThreadDetailParam.from_dto(thread, posts or [])

        if prefix_html:
            param.prefix_html = prefix_html
        if suffix_html:
            param.suffix_html = suffix_html

        if isinstance(thread, Thread):
            thread = convert_aiotieba_thread(thread)

        if show_thread_info and isinstance(thread, ThreadDTO):
            info_html = await self._render_html(
                "thread_info.html",
                {
                    "share_num": thread.share_num,
                    "agree_num": thread.agree_num,
                    "reply_num": thread.reply_num,
                },
            )
            param.thread.sub_html_list.append(info_html)

        if ignore_first_floor:
            param.posts = [p for p in param.posts if p.floor != 1]

        if show_link:
            param.thread.sub_text_list.append(f"tid={param.thread.tid}")

            for post in param.posts:
                post.sub_text_list.append(f"pid={post.pid}")

        async with self.context() as ctx:
            await self._fill_content_urls(ctx, param.thread, max_image_count)
            for post_content in param.posts:
                await self._fill_content_urls(ctx, post_content, max_image_count)
            await self._fill_forum_icon_url(ctx, param)

            data = {
                **param.model_dump(),
                "style_list": [FONT_STYLE],
            }

            image_bytes = await self._render_image("thread_detail.html", config=render_config, data=data)
            return image_bytes
