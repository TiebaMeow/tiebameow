from __future__ import annotations

from datetime import datetime
from functools import cached_property
from types import UnionType
from typing import Any, Literal, Self, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.fragments import FragImageModel, Fragment, TypeFragText


class BaseDTO(BaseModel):
    """
    基础 DTO 类。

    在保证类型严格的同时，允许从不完整的数据源构造 DTO 对象。
    缺失的字段将自动填充为该类型的零值。
    """

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_incomplete_data(cls, data: dict[str, Any] | BaseModel | None = None) -> Self:
        """
        递归补全不完整的数据源缺失的字段并返回 DTO 实例。

        Args:
            data: 不完整的数据源，可以是字典或 Pydantic 模型实例。
        Returns:
            补全后的 DTO 实例。
        """
        if data is None:
            data = {}
        if isinstance(data, BaseModel):
            data = data.model_dump()

        input_payload = data.copy()

        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation

            if field_name in input_payload:
                curr_value = input_payload[field_name]

                # 特殊处理：如果字段是 Pydantic 模型，但传入的是 dict，需要递归补全
                # 防止嵌套对象内部缺字段
                if isinstance(curr_value, dict) and isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    if issubclass(field_type, BaseDTO):
                        input_payload[field_name] = field_type.from_incomplete_data(curr_value)
                    # 处理没有继承 BaseDTO 的普通 Pydantic 模型
                    else:
                        zero_obj = cls._get_zero_value(field_type)
                        # 用传入的 value 覆盖 zero_obj
                        if isinstance(zero_obj, BaseModel):
                            merged_data = zero_obj.model_dump()
                            merged_data.update(curr_value)
                            input_payload[field_name] = field_type.model_validate(merged_data)

            else:
                input_payload[field_name] = cls._get_zero_value(field_type)

        return cls.model_validate(input_payload)

    @classmethod
    def _get_zero_value(cls, field_type: Any) -> Any:
        """根据类型注解生成对应的零值。"""
        origin = get_origin(field_type)
        args = get_args(field_type)

        if origin is Literal:
            return args[0]
        if origin is list:
            return []
        if origin is dict:
            return {}
        if origin is set:
            return set()
        if field_type is int:
            return 0
        if field_type is float:
            return 0.0
        if field_type is str:
            return ""
        if field_type is bool:
            return False
        if field_type is datetime:
            return datetime.fromtimestamp(0)

        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            if issubclass(field_type, BaseDTO):
                return field_type.from_incomplete_data({})
            else:
                dummy_data = {name: cls._get_zero_value(f.annotation) for name, f in field_type.model_fields.items()}
                return field_type.model_validate(dummy_data)

        # 预留复杂类型的处理接口
        if origin is UnionType and type(None) in args:
            pass

        return None


class BaseForumDTO(BaseDTO):
    fid: int
    fname: str


class BaseUserDTO(BaseDTO):
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
    level: int
    glevel: int

    gender: Literal["UNKNOWN", "MALE", "FEMALE"]
    icons: list[str]

    is_bawu: bool
    is_vip: bool
    is_god: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"]
    priv_reply: Literal["ALL", "FANS", "FOLLOW"]


class PostUserDTO(BaseUserDTO):
    level: int
    glevel: int

    gender: Literal["UNKNOWN", "MALE", "FEMALE"]
    ip: str
    icons: list[str]

    is_bawu: bool
    is_vip: bool
    is_god: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"]
    priv_reply: Literal["ALL", "FANS", "FOLLOW"]


class CommentUserDTO(BaseUserDTO):
    level: int

    gender: Literal["UNKNOWN", "MALE", "FEMALE"]
    icons: list[str]

    is_bawu: bool
    is_vip: bool
    is_god: bool

    priv_like: Literal["PUBLIC", "FRIEND", "HIDE"]
    priv_reply: Literal["ALL", "FANS", "FOLLOW"]


class UserInfoDTO(BaseUserDTO):
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


class ShareThreadDTO(BaseDTO):
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int

    title: str
    contents: list[Fragment] = Field(default_factory=list)


class BaseThreadDTO(BaseDTO):
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int

    title: str
    contents: list[Fragment] = Field(default_factory=list)


class ThreadpDTO(BaseThreadDTO):
    author: ThreadUserDTO

    is_share: bool

    agree_num: int
    disagree_num: int
    reply_num: int
    view_num: int
    share_num: int
    create_time: datetime

    thread_type: int
    share_origin: ShareThreadDTO

    @cached_property
    def text(self) -> str:
        text = "".join(frag.text for frag in self.contents if isinstance(frag, TypeFragText))
        return text

    @cached_property
    def images(self) -> list[FragImageModel]:
        images = [frag for frag in self.contents if isinstance(frag, FragImageModel)]
        return images


class ThreadDTO(BaseThreadDTO):
    author: ThreadUserDTO

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

    @cached_property
    def images(self) -> list[FragImageModel]:
        images = [frag for frag in self.contents if isinstance(frag, FragImageModel)]
        return images


class PostDTO(BaseDTO):
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: PostUserDTO

    contents: list[Fragment] = Field(default_factory=list)
    sign: str
    comments: list[CommentDTO] = Field(default_factory=list)

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

    @cached_property
    def images(self) -> list[FragImageModel]:
        images = [frag for frag in self.contents if isinstance(frag, FragImageModel)]
        return images


class CommentDTO(BaseDTO):
    cid: int
    pid: int
    tid: int
    fid: int
    fname: str

    author_id: int
    author: CommentUserDTO

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


class PageInfoDTO(BaseDTO):
    page_size: int = 0
    current_page: int = 0
    total_page: int = 0
    total_count: int = 0

    has_more: bool = False
    has_prev: bool = False


class ThreadsDTO(BaseDTO):
    objs: list[ThreadDTO] = Field(default_factory=list)
    page: PageInfoDTO
    forum: BaseForumDTO


class PostsDTO(BaseDTO):
    objs: list[PostDTO] = Field(default_factory=list)
    page: PageInfoDTO
    forum: BaseForumDTO


class CommentsDTO(BaseDTO):
    objs: list[CommentDTO] = Field(default_factory=list)
    page: PageInfoDTO
    forum: BaseForumDTO
