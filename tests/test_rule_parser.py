from __future__ import annotations

import pytest

from tiebameow.parser.rule_parser import RuleEngineParser
from tiebameow.schemas.rules import (
    Action,
    ActionType,
    Condition,
    FieldType,
    LogicType,
    OperatorType,
    RuleGroup,
)


@pytest.fixture
def parser():
    return RuleEngineParser()


class TestRuleEngineParser:
    # === 1. Basic Parsing Tests (DSL & CNL) ===

    def test_parse_dsl_simple(self, parser: RuleEngineParser):
        rule = "title contains 'hello'"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.field == FieldType.TITLE
        assert node.operator == OperatorType.CONTAINS
        assert node.value == "hello"

    def test_parse_cnl_simple(self, parser: RuleEngineParser):
        rule = "标题包含'你好'"
        node = parser.parse_rule(rule, mode="cnl")
        assert isinstance(node, Condition)
        # Verify it maps back to standard enum values
        assert node.field == FieldType.TITLE
        assert node.operator == OperatorType.CONTAINS
        assert node.value == "你好"

    def test_parse_cnl_synonyms(self, parser: RuleEngineParser):
        # Test synonyms defined in CNL_CONFIG
        # IS_GOOD: ["加精", "精华帖", "精华贴"]
        cases = [
            ("加精等于真", FieldType.IS_GOOD),
            ("精华帖等于真", FieldType.IS_GOOD),
            ("精华贴等于真", FieldType.IS_GOOD),
        ]
        for rule_text, field_enum in cases:
            node = parser.parse_rule(rule_text, mode="cnl")
            assert isinstance(node, Condition)
            assert node.field == field_enum
            assert node.value is True

    def test_parse_operators(self, parser: RuleEngineParser):
        # Test various operators
        cases = [
            ("author.level > 5", "dsl", OperatorType.GT, 5),
            ("等级大于5", "cnl", OperatorType.GT, 5),
            ("reply_num >= 10", "dsl", OperatorType.GTE, 10),
            ("回复数大于等于10", "cnl", OperatorType.GTE, 10),
            ("author.user_id in ['1', '2']", "dsl", OperatorType.IN, ["1", "2"]),
            ("user_id属于['1', '2']", "cnl", OperatorType.IN, ["1", "2"]),
        ]
        for text, mode, op_enum, val in cases:
            node = parser.parse_rule(text, mode=mode)
            assert isinstance(node, Condition)
            assert node.operator == op_enum
            assert node.value == val

    # === 2. Logic & Grouping Tests ===

    def test_logic_and_or_not(self, parser: RuleEngineParser):
        # (A AND B) OR NOT C
        text = "(title contains 'A' AND title contains 'B') OR NOT title contains 'C'"
        node = parser.parse_rule(text, mode="dsl")
        assert isinstance(node, RuleGroup)
        assert node.logic == LogicType.OR
        assert len(node.conditions) == 2

        # Left: (A AND B)
        left = node.conditions[0]
        assert isinstance(left, RuleGroup)
        assert left.logic == LogicType.AND
        assert len(left.conditions) == 2

        # Right: NOT C
        right = node.conditions[1]
        assert isinstance(right, RuleGroup)
        assert right.logic == LogicType.NOT
        assert len(right.conditions) == 1
        assert isinstance(right.conditions[0], Condition)
        assert right.conditions[0].value == "C"

    def test_cnl_logic(self, parser: RuleEngineParser):
        text = "标题包含'A'并且(等级大于5或者回复数小于10)"
        node = parser.parse_rule(text, mode="cnl")
        assert isinstance(node, RuleGroup)
        assert node.logic == LogicType.AND
        assert len(node.conditions) == 2

        cond1 = node.conditions[0]
        assert isinstance(cond1, Condition)
        assert cond1.field == FieldType.TITLE

        group2 = node.conditions[1]
        assert isinstance(group2, RuleGroup)
        assert group2.logic == LogicType.OR
        assert len(group2.conditions) == 2

    # === 3. Value Parsing Tests ===

    def test_parse_values(self, parser: RuleEngineParser):
        # String types
        c = parser.parse_rule("text == 'foo'", "dsl")
        assert isinstance(c, Condition)
        assert c.value == "foo"
        c = parser.parse_rule('text == "bar"', "dsl")
        assert isinstance(c, Condition)
        assert c.value == "bar"

        # Numbers
        c = parser.parse_rule("author.level == 123", "dsl")
        assert isinstance(c, Condition)
        assert c.value == 123
        c = parser.parse_rule("author.level == 3.14", "dsl")
        assert isinstance(c, Condition)
        assert c.value == 3.14  # noqa: FURB152

        # Booleans
        bool_cases = [
            ("is_good == true", True),
            ("is_good == True", True),
            ("is_good == false", False),
            ("is_good == False", False),
        ]
        for t, v in bool_cases:
            c = parser.parse_rule(t, "dsl")
            assert isinstance(c, Condition)
            assert c.value == v

        cnl_bool_cases = [
            ("加精等于真", True),
            ("加精等于是", True),
            ("加精等于假", False),
            ("加精等于否", False),
        ]
        for t, v in cnl_bool_cases:
            c = parser.parse_rule(t, "cnl")
            assert isinstance(c, Condition)
            assert c.value == v

        # Lists
        c = parser.parse_rule("author.user_id in [1, 'a', true]", "dsl")
        assert isinstance(c, Condition)
        assert c.value == [1, "a", True]  # Assuming mixed types allowed in list parser

        # CNL List with Chinese brackets
        c = parser.parse_rule("user_id属于【1, 2】", "cnl")
        assert isinstance(c, Condition)
        assert c.value == [1, 2]

    # === 4. Validation Tests ===

    def test_validate_valid(self, parser: RuleEngineParser):
        valid_rules = [
            ("title contains 'test'", "dsl"),
            ("标题包含'测试'", "cnl"),
            ("author.level > 5 AND reply_num < 10", "dsl"),
        ]
        for r, m in valid_rules:
            assert m in ("dsl", "cnl")
            valid, msg = parser.validate(r, mode=m)
            assert valid, f"Should be valid: {r} ({msg})"
            assert msg is None

    def test_validate_invalid(self, parser: RuleEngineParser):
        invalid_rules = [
            ("title contains", "dsl"),  # Incomplete
            ("unknown_field == 1", "dsl"),  # Unknown field
            ("标题 ?? '测试'", "cnl"),  # Unknown operator
            ("(open parenthesis", "dsl"),  # Unbalanced
        ]
        for r, m in invalid_rules:
            assert m in ("dsl", "cnl")
            valid, msg = parser.validate(r, mode=m)
            assert not valid, f"Should be invalid: {r}"
            assert msg is not None

    def test_validate_unknown_field_in_cnl(self, parser: RuleEngineParser):
        # "未知字段" is not mapped
        valid, msg = parser.validate("未知字段等于1", mode="cnl")
        assert not valid
        # Error message detail might vary, but should fail
        if valid:
            pytest.fail(f"Should have failed validation for unknown field but got valid=True, msg={msg}")

    # === 5. Action Parsing Tests ===

    def test_parse_actions_dsl(self, parser: RuleEngineParser):
        text = "DO: delete(reason='bad'), ban(day=1)"
        actions = parser.parse_actions(text, mode="dsl")
        assert len(actions) == 2

        act1 = actions[0]
        assert act1.type == ActionType.DELETE
        assert act1.params["reason"] == "bad"

        act2 = actions[1]
        assert act2.type == ActionType.BAN
        assert act2.params["day"] == 1

    def test_parse_actions_cnl(self, parser: RuleEngineParser):
        text = "执行：删除(reason='广告'), 封禁（days=3），通知（）"
        actions = parser.parse_actions(text, mode="cnl")
        assert len(actions) == 3
        assert actions[0].type == ActionType.DELETE
        assert actions[0].params["reason"] == "广告"
        assert actions[1].type == ActionType.BAN
        assert actions[1].params["days"] == 3
        assert actions[2].type == ActionType.NOTIFY

    def test_action_prefix_optional(self, parser: RuleEngineParser):
        text = "delete(reason='x')"
        actions = parser.parse_actions(text, mode="dsl")
        assert len(actions) == 1
        assert actions[0].type == ActionType.DELETE

    # === 6. Dump (Serialization) Tests ===

    def test_dump_rule(self, parser: RuleEngineParser):
        # Round trip test
        original = "title contains 'hello'"
        node = parser.parse_rule(original, mode="dsl")
        # Dump back
        dumped = parser.dump_rule(node, mode="dsl")
        # Parse again to verify equivalence
        node2 = parser.parse_rule(dumped, mode="dsl")
        assert node == node2

    def test_dump_rule_group(self, parser: RuleEngineParser):
        # Group round trip
        original = "(title contains 'A' AND author.level > 5)"
        node = parser.parse_rule(original, mode="dsl")
        dumped = parser.dump_rule(node, mode="dsl")
        node2 = parser.parse_rule(dumped, mode="dsl")
        assert node == node2

    def test_dump_actions(self, parser: RuleEngineParser):
        actions = [
            Action(type=ActionType.DELETE, params={"reason": "foo"}),
            Action(type=ActionType.BAN, params={"day": 7}),
        ]
        dumped = parser.dump_actions(actions, mode="dsl")
        # Expected format might slightly vary (spaces etc), but should be parseable
        parsed_back = parser.parse_actions(dumped, mode="dsl")
        assert len(parsed_back) == 2
        assert parsed_back[0].type == ActionType.DELETE
        assert parsed_back[0].params["reason"] == "foo"

    # === 7. Scan Rules Tests ===

    def test_scan_rules(self, parser: RuleEngineParser):
        text = """
        Ignore this.
        Rule 1: title contains "spam"
        Some comments.
        Rule 2: (author.level < 3)
        """
        # Note: scan_rules returns generator
        rules = list(parser.scan_rules(text, mode="dsl"))
        assert len(rules) == 2
        r1 = rules[0]
        assert isinstance(r1, Condition)
        assert r1.field == FieldType.TITLE
        assert r1.value == "spam"

        r2 = rules[1]
        # Depending on complexity, it might be Condition or RuleGroup
        if isinstance(r2, RuleGroup):
            # It's parenthesized, so might be parsed as a group
            assert len(r2.conditions) == 1
            inner = r2.conditions[0]
            assert isinstance(inner, Condition)
            assert inner.value == 3
        elif isinstance(r2, Condition):
            assert r2.value == 3

    # === 8. Edge Cases & Errors ===

    def test_no_spaces_cnl(self, parser: RuleEngineParser):
        # "内容包含'a'"
        text = "内容包含'a'"
        node = parser.parse_rule(text, mode="cnl")
        assert isinstance(node, Condition)
        assert node.field == FieldType.TEXT
        assert node.operator == OperatorType.CONTAINS
        assert node.value == "a"

    def test_chinese_punctuation(self, parser: RuleEngineParser):
        # Use full-width characters
        text = "（等级大于3）且（回复数小于5）"
        # Since '且' is valid logic AND in CNL
        node = parser.parse_rule(text, mode="cnl")
        assert isinstance(node, RuleGroup)
        assert node.logic == LogicType.AND

    def test_greedy_matching_prevention(self, parser: RuleEngineParser):
        text = '内容包含"a"'
        valid, _ = parser.validate(text, mode="cnl")
        assert valid

        text_fail = '内容包含包含"a"'
        # This checks that "包含" doesn't eagerly consume if it messes up structure
        # Or rather, duplicate operators like that are invalid syntax
        valid, _ = parser.validate(text_fail, mode="cnl")
        assert not valid

    def test_parse_raises_error(self, parser: RuleEngineParser):
        with pytest.raises(ValueError, match="Parsing failed"):
            parser.parse_rule("invalid rule syntax", mode="dsl")

    def test_parse_actions_raises_error(self, parser: RuleEngineParser):
        with pytest.raises(ValueError, match="Action parsing failed"):
            parser.parse_actions("invalid action syntax", mode="dsl")
