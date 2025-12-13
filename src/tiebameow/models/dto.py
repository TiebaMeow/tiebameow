from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.fragments import Fragment


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    portrait: str
    user_name: str
    nick_name: str

    level: int
    glevel: int | None = None
    ip: str | None = None
    gender: Literal["UNKNOWN", "MALE", "FEMALE"] | None = None
    icons: list[str] | None = None

    is_bawu: bool | None = None
    is_vip: bool | None = None
    is_god: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"] | None = None
    priv_reply: Literal["ALL", "FANS", "FOLLOW"] | None = None


class ShareThreadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int

    title: str
    contents: list[Fragment] = Field(default_factory=list)


class ThreadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: UserDTO

    title: str
    contents: list[Fragment] = Field(default_factory=list)

    is_good: bool
    is_top: bool
    is_share: bool
    is_hide: bool
    is_livepost: bool
    is_help: bool

    agree_num: int
    disagree_num: int
    reply_num: int
    view_num: int
    share_num: int
    create_time: datetime
    last_time: datetime

    thread_type: int
    tab_id: int
    share_origin: ShareThreadDTO


class PostDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: UserDTO

    contents: list[Fragment] = Field(default_factory=list)
    sign: str

    is_aimeme: bool
    is_thread_author: bool

    agree_num: int
    disagree_num: int
    reply_num: int
    create_time: datetime

    floor: int


class CommentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cid: int
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: UserDTO

    contents: list[Fragment] = Field(default_factory=list)
    reply_to_id: int

    is_thread_author: bool

    agree_num: int
    disagree_num: int
    create_time: datetime

    floor: int
