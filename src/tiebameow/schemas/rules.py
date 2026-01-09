from __future__ import annotations

from enum import StrEnum, unique
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


@unique
class FieldType(StrEnum):
    """
    支持的字段类型枚举。

    定义了规则引擎中可用于条件判断的所有字段，包括主题帖(Thread)、回复(Post)、
    用户信息以及各类型的通用属性。
    """

    TITLE = "title"  # 仅Thread
    IS_GOOD = "is_good"  # 仅Thread
    IS_TOP = "is_top"  # 仅Thread
    IS_SHARE = "is_share"  # 仅Thread
    IS_HIDE = "is_hide"  # 仅Thread
    TEXT = "text"
    LEVEL = "author.level"
    USER_ID = "author.user_id"
    PORTRAIT = "author.portrait"
    USER_NAME = "author.user_name"
    NICK_NAME = "author.nick_name"
    AGREE_NUM = "agree_num"
    DISAGREE_NUM = "disagree_num"
    REPLY_NUM = "reply_num"  # 仅Thread/Post
    VIEW_NUM = "view_num"  # 仅Thread
    SHARE_NUM = "share_num"  # 仅Thread
    CREATE_TIME = "create_time"
    LAST_TIME = "last_time"  # 仅Thread
    SHARE_FNAME = "share_origin.fname"  # 仅Thread
    SHARE_FID = "share_origin.fid"  # 仅Thread
    SHARE_TITLE = "share_origin.title"  # 仅Thread
    SHARE_TEXT = "share_origin.text"  # 仅Thread


@unique
class OperatorType(StrEnum):
    """
    支持的操作符类型枚举。

    定义了字段值与目标值进行比较的具体逻辑。
    """

    CONTAINS = "contains"
    REGEX = "regex"
    EQ = "eq"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    IN = "in"


@unique
class LogicType(StrEnum):
    """
    支持的逻辑运算符枚举。

    用于连接多个条件节点，构成复杂的逻辑表达式。
    """

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@unique
class ActionType(StrEnum):
    """
    支持的动作类型枚举。

    定义了规则匹配成功后只需执行的具体操作。
    """

    DELETE = "delete"
    BAN = "ban"
    NOTIFY = "notify"


@unique
class TargetType(StrEnum):
    """
    支持的规则目标类型枚举。

    定义了规则适用的内容类型范围。
    """

    ALL = "all"
    THREAD = "thread"
    POST = "post"
    COMMENT = "comment"


class Condition(BaseModel):
    """单个条件单元。

    定义了规则中的最小匹配单元，包含字段、操作符和目标值。

    Attributes:
        field: 匹配字段路径，支持点号分隔的嵌套字段，如 'content', 'author.level'。
        operator: 匹配操作符，支持 'contains', 'regex', 'eq', 'gt', 'lt', 'gte', 'lte', 'in'。
        value: 匹配的目标值，类型取决于操作符。
    """

    field: FieldType
    operator: OperatorType
    value: Any


class RuleGroup(BaseModel):
    """规则组，支持逻辑组合。

    用于组合多个条件或子规则组，支持 AND, OR, NOT 等逻辑运算。

    Attributes:
        logic: 逻辑关系，如 'AND', 'OR', 'NOT' 等。
        conditions: 子条件列表，可以是 Condition 或嵌套的 RuleGroup。
    """

    logic: LogicType
    conditions: list[RuleNode]


# 递归类型别名
type RuleNode = Condition | RuleGroup


class Action(BaseModel):
    """匹配命中后的动作。

    定义了当规则匹配成功时应执行的操作。

    Attributes:
        type: 动作类型，如 'delete', 'ban', 'notify'。
        params: 动作参数字典，具体内容取决于动作类型。
    """

    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)


class ReviewRule(BaseModel):
    """完整的审查规则实体。

    包含规则的元数据、触发条件逻辑树以及命中后的执行动作。

    Attributes:
        id: 规则唯一标识 ID。
        fid: 贴吧 fid。
        target_type: 规则适用的目标类型，如 'all', 'thread', 'post', 'comment'。
        name: 规则名称。
        enabled: 是否启用该规则。
        priority: 规则优先级，数字越大越先执行。
        trigger: 规则触发条件的逻辑树根节点。
        actions: 规则命中后执行的动作列表。
    """

    id: int
    fid: int
    target_type: TargetType
    name: str
    enabled: bool
    priority: int
    trigger: RuleNode
    actions: list[Action]

    @model_validator(mode="after")
    def validate_trigger_match_target(self) -> Self:
        """验证 trigger 中的字段是否匹配 target_type。"""

        thread_only_fields = {
            FieldType.TITLE,
            FieldType.IS_GOOD,
            FieldType.IS_TOP,
            FieldType.IS_SHARE,
            FieldType.IS_HIDE,
            FieldType.VIEW_NUM,
            FieldType.SHARE_NUM,
            FieldType.LAST_TIME,
            FieldType.SHARE_FNAME,
            FieldType.SHARE_FID,
            FieldType.SHARE_TITLE,
            FieldType.SHARE_TEXT,
        }

        thread_post_fields = {FieldType.REPLY_NUM}

        target = self.target_type

        forbidden_fields: set[FieldType] = set()

        if target == TargetType.POST:
            forbidden_fields = thread_only_fields
        elif target == TargetType.COMMENT:
            forbidden_fields = thread_only_fields | thread_post_fields
        elif target == TargetType.ALL:
            forbidden_fields = thread_only_fields | thread_post_fields

        if not forbidden_fields:
            return self

        def validate_node(node: RuleNode) -> None:
            if isinstance(node, Condition):
                if node.field in forbidden_fields:
                    raise ValueError(f"Field '{node.field}' is not valid for target_type '{target}'")
            elif isinstance(node, RuleGroup):
                for child in node.conditions:
                    validate_node(child)

        validate_node(self.trigger)
        return self
