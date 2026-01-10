from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum, unique
from typing import TYPE_CHECKING, Any, Literal, cast

import pyparsing as pp

from ..schemas.rules import (
    Action,
    ActionType,
    Condition,
    FieldType,
    LogicType,
    OperatorType,
    RuleGroup,
    RuleNode,
)
from ..utils.time_utils import now_with_tz

if TYPE_CHECKING:
    from collections.abc import Generator


@unique
class PunctuationType(StrEnum):
    """
    标点符号类型枚举。

    用于词法分析中的辅助符号，如括号、逗号等。
    """

    LPAR = "LPAR"
    RPAR = "RPAR"
    LBRACK = "LBRACK"
    RBRACK = "RBRACK"
    COMMA = "COMMA"
    ASSIGN = "ASSIGN"
    COLON = "COLON"
    ACTION_PREFIX = "ACTION_PREFIX"


@unique
class BooleanType(StrEnum):
    """
    布尔值类型枚举。

    用于统一管理 DSL/CNL 中的真假值表示。
    """

    TRUE = "TRUE"
    FALSE = "FALSE"


class TokenMap[E: StrEnum]:
    """
    双向映射容器：负责将枚举类型映射到自然语言 Token (单值或多值)。

    提供正向查找 (Enum -> Primary Token/List) 和 反向查找 (Token -> Enum)。
    主要用于解决多语言 (CNL/DSL) 对应的关键词解析问题。

    Attributes:
        _enum_to_tokens: 保存枚举到 Token 列表的正向映射。
        _token_map: 保存 Token 到枚举的反向映射 (Token 统一转为小写存储)。
    """

    def __init__(self, mapping: dict[E, str | list[str]]) -> None:
        """
        初始化 TokenMap。

        Args:
            mapping: 枚举到 Token 的映射字典，Token 可以是字符串或字符串列表。
        """
        self._enum_to_tokens: dict[E, list[str]] = {}
        self._token_map: dict[str, E] = {}

        for enum_key, tokens in mapping.items():
            token_list = [tokens] if isinstance(tokens, str) else tokens
            # 保存正向映射
            self._enum_to_tokens[enum_key] = token_list
            # 建立反向索引 (不论大小写，统一存小写以便查找时忽略大小写)
            for t in token_list:
                # 简单起见，如果配置中有冲突，后定义的覆盖先定义的
                self._token_map[t.lower()] = enum_key

    def get_tokens(self, key: E) -> list[str]:
        """
        获取该枚举对应的所有 Token 列表。

        Args:
            key: 目标枚举值。

        Returns:
            list[str]: 该枚举对应的所有 Token 字符串列表。
        """
        return self._enum_to_tokens.get(key, [])

    def get_primary_token(self, key: E) -> str:
        """
        获取用于生成的首选 Token (列表第一个)。

        Args:
            key: 目标枚举值。

        Returns:
            str: 首选 Token。

        Raises:
            ValueError: 如果该枚举未定义任何 Token。
        """
        tokens = self.get_tokens(key)
        if not tokens:
            raise ValueError(f"No tokens defined for {key}")
        return tokens[0]

    def get_parser_element(self, key: E, caseless: bool = True) -> pp.ParserElement:
        """
        获取用于解析的 pyparsing ParserElement (Literal 或 OneOf)。

        Args:
            key: 目标枚举值。
            caseless: 是否忽略大小写，默认为 True。

        Returns:
            pp.ParserElement: 对应的 pyparsing 解析元素。
        """
        tokens = self.get_tokens(key)
        if not tokens:
            raise ValueError(f"No tokens configured for {key}")

        # 按照长度降序排列，确保最长匹配优先 (例如 '>=' 优于 '>')
        sorted_tokens = sorted(tokens, key=len, reverse=True)

        if len(sorted_tokens) == 1:
            return pp.CaselessLiteral(sorted_tokens[0]) if caseless else pp.Literal(sorted_tokens[0])
        return pp.one_of(sorted_tokens, caseless=caseless)

    def get_enum(self, token: str) -> E | None:
        """
        根据 Token 反查枚举。

        Args:
            token: 输入的 Token 字符串。

        Returns:
            E | None: 对应的枚举值，如果未找到则返回 None。
        """
        return self._token_map.get(token.lower())

    def get_all_tokens(self) -> list[str]:
        """
        获取所有映射中的 Token 列表 (用于构建保留字)。

        Returns:
            list[str]: 所有已注册 Token 的列表。
        """
        return list(self._token_map.keys())

    def get_all_enums(self) -> list[E]:
        """
        获取所有已映射的枚举值。

        Returns:
            list[E]: 所有已配置 Token 的枚举列表。
        """
        return list(self._enum_to_tokens.keys())


@dataclass
class LangConfig:
    """
    语言配置集，包含各类 Token 的映射关系。

    用于定义特定语言模式 (DSL 或 CNL) 下的所有词法规则配置。

    Attributes:
        fields: 字段 Token 映射。
        operators: 操作符 Token 映射。
        logic: 逻辑运算符 Token 映射。
        actions: 动作 Token 映射。
        punctuation: 标点符号 Token 映射。
    """

    fields: TokenMap[FieldType]
    operators: TokenMap[OperatorType]
    logic: TokenMap[LogicType]
    actions: TokenMap[ActionType]
    punctuation: TokenMap[PunctuationType]
    booleans: TokenMap[BooleanType]

    @classmethod
    def create(
        cls,
        fields: dict[FieldType, str | list[str]],
        operators: dict[OperatorType, str | list[str]],
        logic: dict[LogicType, str | list[str]],
        actions: dict[ActionType, str | list[str]],
        punctuation: dict[PunctuationType, str | list[str]],
        booleans: dict[BooleanType, str | list[str]],
    ) -> LangConfig:
        """
        创建语言配置的工厂方法。

        Args:
            fields: 字段映射字典。
            operators: 操作符映射字典。
            logic: 逻辑词映射字典。
            actions: 动作映射字典。
            punctuation: 标点映射字典。
            booleans: 布尔值映射字典。

        Returns:
            LangConfig: 初始化的语言配置对象。
        """
        return cls(
            fields=TokenMap(fields),
            operators=TokenMap(operators),
            logic=TokenMap(logic),
            actions=TokenMap(actions),
            punctuation=TokenMap(punctuation),
            booleans=TokenMap(booleans),
        )


COMMON_PUNCT: dict[PunctuationType, str | list[str]] = {
    PunctuationType.LPAR: ["(", "（"],
    PunctuationType.RPAR: [")", "）"],
    PunctuationType.LBRACK: ["[", "【"],
    PunctuationType.RBRACK: ["]", "】"],
    PunctuationType.COMMA: [",", "，", "、"],
    PunctuationType.ASSIGN: ["=", "：", ":"],
    PunctuationType.COLON: [":", "："],
    PunctuationType.ACTION_PREFIX: ["DO", "执行", "ACT"],
}

DSL_CONFIG = LangConfig.create(
    fields={k: k.value for k in FieldType},
    operators={
        OperatorType.CONTAINS: "contains",
        OperatorType.NOT_CONTAINS: "not_contains",
        OperatorType.REGEX: "match",
        OperatorType.NOT_REGEX: "not_match",
        OperatorType.EQ: "==",
        OperatorType.NEQ: "!=",
        OperatorType.GT: ">",
        OperatorType.LT: "<",
        OperatorType.GTE: ">=",
        OperatorType.LTE: "<=",
        OperatorType.IN: "in",
        OperatorType.NOT_IN: "not_in",
    },
    logic={
        LogicType.AND: "AND",
        LogicType.OR: "OR",
        LogicType.NOT: "NOT",
    },
    actions={k: k.value for k in ActionType},
    punctuation=COMMON_PUNCT,
    booleans={
        BooleanType.TRUE: "true",
        BooleanType.FALSE: "false",
    },
)

CNL_CONFIG = LangConfig.create(
    fields={
        FieldType.TITLE: "标题",
        FieldType.IS_GOOD: ["加精", "精华帖", "精华贴"],
        FieldType.IS_TOP: ["置顶", "置顶帖", "置顶贴"],
        FieldType.IS_SHARE: ["分享", "分享贴", "分享帖"],
        FieldType.IS_HIDE: ["隐藏", "隐藏贴", "隐藏帖"],
        FieldType.TEXT: ["内容", "文本"],
        FieldType.FULL_TEXT: ["完整内容", "全文"],
        FieldType.LEVEL: ["等级", "用户等级"],
        FieldType.USER_ID: "user_id",
        FieldType.PORTRAIT: "portrait",
        FieldType.USER_NAME: "用户名",
        FieldType.NICK_NAME: "昵称",
        FieldType.AGREE_NUM: ["点赞", "点赞数"],
        FieldType.DISAGREE_NUM: ["点踩", "点踩数"],
        FieldType.REPLY_NUM: ["回复", "回复数"],
        FieldType.VIEW_NUM: ["浏览", "浏览数", "浏览量"],
        FieldType.SHARE_NUM: ["分享", "分享数"],
        FieldType.CREATE_TIME: ["创建时间", "发帖时间", "发贴时间", "发布时间"],
        FieldType.LAST_TIME: ["最后回复时间"],
        FieldType.SHARE_FNAME: ["分享来源吧名", "分享来源贴吧"],
        FieldType.SHARE_FID: ["分享来源吧ID", "分享来源fid"],
        FieldType.SHARE_TITLE: ["分享来源标题"],
        FieldType.SHARE_TEXT: ["分享来源内容", "分享来源文本"],
    },
    operators={
        OperatorType.CONTAINS: "包含",
        OperatorType.NOT_CONTAINS: "不包含",
        OperatorType.REGEX: "正则",
        OperatorType.NOT_REGEX: "不匹配正则",
        OperatorType.EQ: "等于",
        OperatorType.NEQ: "不等于",
        OperatorType.GT: "大于",
        OperatorType.LT: "小于",
        OperatorType.GTE: "大于等于",
        OperatorType.LTE: "小于等于",
        OperatorType.IN: "属于",
        OperatorType.NOT_IN: "不属于",
    },
    logic={
        LogicType.AND: ["并且", "且"],
        LogicType.OR: ["或者", "或"],
        LogicType.NOT: "非",
    },
    actions={
        ActionType.DELETE: ["删除", "删贴", "删帖"],
        ActionType.BAN: ["封禁"],
        ActionType.NOTIFY: ["通知"],
    },
    punctuation=COMMON_PUNCT,
    booleans={
        BooleanType.TRUE: ["真", "是", "true", "True"],
        BooleanType.FALSE: ["假", "否", "false", "False"],
    },
)


class RuleEngineParser:
    """
    基于规则的 DSL/CNL 解析引擎。

    该类负责解析特定语法的规则字符串（包括条件触发器和动作执行），
    将其转换为结构化的 RuleNode 和 Action 对象。
    支持 DSL (Domain Specific Language) 和 CNL (Controlled Natural Language) 两种模式，
    分别对应 开发者友好 和 用户友好 的语法风格。

    Attributes:
        _parsers: 缓存不同模式 (dsl/cnl) 下的 pyparsing 解析对象 (trigger_parser, action_parser)。
    """

    def __init__(self) -> None:
        """
        初始化解析引擎。

        预先构建 DSL 和 CNL 的语法解析器以提高后续解析性能。
        """
        self._parsers: dict[str, tuple[pp.ParserElement, pp.ParserElement]] = {}
        self._parsers["dsl"] = (self._build_trigger_grammar(DSL_CONFIG), self._build_action_grammar(DSL_CONFIG))
        self._parsers["cnl"] = (self._build_trigger_grammar(CNL_CONFIG), self._build_action_grammar(CNL_CONFIG))

    def _build_value_parser(self, cfg: LangConfig) -> pp.ParserElement:
        """
        构建通用的值解析器。

        支持解析多种数据类型：
        1. 字符串：支持双引号、单引号及中文引号，支持转义字符。
        2. 数字：支持整数和浮点数。
        3. 布尔值：支持 true/false (不论大小写) 及 中文 真/假/是/否。
        4. 列表：支持形如 [1, "a"] 的列表结构。

        Args:
            cfg: 当前语言配置。

        Returns:
            pp.ParserElement: 值解析器元素。
        """

        def try_parse_datetime(val: str) -> datetime | None:
            val = val.replace("T", " ").strip()
            fmt_list = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y年%m月%d日 %H时%M分%S秒",
                "%Y年%m月%d日 %H时%M分",
                "%Y年%m月%d日",
            ]
            for fmt in fmt_list:
                try:
                    dt = datetime.strptime(val, fmt)
                    return dt.replace(tzinfo=now_with_tz().tzinfo)
                except ValueError:
                    continue
            return None

        quoted_str = (
            pp.QuotedString('"', esc_char="\\")
            | pp.QuotedString("'", esc_char="\\")
            | pp.QuotedString("“", end_quote_char="”", esc_char="\\")
            | pp.QuotedString("‘", end_quote_char="’", esc_char="\\")
        )
        quoted_str.add_parse_action(lambda t: try_parse_datetime(cast("str", t[0])) or t[0])

        # 1. ISO 8601 绝对时间 (YYYY-MM-DD HH:MM:SS) 与 中文日期格式
        # 扩展支持由 Regex 直接捕获的无引号时间字符串
        iso_pattern = r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?"
        cn_pattern = r"\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?)?"

        # 组合模式，注意顺序
        absolute_date_pattern = f"(?:{iso_pattern})|(?:{cn_pattern})"
        iso_date = pp.Regex(absolute_date_pattern).set_name("absolute_date")

        def parse_iso(t: Any) -> datetime | str:
            val = str(t[0])
            res = try_parse_datetime(val)
            return res or val

        iso_date.set_parse_action(parse_iso)

        # 2. 相对时间处理函数
        def parse_relative_time(amount: str | int, unit: str, direction: str = "ago") -> datetime:
            """计算相对时间，例如 '3d' -> now - 3 days"""
            now = now_with_tz()
            val = int(amount)

            delta_args = {}
            if unit.lower() in ("d", "天"):
                delta_args["days"] = val
            elif unit.lower() in ("h", "小时", "时"):
                delta_args["hours"] = val
            elif unit.lower() in ("m", "分", "分钟"):
                delta_args["minutes"] = val
            elif unit.lower() in ("s", "秒"):
                delta_args["seconds"] = val

            delta = timedelta(**delta_args)

            # 逻辑：'3天前' 或 '3d' (默认ago) -> now - delta
            # 如果未来支持 '3天后' 可以判断 direction
            return now - delta

        # 匹配 DSL: 纯数字 + d/h/m/s (无空格)
        dsl_unit = pp.one_of("d h m s", caseless=True)
        relative_dsl = pp.Group(pp.Combine(pp.Word(pp.nums) + dsl_unit)).set_name("relative_dsl")

        def action_dsl(t: Any) -> datetime:
            # t[0] 是 Group 里的内容，如 "10d"
            full_str = t[0][0]
            unit = full_str[-1]
            amount = full_str[:-1]
            return parse_relative_time(amount, unit)

        relative_dsl.set_parse_action(action_dsl)

        # 匹配 CNL: 纯数字 + 中文单位 + (可选"前")
        cnl_unit = pp.one_of("天 小时 时 分 分钟 秒")
        # 允许数字和单位间有空格，允许后缀"前"
        relative_cnl = pp.Group(pp.Word(pp.nums) + pp.Optional(pp.White()) + cnl_unit + pp.Optional("前")).set_name(
            "relative_cnl"
        )

        def action_cnl(t: Any) -> datetime:
            # t[0] 是一个 list，例如 ['3', '天'] 或 ['3', ' ', '天', '前']
            # 取出数字和单位，忽略空格和后缀
            parsed_list = t[0].as_list()
            amount = parsed_list[0]
            # 找到单位 (在 list 中找到属于 cnl_unit 候选词的项)
            for item in parsed_list[1:]:
                if item.strip() and item != "前":
                    return parse_relative_time(amount, item)
            # Fallback
            return parse_relative_time(amount, parsed_list[1])

        relative_cnl.set_parse_action(action_cnl)

        # 3. 关键字 NOW
        now_keyword = pp.CaselessLiteral("NOW").set_parse_action(lambda: now_with_tz())

        # 组合时间解析器
        datetime_expr = iso_date | relative_dsl | relative_cnl | now_keyword

        # 数字 (优先匹配浮点，再匹配整数)
        number = pp.common.number.set_parse_action(operator.itemgetter(0))

        # 布尔值支持
        # 使用配置中的 TokenMap
        bool_true = cfg.booleans.get_parser_element(BooleanType.TRUE, caseless=True)
        bool_false = cfg.booleans.get_parser_element(BooleanType.FALSE, caseless=True)

        # 获取所有真值的 Token 列表用于后续判断
        true_values = set(cfg.booleans.get_tokens(BooleanType.TRUE))

        boolean = (bool_true | bool_false).set_parse_action(lambda t: True if t[0] in true_values else False)

        # 列表 [1, "a", 'b']
        lbrack = cfg.punctuation.get_parser_element(PunctuationType.LBRACK, caseless=True)
        rbrack = cfg.punctuation.get_parser_element(PunctuationType.RBRACK, caseless=True)
        comma = cfg.punctuation.get_parser_element(PunctuationType.COMMA, caseless=True)

        # boolean 必须放在 quoted_str 之前，或者作为独立分支
        list_val = (
            pp.Suppress(lbrack)
            + pp.DelimitedList(boolean | datetime_expr | quoted_str | number, delim=comma)
            + pp.Suppress(rbrack)
        )
        list_val.set_parse_action(lambda t: [t.as_list()])

        return list_val | boolean | datetime_expr | quoted_str | number

    def _build_identifier_parser(self, reserved_words: list[str]) -> pp.ParserElement:
        """
        构建智能标识符解析器。

        关键逻辑：
        1. 允许 中文、字母、数字、下划线、点号。
        2. 实现 Lookahead 机制，排除包含 '保留字' 的匹配，防止 Greedy 匹配吞噬紧邻的操作符。
           例如确保 '贴吧ID等于' 被解析为 Identifier('贴吧ID') + Op('等于')。

        Args:
            reserved_words: 需要保留的关键词列表 (通常是操作符和逻辑词)。

        Returns:
            pp.ParserElement: 标识符解析器。
        """
        # 1. 构建 Lookahead Pattern (?!reserved)
        # 按照长度排序，优先排除长的保留字
        reserved_sorted = sorted(reserved_words, key=len, reverse=True)
        # re.escape 确保特殊字符被转义
        reserved_pattern = "|".join(map(re.escape, reserved_sorted))

        # 2. 构建 Valid Char Pattern
        # [a-zA-Z0-9._\u4e00-\u9fa5]
        valid_chars_pattern = r"[a-zA-Z0-9._\u4e00-\u9fa5]"

        # 3. 组合 Regex: (?:(?!reserved)valid_char)+
        # 对每一个字符位置进行 Lookahead 检查，确保不开启保留字
        regex_str = f"(?:(?!{reserved_pattern}){valid_chars_pattern})+"

        # 忽略大小写
        return pp.Regex(regex_str, flags=re.IGNORECASE)

    def _build_trigger_grammar(self, cfg: LangConfig) -> pp.ParserElement:
        """
        构建触发器规则的语法解析器。

        语法结构包含：
        1. 条件表达式：Field + Operator + Value。
        2. 逻辑组合：NOT, AND, OR 及 括号嵌套。
        3. 标识符识别：支持严格匹配 (Fields) 和 泛型匹配 (Identifier)。

        Args:
            cfg: 当前语言配置。

        Returns:
            pp.ParserElement: 完整的触发器语法解析器。
        """
        value = self._build_value_parser(cfg)

        # 1. Operators
        all_op_tokens = []
        for op in cfg.operators.get_all_enums():
            all_op_tokens.extend(cfg.operators.get_tokens(op))
        all_op_tokens.sort(key=len, reverse=True)
        op_parser_combined = pp.one_of(all_op_tokens, caseless=True).set_name("operator")

        # 2. Strict Fields (Priority for non-greedy matching)
        all_field_tokens = []
        for f in cfg.fields.get_all_enums():
            all_field_tokens.extend(cfg.fields.get_tokens(f))
        all_field_tokens.sort(key=len, reverse=True)
        strict_field_parser = pp.one_of(all_field_tokens, caseless=True).set_name("field_strict")

        # 3. Generic Identifier (Fallback)
        # 准备保留字 (用于切分无空格文本)
        ops = cfg.operators.get_all_tokens()
        logics = cfg.logic.get_all_tokens()
        reserved_list = ops + logics

        generic_identifier = self._build_identifier_parser(reserved_list)

        # 优先匹配已知字段 (Strict)，解决 "内容包含" 被 Word 贪婪吞噬的问题
        identifier = strict_field_parser | generic_identifier

        # 4. 组合 Condition: Field + Op + Value
        # Group 使得结果结构化
        condition = pp.Group(identifier("field") + op_parser_combined("op") + value("val"))

        # 5. 构建递归逻辑树
        LPAR = cfg.punctuation.get_parser_element(PunctuationType.LPAR)
        RPAR = cfg.punctuation.get_parser_element(PunctuationType.RPAR)
        NOT_L = cfg.logic.get_parser_element(LogicType.NOT)
        AND_L = cfg.logic.get_parser_element(LogicType.AND)
        OR_L = cfg.logic.get_parser_element(LogicType.OR)

        trigger_expr = pp.infix_notation(
            condition,
            [
                (NOT_L, 1, pp.opAssoc.RIGHT),
                (AND_L, 2, pp.opAssoc.LEFT),
                (OR_L, 2, pp.opAssoc.LEFT),
            ],
            lpar=LPAR,
            rpar=RPAR,
        )
        return trigger_expr

    def _build_action_grammar(self, cfg: LangConfig) -> pp.ParserElement:
        """
        构建动作列表的语法解析器。

        语法结构包含：
        1. 动作调用：ActionName(key=value, key2=value2)。
        2. 动作列表：多个动作以逗号分隔。
        3. 前缀支持：可选的 DO/Act 前缀。

        Args:
            cfg: 当前语言配置。

        Returns:
            pp.ParserElement: 动作语法解析器。
        """
        identifier = pp.Word(pp.alphanums + "_")  # 参数名通常是英文 key
        value = self._build_value_parser(cfg)

        LPAR = cfg.punctuation.get_parser_element(PunctuationType.LPAR)
        RPAR = cfg.punctuation.get_parser_element(PunctuationType.RPAR)
        ASSIGN = cfg.punctuation.get_parser_element(PunctuationType.ASSIGN)
        COMMA = cfg.punctuation.get_parser_element(PunctuationType.COMMA)
        COLON = cfg.punctuation.get_parser_element(PunctuationType.COLON)

        # key=val
        param_pair = pp.Group(identifier("key") + pp.Suppress(ASSIGN) + value("val"))
        params = pp.Dict(pp.Optional(pp.DelimitedList(param_pair, delim=COMMA)))

        # type(params)
        all_action_tokens = []
        for act in cfg.actions.get_all_enums():
            all_action_tokens.extend(cfg.actions.get_tokens(act))
        all_action_tokens.sort(key=len, reverse=True)
        action_type = pp.one_of(all_action_tokens, caseless=True)

        action_call = pp.Group(action_type("type") + pp.Suppress(LPAR) + params("params") + pp.Suppress(RPAR))

        # prefix: action, action
        prefix_keywords = cfg.punctuation.get_parser_element(PunctuationType.ACTION_PREFIX)
        # prefix 可以是 DO 或 DO:
        prefix = pp.Suppress(prefix_keywords + pp.Optional(COLON))

        action_list = pp.Optional(prefix) + pp.DelimitedList(action_call, delim=COMMA)
        return action_list

    def _to_rule_node(self, parsed_item: Any, cfg: LangConfig) -> RuleNode:
        """
        将 pyparsing 的解析结果递归转换为 Pydantic 定义的 RuleNode 模型。

        处理单一条件 (Condition) 以及复合逻辑组 (RuleGroup)，
        并负责将 DSL/CNL 中的 Token 映射回标准的枚举值。

        Args:
            parsed_item: pyparsing 返回的解析树节点。
            cfg: 当前语言配置。

        Returns:
            RuleNode: 转换后的规则节点 (Condition 或 RuleGroup)。

        Raises:
            ValueError: 如果解析结果包含未知的操作符或逻辑词。
        """
        # 1. Condition (Group['field', 'op', 'val'])
        if "field" in parsed_item:
            raw_field = parsed_item["field"]
            raw_op = parsed_item["op"]
            val = parsed_item["val"]
            if isinstance(val, pp.ParseResults):
                val = val.as_list()
                if len(val) == 1:
                    val = val[0]

            # 兼容处理: one_of 有时返回 list
            if isinstance(raw_op, list | pp.ParseResults):
                raw_op = raw_op[0]
            if isinstance(raw_field, list | pp.ParseResults):
                raw_field = raw_field[0]

            # 强制转换为字符串以满足类型检查
            raw_field_str = str(raw_field)
            raw_op_str = str(raw_op)

            # 映射回标准枚举
            field_enum = cfg.fields.get_enum(raw_field_str)
            if not field_enum:
                # 严格模式：如果配置没覆盖到，且无法识别为标准字段，则报错
                # 之前允许 raw_field_str 回退，现在为了安全性禁止未知字段
                raise ValueError(f"Unknown field: {raw_field_str}")

            op_enum = cfg.operators.get_enum(raw_op_str)
            # 必须找到对应的 Op，否则可能是非法输入
            if not op_enum:
                raise ValueError(f"Unknown operator: {raw_op}")

            return Condition(field=field_enum, operator=op_enum, value=val)

        # 2. RuleGroup (List: [Node, Logic, Node...])
        if isinstance(parsed_item, list) or hasattr(parsed_item, "as_list"):
            items = parsed_item

            # Handle ( A ) - sometimes retained by infix_notation
            lpar_tokens = cfg.punctuation.get_tokens(PunctuationType.LPAR)
            rpar_tokens = cfg.punctuation.get_tokens(PunctuationType.RPAR)
            if len(items) == 3 and items[0] in lpar_tokens and items[-1] in rpar_tokens:
                return self._to_rule_node(items[1], cfg)

            # NOT A
            # 注意: 这里比较 tokens
            # items[0] 是 parsing 出来的 token, 需反查 LogicEnum
            if len(items) == 2:
                token0 = items[0]
                logic_enum = cfg.logic.get_enum(token0)
                if logic_enum == LogicType.NOT:
                    return RuleGroup(logic=LogicType.NOT, conditions=[self._to_rule_node(items[1], cfg)])

            # A AND B AND C
            # 假设同级逻辑相同 (pyparsing infix_notation特性)
            if len(items) >= 3:
                logic_token = items[1]
                logic_enum = cfg.logic.get_enum(logic_token)

                if not logic_enum:
                    raise ValueError(f"Unknown logic operator: {logic_token}")

                conditions = [self._to_rule_node(items[i], cfg) for i in range(0, len(items), 2)]

                return RuleGroup(logic=logic_enum, conditions=conditions)

            # Fallback for single item (defensive)
            if len(items) == 1:
                return self._to_rule_node(items[0], cfg)

        raise ValueError(f"Unexpected parse item: {parsed_item}")

    def _to_actions(self, parsed_res: Any, cfg: LangConfig) -> list[Action]:
        """
        将动作解析结果转换为 Action 对象列表。

        Args:
            parsed_res: pyparsing 解析结果。
            cfg: 当前语言配置。

        Returns:
            list[Action]: 转换后的动作对象列表。

        Raises:
            ValueError: 如果动作类型未知。
        """
        actions = []
        for item in parsed_res:
            raw_type = item.type
            raw_params = item.params.as_dict()

            type_enum = cfg.actions.get_enum(raw_type)
            if not type_enum:
                raise ValueError(f"Unknown action type: {raw_type}")

            actions.append(Action(type=type_enum, params=raw_params))
        return actions

    def parse_rule(self, text: str, mode: Literal["dsl", "cnl"] = "dsl") -> RuleNode:
        """
        解析规则触发器字符串。

        将输入的字符串 (DSL 或 CNL) 解析为 RuleNode 对象 (Condition 或 RuleGroup)。

        Args:
            text: 待解析的规则字符串。
            mode: 解析模式，可选 "dsl" (默认) 或 "cnl"。

        Returns:
            RuleNode: 解析生成的规则节点对象。

        Raises:
            ValueError: 当语法无法匹配或发生解析错误时抛出。
        """
        parser, _ = self._parsers[mode]
        cfg = DSL_CONFIG if mode == "dsl" else CNL_CONFIG
        try:
            # parse_string(parse_all=True) 确保完全匹配
            res = parser.parse_string(text, parse_all=True)[0]
            return self._to_rule_node(res, cfg)
        except pp.ParseException as e:
            # 增强错误提示：可视化指出错误位置
            raise ValueError(f"Parsing failed at position {e.col}:\n{e.line}\n{' ' * (e.col - 1)}^\n{e}") from e

    def parse_actions(self, text: str, mode: Literal["dsl", "cnl"] = "dsl") -> list[Action]:
        """
        解析动作字符串。

        将输入的动作字符串解析为 Action 对象列表。支持 "动作名(参数)" 的调用格式。

        Args:
            text: 待解析的动作字符串。
            mode: 解析模式，可选 "dsl" (默认) 或 "cnl"。

        Returns:
            list[Action]: 解析生成的动作对象列表。

        Raises:
            ValueError: 当语法无法匹配或动作名未知时抛出。
        """
        _, parser = self._parsers[mode]
        cfg = DSL_CONFIG if mode == "dsl" else CNL_CONFIG
        try:
            res = parser.parse_string(text, parse_all=True)
            return self._to_actions(res, cfg)
        except pp.ParseException as e:
            raise ValueError(f"Action parsing failed: {e}") from e

    def scan_rules(self, text: str, mode: Literal["dsl", "cnl"] = "cnl") -> Generator[RuleNode, None, None]:
        """
        从文本中扫描并提取所有合法的规则片段。

        该方法主要用于从非结构化的自然语言文本中提取看似合法的规则，
        常用于处理用户在聊天中输入的混合文本。

        Args:
            text: 输入的任意文本。
            mode: 扫描模式，默认为 "cnl"。

        Yields:
             Generator[RuleNode, None, None]: 逐个返回提取到的规则节点。
        """
        parser, _ = self._parsers[mode]
        cfg = DSL_CONFIG if mode == "dsl" else CNL_CONFIG

        # scan_string 返回生成器 (parsed_obj, start_index, end_index)
        for match, _start, _end in parser.scan_string(text):
            try:
                yield self._to_rule_node(match[0], cfg)
            except Exception:
                continue

    def validate(self, text: str, mode: Literal["dsl", "cnl"]) -> tuple[bool, str | None]:
        """
        验证规则字符串是否符合规范。

        Args:
            text: 待验证的规则字符串。
            mode: 验证模式 ("dsl" 或 "cnl")。

        Returns:
            tuple[bool, str | None]:
                - (True, None): 验证通过。
                - (False, error_msg): 验证失败及错误信息。
        """
        try:
            self.parse_rule(text, mode)
            return True, None
        except ValueError as e:
            return False, str(e)

    def dump_rule(self, node: RuleNode, mode: Literal["dsl", "cnl"] = "dsl") -> str:
        """
        将 RuleNode 序列化为规则字符串。

        支持将内部的规则对象逆向生成 DSL 或 CNL 字符串，确保生成的字符串可以被重新解析。

        Args:
            node: 待序列化的规则节点。
            mode: 输出模式，可选 "dsl" (默认) 或 "cnl"。

        Returns:
            str: 生成的规则字符串。
        """
        cfg = DSL_CONFIG if mode == "dsl" else CNL_CONFIG

        if isinstance(node, Condition):
            # 将 str 值转回 Enum 以查找 Token
            try:
                f_enum = FieldType(node.field)
            except ValueError:
                f_enum = None

            # 如果是预定义的字段，用主Token，否则原样返回
            field_str = cfg.fields.get_primary_token(f_enum) if f_enum else node.field

            # Op 必须是规范的
            o_enum = OperatorType(node.operator)
            op_str = cfg.operators.get_primary_token(o_enum)

            val = node.value

            if isinstance(val, datetime):
                # 格式：2023-01-01 12:00:00
                val_str = val.strftime("%Y-%m-%d %H:%M:%S")
                # 如果是整天，去掉时间部分让看起来更干净
                if val.hour == 0 and val.minute == 0 and val.second == 0:
                    val_str = val.strftime("%Y-%m-%d")
            elif isinstance(val, str):
                # CNL 模式下也可以根据喜好改用中文引号，这里默认使用双引号以保持 JSON 兼容性
                val_str = f'"{val}"'
            elif isinstance(val, bool):
                # 布尔值转回对应语言
                bool_enum = BooleanType.TRUE if val else BooleanType.FALSE
                val_str = cfg.booleans.get_primary_token(bool_enum)
            elif isinstance(val, list):

                def fmt_item(x: Any) -> str:
                    if isinstance(x, datetime):
                        return x.strftime("%Y-%m-%d %H:%M:%S")
                    return f'"{x}"' if isinstance(x, str) else str(x)

                # 递归处理列表内元素
                items = [fmt_item(x) for x in val]
                # 使用主要的括号符号
                lb = cfg.punctuation.get_primary_token(PunctuationType.LBRACK)
                rb = cfg.punctuation.get_primary_token(PunctuationType.RBRACK)
                # 使用主要的逗号分隔符
                sep = cfg.punctuation.get_primary_token(PunctuationType.COMMA) + " "
                val_str = f"{lb}{sep.join(items)}{rb}"
            else:
                val_str = str(val)

            return f"{field_str}{op_str}{val_str}"

        if isinstance(node, RuleGroup):
            # 获取主要的逻辑词
            l_enum = LogicType(node.logic)
            logic_str = cfg.logic.get_primary_token(l_enum)

            # 递归
            children = [self.dump_rule(c, mode) for c in node.conditions]

            # 拼接
            joined = f" {logic_str} ".join(children)

            # 如果是 NOT，加括号
            if l_enum == LogicType.NOT:
                return f"{logic_str} ({children[0]})"

            # 顶层是否加括号通常由调用方决定，这里简单处理：如果是复合组，加上括号
            return f"({joined})"

        raise ValueError(f"Unknown node type: {type(node)}")

    def dump_actions(self, actions: list[Action], mode: Literal["dsl", "cnl"] = "dsl") -> str:
        """
        将 Action 列表序列化为动作字符串。

        Args:
            actions: 动作列表。
            mode: 输出模式，可选 "dsl" (默认) 或 "cnl"。

        Returns:
            str: 生成的动作字符串。
        """
        cfg = DSL_CONFIG if mode == "dsl" else CNL_CONFIG
        parts = []
        for act in actions:
            a_enum = ActionType(act.type)
            t_name = cfg.actions.get_primary_token(a_enum)

            params_parts = []
            for k, v in act.params.items():
                v_str = f'"{v}"' if isinstance(v, str) else str(v)
                # 使用等号
                eq = cfg.punctuation.get_primary_token(PunctuationType.ASSIGN)
                params_parts.append(f"{k}{eq}{v_str}")

            lb = cfg.punctuation.get_primary_token(PunctuationType.LPAR)
            rb = cfg.punctuation.get_primary_token(PunctuationType.RPAR)
            comma = cfg.punctuation.get_primary_token(PunctuationType.COMMA) + " "

            p_str = comma.join(params_parts)
            parts.append(f"{t_name}{lb}{p_str}{rb}")

        prefix = cfg.punctuation.get_primary_token(PunctuationType.ACTION_PREFIX)
        colon = cfg.punctuation.get_primary_token(PunctuationType.COLON)
        comma_sep = cfg.punctuation.get_primary_token(PunctuationType.COMMA) + " "

        body = comma_sep.join(parts)
        return f"{prefix}{colon} {body}"
