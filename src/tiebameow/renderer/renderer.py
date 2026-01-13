from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

import jinja2
import yarl
from aiotieba.api.get_posts._classdef import Comment_p, Thread_p
from aiotieba.typing import Comment, Post, Thread

from ..client import Client
from ..models.dto import CommentDTO, PostDTO, ThreadDTO, ThreadpDTO
from ..parser import convert_aiotieba_comment, convert_aiotieba_post, convert_aiotieba_thread, convert_aiotieba_threadp
from ..utils.logger import logger
from .config import RenderConfig
from .playwright_core import PlaywrightCore
from .style import FONT_URL, font_path, get_font_style

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from playwright.async_api import Route

    type RenderContentType = (
        ThreadDTO | Thread | ThreadpDTO | Thread_p | PostDTO | Post | CommentDTO | Comment | Comment_p
    )


def format_date(dt: datetime | int | float) -> str:
    if isinstance(dt, (int, float)):
        if dt > 1e11:
            dt = dt / 1000
        dt = datetime.fromtimestamp(dt)
    return dt.strftime("%Y-%m-%d %H:%M")


class Renderer:
    """
    渲染器，用于将贴子数据渲染为图像

    Args:
        client: 用于获取资源的客户端实例，若为 None 则创建新的 Client 实例
        config: 渲染配置，若为 None 则使用默认配置
        template_dir: 自定义模板目录，若为 None 则使用内置模板
    """

    def __init__(
        self,
        client: Client | None = None,
        config: RenderConfig | None = None,
        template_dir: str | Path | None = None,
    ) -> None:
        self.core = PlaywrightCore()

        if config is None:
            config = RenderConfig()
        self.config = config

        self.client = client or Client()
        self._own_client = client is None
        self._client_entered = False

        loader: jinja2.BaseLoader
        if template_dir:
            loader = jinja2.FileSystemLoader(str(template_dir))
        else:
            loader = jinja2.PackageLoader("tiebameow.renderer", "templates")

        self.env = jinja2.Environment(loader=loader, enable_async=True)
        self.env.filters["format_date"] = format_date

    async def close(self) -> None:
        await self.core.close()
        if self._own_client and self._client_entered:
            await self.client.__aexit__(None, None, None)
            self._client_entered = False

    async def _ensure_client(self) -> None:
        if self._own_client and not self._client_entered:
            await self.client.__aenter__()
            self._client_entered = True

    async def __aenter__(self) -> Renderer:
        await self._ensure_client()
        try:
            await self.core.launch()
        except Exception:
            await self.close()
            raise
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        await self.close()

    @staticmethod
    def _get_portrait_url(portrait: str, size: Literal["s", "m", "l"] = "s") -> str:
        """获取用户头像的本地URL"""
        return str(
            yarl.URL.build(
                scheme="http", host="tiebameow.local", path="/portrait", query={"id": portrait, "size": size}
            )
        )

    @staticmethod
    def _get_image_url(image_hash: str, size: Literal["s", "m", "l"] = "s") -> str:
        """获取图片的本地URL"""
        return str(
            yarl.URL.build(
                scheme="http", host="tiebameow.local", path="/image", query={"hash": image_hash, "size": size}
            )
        )

    @staticmethod
    def _get_forum_icon_url(fname: str) -> str:
        """获取吧头像的本地URL"""
        return str(yarl.URL.build(scheme="http", host="tiebameow.local", path="/forum", query={"fname": fname}))

    async def _handle_route(self, route: Route) -> None:
        """
        处理 Playwright 的路由请求

        拦截对 tiebameow.local 的请求，并根据请求路径提供相应的资源。

        Args:
            route: Playwright 的路由对象
        """
        url = yarl.URL(route.request.url)

        if url.host != "tiebameow.local":
            await route.continue_()
            return

        if str(url) == FONT_URL:
            if font_path.exists():
                await route.fulfill(path=font_path)
            else:
                await route.abort()
            return

        try:
            if url.path == "/portrait":
                portrait = url.query.get("id")
                size = url.query.get("size", "s")
                if not portrait:
                    await route.abort()
                    return

                path = ""
                if size == "s":
                    path = "n"
                elif size == "l":
                    path = "h"

                real_url = yarl.URL.build(
                    scheme="http", host="tb.himg.baidu.com", path=f"/sys/portrait{path}/item/{portrait}"
                )
                await self._proxy_request(route, str(real_url))

            elif url.path == "/image":
                image_hash = url.query.get("hash")
                size = url.query.get("size", "s")

                if not image_hash:
                    await route.abort()
                    return

                if size == "s":
                    real_url = yarl.URL.build(
                        scheme="http",
                        host="imgsrc.baidu.com",
                        path=f"/forum/w=720;q=60;g=0/sign=__/{image_hash}.jpg",
                    )
                elif size == "m":
                    real_url = yarl.URL.build(
                        scheme="http",
                        host="imgsrc.baidu.com",
                        path=f"/forum/w=960;q=60;g=0/sign=__/{image_hash}.jpg",
                    )
                elif size == "l":
                    real_url = yarl.URL.build(
                        scheme="http", host="imgsrc.baidu.com", path=f"/forum/pic/item/{image_hash}.jpg"
                    )
                else:
                    await route.abort()
                    return

                await self._proxy_request(route, str(real_url))

            elif url.path == "/forum":
                fname = url.query.get("fname")
                if not fname:
                    await route.abort()
                    return

                try:
                    forum_info = await self.client.get_forum(fname)
                    if forum_info and forum_info.small_avatar:
                        await self._proxy_request(route, forum_info.small_avatar)
                    else:
                        await route.abort()
                except Exception:
                    await route.abort()

            else:
                await route.abort()

        except Exception as e:
            logger.error(f"Error handling route {url}: {e}")
            await route.abort()

    async def _proxy_request(self, route: Route, url: str) -> None:
        try:
            response = await self.client.get_image_bytes(url)
            await route.fulfill(body=response.data)
        except Exception as e:
            logger.error(f"Failed to proxy request for {url}: {e}")
            await route.abort()

    async def _build_content_context(
        self,
        content: ThreadDTO | ThreadpDTO | PostDTO | CommentDTO,
        max_image_count: int = 9,
        show_link: bool = True,
    ) -> dict[str, Any]:
        """
        构建渲染内容上下文字典

        Args:
            content: 要构建上下文的内容，可以是 ThreadDTO、PostDTO 或 CommentDTO
            max_image_count: 最大包含的图片数量，默认为 9
            show_link: 是否显示 tid 和 pid，默认为 True

        Returns:
            dict[str, Any]: 包含渲染内容信息的字典
        """
        context: dict[str, Any] = {
            "text": content.text,
            "create_time": content.create_time,
            "nick_name": content.author.show_name or f"uid:{content.author.user_id}",
            "level": content.author.level,
            "portrait_url": "",
            "image_url_list": [],
            "remain_image_count": 0,
            "sub_text_list": [],
            "sub_html_list": [],
            "tid": content.tid,
            "pid": content.pid,
        }

        if isinstance(content, (ThreadDTO, ThreadpDTO, PostDTO)):
            context["image_hash_list"] = [img.hash for img in content.images]
        else:
            context["image_hash_list"] = []

        if isinstance(content, (ThreadDTO, ThreadpDTO)):
            context["title"] = content.title
            if show_link:
                context["sub_text_list"].append(f"tid: {content.tid}")
        elif isinstance(content, PostDTO):
            context["floor"] = content.floor
            if show_link:
                context["sub_text_list"].append(f"pid: {content.pid}")
            context["comments"] = [await self._build_content_context(c, max_image_count) for c in content.comments]
        elif isinstance(content, CommentDTO):
            context["pid"] = content.cid
            context["floor"] = content.floor
            if show_link:
                context["sub_text_list"].append(f"pid: {content.cid}")

        if content.author.portrait:
            size: Literal["s", "m", "l"] = "s" if isinstance(content, CommentDTO) else "m"
            context["portrait_url"] = self._get_portrait_url(content.author.portrait, size=size)

        if context["image_hash_list"]:
            limit = min(max_image_count, len(context["image_hash_list"]))
            context["image_url_list"] = [self._get_image_url(h, size="s") for h in context["image_hash_list"][:limit]]
            context["remain_image_count"] = max(0, len(context["image_hash_list"]) - limit)

        return context

    async def _render_html(self, template_name: str, data: dict[str, Any]) -> str:
        """
        使用指定模板渲染 HTML

        Args:
            template_name: 模板名称
            data: 渲染数据字典

        Returns:
            str: 渲染后的 HTML 字符串
        """
        template = self.env.get_template(template_name)
        html = await template.render_async(**data)
        return html

    async def _render_image(
        self,
        template_name: str,
        config: RenderConfig | None = None,
        data: dict[str, Any] | None = None,
        element: str | None = None,
    ) -> bytes:
        """
        使用指定模板渲染图像

        Args:
            template_name: 模板名称
            config: 渲染配置，若为 None 则使用默认配置
            data: 渲染数据字典
            element: 要截图的元素选择器，若为 None 则截图全页

        Returns:
            bytes: 渲染后的图像字节数据
        """
        html = await self._render_html(template_name, data or {})
        image_bytes = await self.core.render(
            html, config or self.config, element=element, request_handler=self._handle_route
        )
        return image_bytes

    async def render_content(
        self,
        content: RenderContentType,
        *,
        max_image_count: int = 9,
        prefix_html: str | None = None,
        suffix_html: str | None = None,
        title: str = "",
        **config: Any,
    ) -> bytes:
        """
        渲染内容（贴子或回复）为图像

        Args:
            content: 要渲染的内容，可以是 Thread/Post 相关对象
            max_image_count: 最大包含的图片数量，默认为 9
            prefix_html: 文本前缀，可选，支持 HTML
            suffix_html: 文本后缀，可选，支持 HTML
            title: 覆盖标题，可选
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """
        await self._ensure_client()

        render_config = self.config.model_copy(update=config)

        if isinstance(content, Thread):
            content = convert_aiotieba_thread(content)
        elif isinstance(content, Thread_p):
            content = convert_aiotieba_threadp(content)
        elif isinstance(content, Post):
            content = convert_aiotieba_post(content)
        elif isinstance(content, Comment | Comment_p):
            content = convert_aiotieba_comment(content)

        content_context = await self._build_content_context(content, max_image_count)

        if title and isinstance(content, ThreadDTO):
            content_context["title"] = title

        if prefix_html:
            content_context["prefix_html"] = prefix_html
        if suffix_html:
            content_context["suffix_html"] = suffix_html

        forum_icon_url = ""
        if content.fname:
            forum_icon_url = self._get_forum_icon_url(content.fname)

        data = {
            "content": content_context,
            "forum": content.fname,
            "forum_icon_url": forum_icon_url,
            "prefix_html": prefix_html or "",
            "suffix_html": suffix_html or "",
            "style_list": [get_font_style()],
        }

        image_bytes = await self._render_image("thread.html", config=render_config, data=data)
        return image_bytes

    async def render_thread_detail(
        self,
        thread: ThreadDTO | ThreadpDTO | Thread | Thread_p,
        posts: Sequence[PostDTO | Post] | None = None,
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
        渲染贴子详情（包含回复）为图像

        Args:
            thread: 要渲染的贴子
            posts: 要渲染的回复列表
            max_image_count: 每个楼层最大包含的图片数量，默认为 9
            prefix_html: 贴子文本前缀，可选，支持 HTML
            suffix_html: 贴子文本后缀，可选，支持 HTML
            ignore_first_floor: 是否忽略渲染第一楼（楼主），默认为 True
            show_thread_info: 是否显示贴子信息（转发、点赞、回复数），默认为 True
            show_link: 是否显示 tid 和 pid，默认为 True
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """
        await self._ensure_client()
        render_config = self.config.model_copy(update=config)

        if isinstance(thread, Thread):
            thread = convert_aiotieba_thread(thread)
        elif isinstance(thread, Thread_p):
            thread = convert_aiotieba_threadp(thread)

        posts_dtos: list[PostDTO] = []
        if posts:
            for p in posts:
                if isinstance(p, Post):
                    posts_dtos.append(convert_aiotieba_post(p))
                else:
                    posts_dtos.append(p)

        if ignore_first_floor:
            posts_dtos = [p for p in posts_dtos if p.floor != 1]

        thread_context = await self._build_content_context(thread, max_image_count, show_link=show_link)
        posts_contexts = await asyncio.gather(*[
            self._build_content_context(p, max_image_count, show_link=show_link) for p in posts_dtos
        ])

        if show_thread_info:
            info_html = await self._render_html(
                "thread_info.html",
                {
                    "share_num": thread.share_num,
                    "agree_num": thread.agree_num,
                    "reply_num": thread.reply_num,
                },
            )
            thread_context["sub_html_list"].append(info_html)

        forum_icon_url = ""
        if thread.fname:
            forum_icon_url = self._get_forum_icon_url(thread.fname)

        data = {
            "thread": thread_context,
            "posts": posts_contexts,
            "forum": thread.fname,
            "forum_icon_url": forum_icon_url,
            "prefix_html": prefix_html or "",
            "suffix_html": suffix_html or "",
            "style_list": [get_font_style()],
        }

        image_bytes = await self._render_image("thread_detail.html", config=render_config, data=data)
        return image_bytes

    async def text_to_image(
        self,
        text: str,
        *,
        title: str = "",
        header: str = "",
        footer: str = "",
        simple_mode: bool = False,
        **config: Any,
    ) -> bytes:
        """
        将简单的文本渲染为图片

        Args:
            text: 要渲染的文本
            title: 标题，可选，显示在头部下方的粗体大号字
            header: 页眉，可选，显示在最上方的灰色小号字
            footer: 页脚文本（如页码），可选，显示在最下方的灰色小号字
            simple_mode: 是否使用极简紧凑样式，默认为 False
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """
        render_config = self.config.model_copy(update=config)

        template_name = "text_simple.html" if simple_mode else "text.html"

        data = {
            "text": text,
            "title": title,
            "header": header,
            "footer": footer,
            "style_list": [get_font_style()],
        }

        element = ".container" if simple_mode else None
        image_bytes = await self._render_image(template_name, config=render_config, data=data, element=element)
        return image_bytes
