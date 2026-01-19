"""数据模型定义模块。

该模块定义了所有与贴吧数据相关的SQLAlchemy ORM模型和Pydantic验证模型，
包括论坛、用户、主题贴、回复、楼中楼等实体，以及各种内容片段的数据模型。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, cast

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import BIGINT, JSON, Boolean, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, foreign, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, TypeEngine

from ..schemas.fragments import FRAG_MAP, Fragment, FragUnknownModel
from ..schemas.rules import Actions, Condition, FieldType, ReviewRule, RuleGroup, RuleNode, TargetType
from ..utils.time_utils import now_with_tz

if TYPE_CHECKING:
    from collections.abc import Callable

    import aiotieba.typing as aiotieba
    from sqlalchemy.engine.interfaces import Dialect

    from .dto import BaseUserDTO, CommentDTO, PostDTO, ThreadDTO

    type AiotiebaType = aiotieba.Thread | aiotieba.Post | aiotieba.Comment


__all__ = [
    "Base",
    "Forum",
    "User",
    "Thread",
    "Post",
    "Comment",
    "Fragment",
    "RuleBase",
    "ReviewRules",
]


class Base(DeclarativeBase):
    pass


class FragmentListType(TypeDecorator[list[Fragment]]):
    """自动处理Fragment模型列表的JSON序列化与反序列化。

    自动适配不同数据库的JSON类型。
    """

    impl = JSON
    cache_ok = True

    def __init__(self, fallback: Callable[[], Fragment] | None = None, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.adapter: TypeAdapter[Fragment] = TypeAdapter(Fragment)
        self.fallback = fallback

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: list[Fragment] | None, dialect: Dialect) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        return [self.adapter.dump_python(item, mode="json") for item in value]

    def process_result_value(self, value: list[dict[str, Any]] | None, dialect: Dialect) -> list[Fragment] | None:
        if value is None:
            return None
        return [self._validate(item) for item in value]

    def _validate(self, item: dict[str, Any]) -> Fragment:
        if "type" in item:
            if model_cls := FRAG_MAP.get(item["type"]):
                return model_cls.model_construct(**item)

        try:
            return self.adapter.validate_python(item)
        except ValidationError:
            if self.fallback:
                return self.fallback()
            raise


class RuleNodeType(TypeDecorator[RuleNode]):
    """自动处理RuleNode模型的JSON序列化与反序列化。"""

    impl = JSON
    cache_ok = True
    _datetime_fields = {FieldType.CREATE_TIME, FieldType.LAST_TIME}

    def __init__(self, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.adapter: TypeAdapter[RuleNode] = TypeAdapter(RuleNode)

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: RuleNode | None, dialect: Dialect) -> dict[str, Any] | None:
        if value is None:
            return None
        prepared = self._serialize_node(value)
        return cast("dict[str, Any]", self.adapter.dump_python(prepared, mode="json"))

    def process_result_value(self, value: dict[str, Any] | None, dialect: Dialect) -> RuleNode | None:
        if value is None:
            return None
        loaded = self.adapter.validate_python(value)
        return self._deserialize_node(loaded)

    def _serialize_node(self, node: RuleNode) -> RuleNode:
        if isinstance(node, Condition):
            if node.field in self._datetime_fields and isinstance(node.value, datetime):
                return node.model_copy(update={"value": node.value.isoformat()})
            return node
        if isinstance(node, RuleGroup):
            converted = [self._serialize_node(child) for child in node.conditions]
            return node.model_copy(update={"conditions": converted})

    def _deserialize_node(self, node: RuleNode) -> RuleNode:
        if isinstance(node, Condition):
            if node.field in self._datetime_fields and isinstance(node.value, str):
                try:
                    return node.model_copy(update={"value": datetime.fromisoformat(node.value)})
                except ValueError:
                    return node
            return node
        if isinstance(node, RuleGroup):
            converted = [self._deserialize_node(child) for child in node.conditions]
            return node.model_copy(update={"conditions": converted})


class ActionsType(TypeDecorator[Actions]):
    """自动处理Actions模型的JSON序列化与反序列化。"""

    impl = JSON
    cache_ok = True

    def __init__(self, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.adapter: TypeAdapter[Actions] = TypeAdapter(Actions)

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Actions | None, dialect: Dialect) -> dict[str, Any] | None:
        if value is None:
            return None
        return cast("dict[str, Any]", self.adapter.dump_python(value, mode="json"))

    def process_result_value(self, value: dict[str, Any] | None, dialect: Dialect) -> Actions | None:
        if value is None:
            return None
        return self.adapter.validate_python(value)


class MixinBase(Base):
    """为SQLAlchemy模型提供通用方法的混入类。"""

    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """将模型实例的列数据转换为字典。

        此方法包含直接映射到数据库表的列，用于批量插入操作。

        Returns:
            dict: 包含模型列名和对应值的字典。
        """
        result = {}
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            result[c.name] = value
        return result


class Forum(MixinBase):
    """贴吧信息数据模型。

    Attributes:
        fid: 论坛ID，主键。
        fname: 论坛名称，建立索引用于快速查询。
        threads: 该论坛下的所有帖子，与Thread模型的反向关系。
    """

    __tablename__ = "forum"

    fid: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    fname: Mapped[str] = mapped_column(String(255), index=True)

    threads: Mapped[list[Thread]] = relationship(
        "Thread",
        back_populates="forum",
        primaryjoin=lambda: Forum.fid == foreign(Thread.fid),
    )


class User(MixinBase):
    """用户数据模型。

    Attributes:
        user_id: 用户user_id，主键。
        portrait: 用户portrait。
        user_name: 用户名。
        nick_name: 用户昵称。
        threads: 该用户发布的所有帖子，与Thread模型的反向关系。
        posts: 该用户发布的所有回复，与Post模型的反向关系。
        comments: 该用户发布的所有评论，与Comment模型的反向关系。
    """

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    portrait: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    nick_name: Mapped[str] = mapped_column(String(255), nullable=True, index=True)

    threads: Mapped[list[Thread]] = relationship(
        "Thread",
        back_populates="author",
        primaryjoin=lambda: User.user_id == foreign(Thread.author_id),
    )
    posts: Mapped[list[Post]] = relationship(
        "Post",
        back_populates="author",
        primaryjoin=lambda: User.user_id == foreign(Post.author_id),
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="author",
        primaryjoin=lambda: User.user_id == foreign(Comment.author_id),
    )

    @classmethod
    def from_dto(cls, dto: BaseUserDTO) -> User:
        """从UserDTO对象创建User模型实例。

        Args:
            dto: UserDTO对象。

        Returns:
            User: 转换后的User模型实例。
        """
        return cls(
            user_id=dto.user_id,
            portrait=dto.portrait,
            user_name=dto.user_name.replace("\x00", ""),
            nick_name=dto.nick_name.replace("\x00", ""),
        )


class Thread(MixinBase):
    """主题贴数据模型。

    Attributes:
        tid: 主题贴tid，与create_time组成复合主键。
        create_time: 主题贴创建时间，带时区信息，与tid组成复合主键。
        title: 主题贴标题内容。
        text: 主题贴的纯文本内容。
        contents: 正文内容碎片列表，以JSONB格式存储。
        last_time: 最后回复时间，带时区信息。
        reply_num: 回复数。
        author_level: 作者在主题贴所在吧的等级。
        scrape_time: 数据抓取时间。
        fid: 所属贴吧fid，外键关联到Forum表。
        author_id: 作者user_id，外键关联到User表。
        forum: 所属贴吧对象，与Forum模型的关系。
        author: 作者用户对象，与User模型的关系。
        posts: 该贴子下的所有回复，与Post模型的反向关系。
    """

    __tablename__ = "thread"
    __table_args__ = (
        Index("idx_thread_forum_ctime", "fid", "create_time"),
        Index("idx_thread_forum_ltime", "fid", "last_time"),
        Index("idx_thread_author_time", "author_id", "create_time"),
        Index("idx_thread_author_forum_time", "author_id", "fid", "create_time"),
    )

    tid: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    contents: Mapped[list[Fragment] | None] = mapped_column(
        MutableList.as_mutable(FragmentListType(fallback=FragUnknownModel)), nullable=True
    )
    last_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reply_num: Mapped[int] = mapped_column(Integer)
    author_level: Mapped[int] = mapped_column(Integer)
    scrape_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_with_tz)

    fid: Mapped[int] = mapped_column(BIGINT, index=True)
    author_id: Mapped[int] = mapped_column(BIGINT, index=True)

    forum: Mapped[Forum] = relationship(
        "Forum",
        back_populates="threads",
        primaryjoin=lambda: foreign(Thread.fid) == Forum.fid,
    )
    author: Mapped[User] = relationship(
        "User",
        back_populates="threads",
        primaryjoin=lambda: foreign(Thread.author_id) == User.user_id,
    )
    posts: Mapped[list[Post]] = relationship(
        "Post",
        back_populates="thread",
        primaryjoin=lambda: Thread.tid == foreign(Post.tid),
    )

    @classmethod
    def from_dto(cls, dto: ThreadDTO) -> Thread:
        """从ThreadDTO对象创建Thread模型实例。

        Args:
            dto: ThreadDTO对象。

        Returns:
            Thread: 转换后的Thread模型实例。
        """
        return cls(
            tid=dto.tid,
            create_time=dto.create_time,
            title=dto.title,
            text=dto.text,
            contents=dto.contents,
            last_time=dto.last_time,
            reply_num=dto.reply_num,
            author_level=dto.author.level,
            scrape_time=now_with_tz(),
            fid=dto.fid,
            author_id=dto.author_id,
        )


class Post(MixinBase):
    """回复数据模型。

    Attributes:
        pid: 回复pid，与create_time组成复合主键。
        create_time: 回复创建时间，带时区信息，与pid组成复合主键。
        text: 回复的纯文本内容。
        contents: 回复的正文内容碎片列表，以JSONB格式存储。
        floor: 楼层号。
        reply_num: 该回复下的楼中楼数量。
        author_level: 作者在主题贴所在吧的等级。
        scrape_time: 数据抓取时间。
        tid: 所属贴子tid，外键关联到Thread表。
        author_id: 作者user_id，外键关联到User表。
        thread: 所属主题贴对象，与Thread模型的关系。
        author: 作者用户对象，与User模型的关系。
        comments: 该回复下的所有楼中楼，与Comment模型的反向关系。
    """

    __tablename__ = "post"
    __table_args__ = (
        Index("idx_post_thread_time", "tid", "create_time"),
        Index("idx_post_author_time", "author_id", "create_time"),
    )

    pid: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    contents: Mapped[list[Fragment] | None] = mapped_column(
        MutableList.as_mutable(FragmentListType(fallback=FragUnknownModel)), nullable=True
    )
    floor: Mapped[int] = mapped_column(Integer)
    reply_num: Mapped[int] = mapped_column(Integer)
    author_level: Mapped[int] = mapped_column(Integer)
    scrape_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_with_tz)

    tid: Mapped[int] = mapped_column(BIGINT, index=True)
    fid: Mapped[int] = mapped_column(BIGINT, index=True)
    author_id: Mapped[int] = mapped_column(BIGINT, index=True)

    thread: Mapped[Thread] = relationship(
        "Thread",
        back_populates="posts",
        primaryjoin=lambda: foreign(Post.tid) == Thread.tid,
    )
    author: Mapped[User] = relationship(
        "User",
        back_populates="posts",
        primaryjoin=lambda: foreign(Post.author_id) == User.user_id,
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="post",
        primaryjoin=lambda: Post.pid == foreign(Comment.pid),
    )

    @classmethod
    def from_dto(cls, dto: PostDTO) -> Post:
        """从PostDTO对象创建Post模型实例。

        Args:
            dto: PostDTO对象。

        Returns:
            Post: 转换后的Post模型实例。
        """
        return cls(
            pid=dto.pid,
            create_time=dto.create_time,
            text=dto.text,
            contents=dto.contents,
            floor=dto.floor,
            reply_num=dto.reply_num,
            author_level=dto.author.level,
            scrape_time=now_with_tz(),
            tid=dto.tid,
            fid=dto.fid,
            author_id=dto.author_id,
        )


class Comment(MixinBase):
    """楼中楼数据模型。

    Attributes:
        cid: 楼中楼pid，存储为cid以区分，与create_time组成复合主键。
        create_time: 楼中楼创建时间，带时区信息，与cid组成复合主键。
        text: 楼中楼的纯文本内容。
        contents: 楼中楼的正文内容碎片列表，以JSONB格式存储。
        author_level: 作者在主题贴所在吧的等级。
        reply_to_id: 被回复者的user_id，可为空。
        scrape_time: 数据抓取时间。
        pid: 所属回复ID，外键关联到Post表。
        author_id: 作者user_id，外键关联到User表。
        post: 所属回复对象，与Post模型的关系。
        author: 作者用户对象，与User模型的关系。
    """

    __tablename__ = "comment"
    __table_args__ = (
        Index("idx_comment_post_time", "pid", "create_time"),
        Index("idx_comment_author_time", "author_id", "create_time"),
    )

    cid: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    contents: Mapped[list[Fragment] | None] = mapped_column(
        MutableList.as_mutable(FragmentListType(fallback=FragUnknownModel)), nullable=True
    )
    author_level: Mapped[int] = mapped_column(Integer)
    reply_to_id: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    scrape_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_with_tz)

    pid: Mapped[int] = mapped_column(BIGINT, index=True)
    tid: Mapped[int] = mapped_column(BIGINT, index=True)
    fid: Mapped[int] = mapped_column(BIGINT, index=True)
    author_id: Mapped[int] = mapped_column(BIGINT, index=True)

    post: Mapped[Post] = relationship(
        "Post",
        back_populates="comments",
        primaryjoin=lambda: foreign(Comment.pid) == Post.pid,
    )
    author: Mapped[User] = relationship(
        "User",
        back_populates="comments",
        primaryjoin=lambda: foreign(Comment.author_id) == User.user_id,
    )

    @classmethod
    def from_dto(cls, dto: CommentDTO) -> Comment:
        """从CommentDTO对象创建Comment模型实例。

        Args:
            dto: CommentDTO对象。

        Returns:
            Comment: 转换后的Comment模型实例。
        """
        return cls(
            cid=dto.cid,
            create_time=dto.create_time,
            text=dto.text,
            contents=dto.contents,
            author_level=dto.author.level,
            reply_to_id=dto.reply_to_id,
            scrape_time=now_with_tz(),
            pid=dto.pid,
            tid=dto.tid,
            fid=dto.fid,
            author_id=dto.author_id,
        )


class RuleBase(DeclarativeBase):
    pass


class ReviewRules(RuleBase):
    """审查规则的数据库模型。

    对应数据库中的 review_rules 表。

    Attributes:
        id: 主键 ID。
        fid: 贴吧 fid。
        forum_rule_id: 贴吧规则 ID。
        target_type: 规则作用目标类型。
        name: 规则名称。
        enabled: 是否启用。
        priority: 优先级。
        trigger: 触发条件 JSON。
        actions: 动作列表 JSON。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "review_rules"
    __table_args__ = (
        UniqueConstraint("fid", "forum_rule_id", name="uq_review_rules_fid_forum_rule_id"),
        Index("idx_review_rules_fid_forum_rule_id", "fid", "forum_rule_id"),
        Index("idx_review_rules_fid_enabled_priority", "fid", "enabled", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fid: Mapped[int] = mapped_column(BIGINT, nullable=False)
    forum_rule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    uploader_id: Mapped[int] = mapped_column(BIGINT, default=0, nullable=False)
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, name="target_type_enum"),
        index=True,
        default=TargetType.ALL,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trigger: Mapped[RuleNode] = mapped_column(RuleNodeType, index=True, nullable=False)
    actions: Mapped[Actions] = mapped_column(ActionsType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_with_tz, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, default=now_with_tz, onupdate=now_with_tz, nullable=False
    )

    @classmethod
    def from_rule_data(cls, review_rule: ReviewRule) -> ReviewRules:
        """
        从ReviewRule对象创建ReviewRules模型实例。

        id 字段将被忽略，由数据库自动生成。

        Args:
            review_rule: ReviewRule对象。

        Returns:
            ReviewRules: 转换后的ReviewRules模型实例。
        """
        return cls(
            fid=review_rule.fid,
            forum_rule_id=review_rule.forum_rule_id,
            uploader_id=review_rule.uploader_id,
            target_type=review_rule.target_type,
            name=review_rule.name,
            enabled=review_rule.enabled,
            priority=review_rule.priority,
            trigger=review_rule.trigger,
            actions=review_rule.actions,
        )

    def to_rule_data(self) -> ReviewRule:
        """
        将ReviewRules模型实例转换为ReviewRule对象。

        Returns:
            ReviewRule: 转换后的ReviewRule对象。
        """
        return ReviewRule(
            id=self.id,
            fid=self.fid,
            forum_rule_id=self.forum_rule_id,
            uploader_id=self.uploader_id,
            target_type=self.target_type,
            name=self.name,
            enabled=self.enabled,
            priority=self.priority,
            trigger=self.trigger,
            actions=self.actions,
        )
