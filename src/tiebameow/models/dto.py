from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from datetime import datetime

    from ..schemas.fragments import Fragment


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    portrait: str | None = None
    user_name: str | None = None
    nick_name: str | None = None


class ThreadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tid: int
    fid: int
    author_id: int
    title: str
    text: str = ""
    contents: list[Fragment] = Field(default_factory=list)
    create_time: datetime
    last_time: datetime
    reply_num: int = 0
    author_level: int = 0

    author: UserDTO | None = None


class PostDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: int
    tid: int
    fid: int
    author_id: int
    text: str = ""
    contents: list[Fragment] = Field(default_factory=list)
    floor: int
    reply_num: int = 0
    create_time: datetime
    author_level: int = 0

    author: UserDTO | None = None


class CommentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cid: int
    pid: int
    tid: int
    fid: int
    author_id: int
    text: str = ""
    contents: list[Fragment] = Field(default_factory=list)
    create_time: datetime
    author_level: int = 0

    author: UserDTO | None = None
