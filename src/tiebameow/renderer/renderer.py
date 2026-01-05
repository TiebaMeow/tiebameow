from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

import jinja2
import yarl
from aiotieba.typing import Post, Thread

from ..client import Client
from ..models.dto import BaseUserDTO, CommentDTO, PostDTO, ThreadDTO
from ..parser import convert_aiotieba_post, convert_aiotieba_thread
from ..utils.logger import logger
from .config import RenderConfig
from .playwright import PlaywrightCore
from .style import get_font_style

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def format_date(dt: datetime | int | float) -> str:
    if isinstance(dt, (int, float)):
        if dt > 1e11:
            dt = dt / 1000
        dt = datetime.fromtimestamp(dt)
    return dt.strftime("%Y-%m-%d %H:%M")


class Renderer:
    """
    渲染器，用于将数据渲染为图像

    Args:
        config: 渲染配置，若为 None 则使用默认配置
        client: 用于获取资源的客户端实例，若为 None 则创建新的 Client 实例
        template_dir: 自定义模板目录，若为 None 则使用内置模板
    """

    def __init__(
        self,
        config: RenderConfig | None = None,
        client: Client | None = None,
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
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        await self.close()

    @staticmethod
    async def _get_portrait(
        client: Client, data: str | ThreadDTO | BaseUserDTO, size: Literal["s", "m", "l"] = "s"
    ) -> bytes:
        """获取单个用户头像的二进制数据"""
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

    @staticmethod
    async def _get_image(client: Client, image_hash: str, size: Literal["s", "m", "l"] = "s") -> bytes:
        """获取单张图片的二进制数据"""
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

    @staticmethod
    async def _get_images(
        client: Client,
        data: ThreadDTO | PostDTO | list[str],
        size: Literal["s", "m", "l"] = "s",
        max_count: int | None = None,
    ) -> list[bytes]:
        """获取多张图片的二进制数据"""
        if isinstance(data, (ThreadDTO, PostDTO)):
            image_hash_list = [img.hash for img in data.images]
        else:
            image_hash_list = data

        if max_count is not None:
            image_hash_list = image_hash_list[:max_count]

        images_bytes = await asyncio.gather(*[
            Renderer._get_image(client, image_hash, size=size) for image_hash in image_hash_list
        ])

        return images_bytes

    @staticmethod
    async def _get_forum_icon(client: Client, fname: str) -> bytes:
        """根据贴吧名称获取吧头像"""
        if not fname:
            return b""

        try:
            forum_info = await client.get_forum(fname)
        except Exception as e:
            logger.error(f"Failed to get forum info for {fname}: {e}")
            return b""

        if not forum_info or not forum_info.small_avatar:
            return b""

        try:
            response = await client.get_image_bytes(forum_info.small_avatar)
            return cast("bytes", response.data)
        except Exception as e:
            logger.error(f"Failed to get forum icon image from {forum_info.small_avatar}: {e}")
            return b""

    @staticmethod
    def _get_mime_type(data: bytes) -> str:
        """根据二进制数据判断 MIME 类型"""
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"GIF8"):
            return "image/gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def _bytes2base64_url(self, data: bytes) -> str:
        """将二进制数据转换为 Base64 编码的 URL"""
        if not data:
            return ""

        mime_type = self._get_mime_type(data)
        return f"data:{mime_type};base64,{base64.b64encode(data).decode('utf-8')}"

    async def _build_content_context(
        self,
        content: ThreadDTO | PostDTO | CommentDTO,
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

        if isinstance(content, (ThreadDTO, PostDTO)):
            context["image_hash_list"] = [img.hash for img in content.images]
        else:
            context["image_hash_list"] = []

        if isinstance(content, ThreadDTO):
            context["title"] = content.title
            if show_link:
                context["sub_text_list"].append(f"tid: {content.tid}")
        elif isinstance(content, PostDTO):
            context["floor"] = content.floor
            if show_link:
                context["sub_text_list"].append(f"pid: {content.pid}")
            context["comments"] = [await self._build_content_context(c, max_image_count) for c in content.comments]
        elif isinstance(content, CommentDTO):
            pass

        portrait_bytes = b""
        if content.author.portrait:
            portrait_bytes = await self._get_portrait(self.client, content.author.portrait, size="m")

        images_bytes: list[bytes] = []
        if context["image_hash_list"]:
            images_bytes = await self._get_images(
                self.client, context["image_hash_list"], size="s", max_count=max_image_count
            )

        if portrait_bytes:
            context["portrait_url"] = self._bytes2base64_url(portrait_bytes)

        if images_bytes:
            context["image_url_list"] = [self._bytes2base64_url(img) for img in images_bytes]
            context["remain_image_count"] = max(0, len(context["image_hash_list"]) - len(context["image_url_list"]))

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
        self, template_name: str, config: RenderConfig | None = None, data: dict[str, Any] | None = None
    ) -> bytes:
        """
        使用指定模板渲染图像

        Args:
            template_name: 模板名称
            config: 渲染配置，若为 None 则使用默认配置
            data: 渲染数据字典

        Returns:
            bytes: 渲染后的图像字节数据
        """
        html = await self._render_html(template_name, data or {})
        image_bytes = await self.core.render(html, config or self.config)
        return image_bytes

    async def render_content(
        self,
        content: ThreadDTO | Thread | PostDTO | Post,
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
        elif isinstance(content, Post):
            content = convert_aiotieba_post(content)

        content_context = await self._build_content_context(content, max_image_count)

        if title and isinstance(content, ThreadDTO):
            content_context["title"] = title

        if prefix_html:
            content_context["prefix_html"] = prefix_html
        if suffix_html:
            content_context["suffix_html"] = suffix_html

        forum_icon_url = ""
        if content.fname:
            icon_bytes = await self._get_forum_icon(self.client, content.fname)
            forum_icon_url = self._bytes2base64_url(icon_bytes)

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
        thread: ThreadDTO | Thread,
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
        渲染帖子详情（包含回复）为图像

        Args:
            thread: 要渲染的帖子
            posts: 要渲染的回复列表
            max_image_count: 每个楼层最大包含的图片数量，默认为 9
            prefix_html: 帖子文本前缀，可选，支持 HTML
            suffix_html: 帖子文本后缀，可选，支持 HTML
            ignore_first_floor: 是否忽略渲染第一楼（楼主），默认为 True
            show_thread_info: 是否显示帖子信息（转发、点赞、回复数），默认为 True
            show_link: 是否显示 tid 和 pid，默认为 True
            **config: 其他渲染配置参数

        Returns:
            生成的图像的字节数据
        """
        await self._ensure_client()
        render_config = self.config.model_copy(update=config)

        if isinstance(thread, Thread):
            thread = convert_aiotieba_thread(thread)

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
            icon_bytes = await self._get_forum_icon(self.client, thread.fname)
            forum_icon_url = self._bytes2base64_url(icon_bytes)

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
