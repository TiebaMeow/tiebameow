from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jinja2
from aiotieba.typing import Thread, Post, Comment
from pydantic import BaseModel

from ..models.dto import ThreadDTO, PostDTO, CommentDTO
from ..parser import convert_aiotieba_thread, convert_aiotieba_post, convert_aiotieba_comment
from .config import Config
from .context import Base64Context, ContextBase
from .core import PlaywrightCore
from .param import ThreadRenderParam, PostRenderParam, CommentRenderParam, ThreadDetailRenderParam
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

    def _to_thread_param(self, thread: ThreadDTO | Thread | ThreadRenderParam) -> ThreadRenderParam:
        if isinstance(thread, ThreadRenderParam):
            return thread
        if isinstance(thread, Thread):
            thread = convert_aiotieba_thread(thread)
        # ThreadDTO
        return ThreadRenderParam(
            title=thread.title,
            text=thread.text,
            create_time=thread.create_time,
            nick_name=thread.author.nick_name or thread.author.user_name or f"uid:{thread.author.user_id}",
            level=thread.author.level,
            portrait=thread.author.portrait,
            image_hash_list=[img.hash for img in thread.images],
        )

    def _to_comment_param(self, comment: CommentDTO | Comment | CommentRenderParam) -> CommentRenderParam:
        if isinstance(comment, CommentRenderParam):
            return comment
        if isinstance(comment, Comment):
            comment = convert_aiotieba_comment(comment)
        return CommentRenderParam(
            nick_name=comment.author.nick_name or comment.author.user_name or f"uid:{comment.author.user_id}",
            text=comment.text,
            create_time=comment.create_time,
        )

    def _to_post_param(self, post: PostDTO | Post | PostRenderParam) -> PostRenderParam:
        if isinstance(post, PostRenderParam):
            return post
        if isinstance(post, Post):
            post = convert_aiotieba_post(post)
        
        comments = [self._to_comment_param(c) for c in post.comments]
        
        return PostRenderParam(
            text=post.text,
            create_time=post.create_time,
            nick_name=post.author.nick_name or post.author.user_name or f"uid:{post.author.user_id}",
            level=post.author.level,
            portrait=post.author.portrait,
            image_hash_list=[img.hash for img in post.images],
            floor_text=f"{post.floor}楼",
            comments=comments,
        )

    async def _fill_param_urls(self, ctx: ContextBase, param: ThreadRenderParam, max_image_count: int) -> None:
        if not param.portrait_url:
            if param.portrait:
                param.portrait_url = await ctx.get_portrait_url(param.portrait, size="m")
            else:
                param.portrait_url = ""

        if not param.image_url_list and param.image_hash_list:
            param.image_url_list = await ctx.get_image_url_list(
                param.image_hash_list, size="s", max_count=max_image_count
            )

        param.remain_image_count = max(0, len(param.image_hash_list) - len(param.image_url_list))

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

        param = self._to_thread_param(thread)

        if prefix_html:
            param.prefix_html = prefix_html
        if suffix_html:
            param.suffix_html = suffix_html

        async with self.context() as ctx:
            await self._fill_param_urls(ctx, param, max_image_count)

            data = {
                **param.model_dump(),
                "style_list": [FONT_STYLE],
            }

            image_bytes = await self._render_image("thread.html", config=render_config, data=data)
            return image_bytes

    async def render_thread_detail(
        self,
        thread: ThreadDTO | Thread | ThreadRenderParam,
        posts: list[PostDTO | Post | PostRenderParam],
        *,
        width: int = 550,
        max_image_count: int = 9,
        prefix_html: str | None = None,
        suffix_html: str | None = None,
        **config: Any,
    ) -> bytes:
        """
        渲染帖子详情（包含回复）为图像

        Args:
            thread: 要渲染的帖子
            posts: 要渲染的回复列表
            width: 渲染图像的原始宽度，默认为 550 (px)
            max_image_count: 每个楼层最大包含的图片数量，默认为 9
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

        thread_param = self._to_thread_param(thread)
        post_params = [self._to_post_param(p) for p in posts]

        async with self.context() as ctx:
            await self._fill_param_urls(ctx, thread_param, max_image_count)
            for post_param in post_params:
                await self._fill_param_urls(ctx, post_param, max_image_count)

            detail_param = ThreadDetailRenderParam(
                thread=thread_param,
                posts=post_params,
                prefix_html=prefix_html or "",
                suffix_html=suffix_html or "",
            )

            data = {
                **detail_param.model_dump(),
                "style_list": [FONT_STYLE],
            }

            image_bytes = await self._render_image("thread_detail.html", config=render_config, data=data)
            return image_bytes
