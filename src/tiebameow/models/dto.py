from datetime import datetime
from functools import cached_property
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.fragments import Fragment, TypeFragText


class BaseUserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    portrait: str
    user_name: str
    nick_name_new: str

    @property
    def nick_name(self) -> str:
        return self.nick_name_new

    @property
    def show_name(self) -> str:
        return self.nick_name_new or self.user_name


class ThreadUserDTO(BaseUserDTO):
    model_config = ConfigDict(from_attributes=True)

    level: int
    glevel: int | None = None

    gender: Literal["UNKNOWN", "MALE", "FEMALE"]
    ip: str | None = None
    icons: list[str]

    is_bawu: bool
    is_vip: bool
    is_god: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"]
    priv_reply: Literal["ALL", "FANS", "FOLLOW"]


class UserInfoDTO(BaseUserDTO):
    model_config = ConfigDict(from_attributes=True)

    nick_name_old: str
    tieba_uid: int

    glevel: int
    gender: Literal["UNKNOWN", "MALE", "FEMALE"]
    age: float
    post_num: int
    agree_num: int
    fan_num: int
    follow_num: int
    forum_num: int
    sign: str
    ip: str
    icons: list[str]

    is_vip: bool
    is_god: bool
    is_blocked: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"]
    priv_reply: Literal["ALL", "FANS", "FOLLOW"]


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
    author: ThreadUserDTO

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

    @cached_property
    def text(self) -> str:
        text = "".join(frag.text for frag in self.contents if isinstance(frag, TypeFragText))
        return text


class PostDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: ThreadUserDTO

    contents: list[Fragment] = Field(default_factory=list)
    sign: str

    is_aimeme: bool
    is_thread_author: bool

    agree_num: int
    disagree_num: int
    reply_num: int
    create_time: datetime

    floor: int

    @cached_property
    def text(self) -> str:
        text = "".join(frag.text for frag in self.contents if isinstance(frag, TypeFragText))
        return text


class CommentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cid: int
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: ThreadUserDTO

    contents: list[Fragment] = Field(default_factory=list)
    reply_to_id: int

    is_thread_author: bool

    agree_num: int
    disagree_num: int
    create_time: datetime

    floor: int

    @cached_property
    def text(self) -> str:
        text = "".join(frag.text for frag in self.contents if isinstance(frag, TypeFragText))
        return text
