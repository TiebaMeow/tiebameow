from __future__ import annotations

from datetime import datetime

from aiotieba.typing import Comment, Post, Thread
from pydantic import BaseModel, field_validator

from ..models.dto import CommentDTO, PostDTO, ThreadDTO
from ..parser import convert_aiotieba_comment, convert_aiotieba_post, convert_aiotieba_thread


def convert_timestamp(v: int | float | datetime) -> datetime:
    if isinstance(v, (int, float)):
        if v > 1e11:
            v = v / 1000
        return datetime.fromtimestamp(v)
    return v


class BaseContent(BaseModel):
    text: str = ""

    create_time: datetime | int | float

    nick_name: str = ""

    level: int = 0

    portrait: str = ""

    portrait_url: str = ""

    image_hash_list: list[str] = []

    image_url_list: list[str] = []

    remain_image_count: int = 0

    sub_text_list: list[str] = []

    sub_html_list: list[str] = []

    tid: int = 0

    pid: int = 0

    @property
    def need_fill_url(self) -> bool:
        return bool((self.image_hash_list and not self.image_url_list) or (self.portrait and not self.portrait_url))

    @field_validator("create_time", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | float | datetime) -> datetime:
        return convert_timestamp(v)


class CommentContent(BaseModel):
    nick_name: str = ""
    text: str = ""
    create_time: datetime | int | float

    tid: int = 0
    pid: int = 0

    @field_validator("create_time", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | float | datetime) -> datetime:
        return convert_timestamp(v)

    @classmethod
    def from_dto(cls, dto: CommentDTO | Comment) -> CommentContent:
        if isinstance(dto, Comment):
            dto = convert_aiotieba_comment(dto)

        return cls(
            nick_name=dto.author.nick_name or dto.author.user_name or f"uid:{dto.author.user_id}",
            text=dto.text,
            create_time=dto.create_time,
            tid=dto.tid,
            pid=dto.pid,
        )


class ThreadContent(BaseContent):
    title: str = ""

    @classmethod
    def from_dto(cls, dto: ThreadDTO | Thread) -> ThreadContent:
        if isinstance(dto, Thread):
            dto = convert_aiotieba_thread(dto)

        return cls(
            text=dto.text,
            create_time=dto.create_time,
            nick_name=dto.author.nick_name or dto.author.user_name or f"uid:{dto.author.user_id}",
            level=dto.author.level,
            portrait=dto.author.portrait,
            image_hash_list=[img.hash for img in dto.images],
            title=dto.title,
            sub_text_list=[str(dto.tid)],
            tid=dto.tid,
            pid=dto.pid,
        )


class PostContent(BaseContent):
    title: str = ""
    floor: int = 0
    comments: list[CommentContent] = []

    @classmethod
    def from_dto(cls, dto: PostDTO | Post) -> PostContent:
        if isinstance(dto, Post):
            dto = convert_aiotieba_post(dto)

        comments = [CommentContent.from_dto(c) for c in dto.comments]

        return cls(
            text=dto.text,
            create_time=dto.create_time,
            nick_name=dto.author.nick_name or dto.author.user_name or f"uid:{dto.author.user_id}",
            level=dto.author.level,
            portrait=dto.author.portrait,
            image_hash_list=[img.hash for img in dto.images],
            comments=comments,
            floor=dto.floor,
            tid=dto.tid,
            pid=dto.pid,
        )


class RenderBaseParam(BaseModel):
    prefix_html: str = ""
    suffix_html: str = ""

    forum: str = ""
    forum_icon_url: str = ""

    @property
    def need_fill_url(self) -> bool:
        return bool(self.forum and not self.forum_icon_url)


class RenderContentParam(RenderBaseParam):
    content: ThreadContent | PostContent

    @classmethod
    def from_dto(cls, dto: ThreadDTO | PostDTO | Thread | Post) -> RenderContentParam:
        content: ThreadContent | PostContent
        if isinstance(dto, (ThreadDTO, Thread)):
            content = ThreadContent.from_dto(dto)
        else:
            content = PostContent.from_dto(dto)

        fname = ""
        if isinstance(dto, (ThreadDTO, PostDTO)):
            fname = dto.fname
        elif isinstance(dto, (Thread, Post)):
            fname = dto.fname

        return cls(content=content, forum=fname)

    @property
    def need_fill_url_any(self) -> bool:
        return self.need_fill_url or self.content.need_fill_url


class RenderThreadDetailParam(RenderBaseParam):
    thread: ThreadContent
    posts: list[PostContent] = []

    @classmethod
    def from_dto(
        cls, thread_dto: ThreadDTO | Thread | ThreadContent, post_dtos: list[PostDTO | Post | PostContent]
    ) -> RenderThreadDetailParam:
        thread = thread_dto if isinstance(thread_dto, ThreadContent) else ThreadContent.from_dto(thread_dto)
        posts = [
            post_dto if isinstance(post_dto, PostContent) else PostContent.from_dto(post_dto) for post_dto in post_dtos
        ]

        fname = ""

        if isinstance(thread_dto, ThreadDTO):
            fname = thread_dto.fname
        elif isinstance(thread_dto, Thread):
            fname = thread_dto.fname

        return cls(thread=thread, posts=posts, forum=fname)

    @property
    def need_fill_url_any(self) -> bool:
        if self.need_fill_url or self.thread.need_fill_url:
            return True
        for post in self.posts:
            if post.need_fill_url:
                return True
        return False
