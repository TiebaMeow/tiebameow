from __future__ import annotations

import math
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from tiebameow.parser.rule_parser import DSL_CONFIG, Condition, RuleEngineParser, RuleGroup, TokenMap
from tiebameow.schemas.rules import (
    Action,
    ActionType,
    FieldType,
    LogicType,
    OperatorType,
)
from tiebameow.utils.time_utils import SHANGHAI_TZ


@pytest.fixture
def parser():
    return RuleEngineParser()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2023, 10, 1, 12, 0, 0, tzinfo=SHANGHAI_TZ)


@pytest.fixture
def mock_now(monkeypatch, fixed_now):
    # Mock the now_with_tz function in rule_parser module
    monkeypatch.setattr("tiebameow.parser.rule_parser.now_with_tz", lambda: fixed_now)


class TestRuleEngineParserBasic:
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
        assert node.field == FieldType.TITLE
        assert node.operator == OperatorType.CONTAINS
        assert node.value == "你好"

    def test_parse_cnl_synonyms(self, parser: RuleEngineParser):
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
        text = "(title contains 'A' AND title contains 'B') OR NOT title contains 'C'"
        node = parser.parse_rule(text, mode="dsl")
        assert isinstance(node, RuleGroup)
        assert node.logic == LogicType.OR
        assert len(node.conditions) == 2

        left = node.conditions[0]
        assert isinstance(left, RuleGroup)
        assert left.logic == LogicType.AND
        assert len(left.conditions) == 2

        right = node.conditions[1]
        assert isinstance(right, RuleGroup)
        assert right.logic == LogicType.NOT
        assert len(right.conditions) == 1

    def test_cnl_logic(self, parser: RuleEngineParser):
        text = "标题包含'A'并且(等级大于5或者回复数小于10)"
        node = parser.parse_rule(text, mode="cnl")
        assert isinstance(node, RuleGroup)
        assert node.logic == LogicType.AND
        assert len(node.conditions) == 2

        group2 = node.conditions[1]
        assert isinstance(group2, RuleGroup)
        assert group2.logic == LogicType.OR

    # === 3. Value Parsing Tests ===

    def test_parse_values_types(self, parser: RuleEngineParser):
        # String
        r1 = parser.parse_rule("text == 'foo'", "dsl")
        assert isinstance(r1, Condition)
        assert r1.value == "foo"
        # Integer
        r2 = parser.parse_rule("agree_num == 42", "dsl")
        assert isinstance(r2, Condition)
        assert r2.value == 42
        # Float
        r3 = parser.parse_rule("agree_num == 3.45", "dsl")
        assert isinstance(r3, Condition)
        assert math.isclose(r3.value, 3.45)
        # Bool
        r4 = parser.parse_rule("is_good == false", "dsl")
        assert isinstance(r4, Condition)
        assert r4.value is False
        # CNL Bool
        r5 = parser.parse_rule("加精等于真", "cnl")
        assert isinstance(r5, Condition)
        assert r5.value is True
        # List
        r6 = parser.parse_rule("title in ['a', 'b']", "dsl")
        assert isinstance(r6, Condition)
        assert r6.value == ["a", "b"]
        r7 = parser.parse_rule("标题属于['x', 'y']", "cnl")
        assert isinstance(r7, Condition)
        assert r7.value == ["x", "y"]
        r8 = parser.parse_rule("author.user_id in [1, 'a']", "dsl")
        assert isinstance(r8, Condition)
        assert r8.value == [1, "a"]
        r9 = parser.parse_rule("user_id属于【1, 2】", "cnl")
        assert isinstance(r9, Condition)
        assert r9.value == [1, 2]

    # === 4. Validation & Actions ===

    def test_validate(self, parser: RuleEngineParser):
        assert parser.validate("title contains 'test'", mode="dsl")[0]
        assert not parser.validate("title contains", mode="dsl")[0]
        assert not parser.validate("未知字段等于1", mode="cnl")[0]

    def test_parse_actions(self, parser: RuleEngineParser):
        dsl_text = "DO: delete(reason='bad'), ban(day=1)"
        actions = parser.parse_actions(dsl_text, mode="dsl")
        assert len(actions) == 2
        assert actions[0].type == ActionType.DELETE
        assert actions[1].type == ActionType.BAN

        cnl_text = "执行：删除(reason='广告'), 封禁（days=3）"
        actions_cnl = parser.parse_actions(cnl_text, mode="cnl")
        assert len(actions_cnl) == 2
        assert actions_cnl[0].type == ActionType.DELETE

    # === 5. Dump & Scan ===

    def test_dump_rule(self, parser: RuleEngineParser):
        original = "(title contains 'A' AND author.level > 5)"
        node = parser.parse_rule(original, mode="dsl")
        dumped = parser.dump_rule(node, mode="dsl")
        node2 = parser.parse_rule(dumped, mode="dsl")
        assert node == node2

    def test_scan_rules(self, parser: RuleEngineParser):
        text = 'Rule 1: title contains "spam"\nRule 2: (author.level < 3)'
        rules = list(parser.scan_rules(text, mode="dsl"))
        assert len(rules) == 2
        assert isinstance(rules[0], Condition)
        assert rules[0].value == "spam"


class TestRuleParserAdvancedAndConfig:
    def test_token_map_errors(self):
        tm = TokenMap({FieldType.TITLE: "title"})
        with pytest.raises(ValueError, match="No tokens defined"):
            tm.get_primary_token(FieldType.IS_GOOD)

    def test_dump_bool_and_list(self, parser: RuleEngineParser):
        c = Condition(field=FieldType.IS_GOOD, operator=OperatorType.EQ, value=True)
        assert "is_good==true" in parser.dump_rule(c, mode="dsl").replace(" ", "")

        c2 = Condition(field=FieldType.LEVEL, operator=OperatorType.IN, value=[1, 2])
        assert "[1, 2]" in parser.dump_rule(c2, mode="dsl")
        assert "[1, 2]" in parser.dump_rule(c2, mode="cnl")

    def test_dump_unknown_node(self, parser: RuleEngineParser):
        with pytest.raises(ValueError, match="Unknown node type"):
            parser.dump_rule("not a node", mode="dsl")  # type: ignore

    def test_dump_unknown_field_graceful(self, parser: RuleEngineParser):
        # Bypass validation to test dump robustness
        c = Condition.model_construct(field="custom_field", operator=OperatorType.EQ, value=1)
        dumped = parser.dump_rule(c, mode="dsl")
        # Should fallback to using the string directly
        assert "custom_field==1" in dumped.replace(" ", "")


class TestRuleParserDatetime:
    @pytest.mark.usefixtures("mock_now")
    def test_iso_dates_tz_aware(self, parser: RuleEngineParser):
        rule = "create_time > '2023-01-01 10:00:00'"
        node = parser.parse_rule(rule, mode="dsl")
        expected = datetime(2023, 1, 1, 10, 0, 0, tzinfo=SHANGHAI_TZ)
        assert isinstance(node, Condition)
        assert node.value == expected

    @pytest.mark.usefixtures("mock_now")
    def test_relative_dsl(self, parser: RuleEngineParser, fixed_now):
        # create_time > 1d
        node = parser.parse_rule("create_time > 1d", mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(days=1)
        # create_time == 30m
        node = parser.parse_rule("create_time == 30m", mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(minutes=30)

    @pytest.mark.usefixtures("mock_now")
    def test_cnl_dates(self, parser: RuleEngineParser, fixed_now):
        # Absolute
        rule = "发贴时间大于 2023年1月1日 0时0分0秒"
        node = parser.parse_rule(rule, mode="cnl")
        assert isinstance(node, Condition)
        assert node.value == datetime(2023, 1, 1, 0, 0, 0, tzinfo=SHANGHAI_TZ)

        # Relative
        rule = "创建时间大于1天"
        node = parser.parse_rule(rule, mode="cnl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(days=1)

    @pytest.mark.usefixtures("mock_now")
    def test_now_keyword(self, parser: RuleEngineParser, fixed_now):
        node = parser.parse_rule("create_time < NOW", mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now

    def test_dump_datetime(self, parser: RuleEngineParser):
        dt = datetime(2023, 1, 1, 0, 0, 0)
        cond = Condition(field=FieldType.CREATE_TIME, operator=OperatorType.GT, value=dt)
        assert "2023-01-01" in parser.dump_rule(cond, mode="dsl")


class TestRuleParserEdgeCasesAndCoverage:
    def test_unknown_field_internal(self, parser: RuleEngineParser):
        fake_parsed_item = {"field": "InvalidField", "op": "==", "val": 1}
        with pytest.raises(ValueError, match="Unknown field"):
            parser._to_rule_node(fake_parsed_item, DSL_CONFIG)

    def test_unknown_operator_internal(self, parser: RuleEngineParser):
        item = {"field": "title", "op": "UnknownOp", "val": 1}
        with pytest.raises(ValueError, match="Unknown operator"):
            parser._to_rule_node(item, DSL_CONFIG)

    def test_single_item_fallback(self, parser: RuleEngineParser):
        cond_item = {"field": "title", "op": "contains", "val": "test"}
        res = parser._to_rule_node([cond_item], DSL_CONFIG)
        assert isinstance(res, Condition)
        assert res.value == "test"

    def test_convert_fragment_unknown(self):
        # Testing convert_fragment in isolation if needed, but this is rule parser.
        # This seems to belong to Parser coverage, but if it was in test_rule_parser_coverage, maybe it was misplaced?
        # Checking file content... test_parser_coverage.py had convert_aiotieba_fragment.
        # test_rule_parser_coverage.py had test_rule_parser_unknown_field etc.
        pass

    def test_scan_rules_exception(self, parser: RuleEngineParser):
        # Middle one fails
        text = "title == 'a'   UnknownField == 1   title == 'b'"
        rules = list(parser.scan_rules(text, mode="dsl"))
        assert len(rules) == 2
        assert isinstance(rules[0], Condition)
        assert rules[0].value == "a"
        assert isinstance(rules[1], Condition)
        assert rules[1].value == "b"

    def test_to_actions_errors(self, parser: RuleEngineParser):
        class MockItem:
            type = "bad_action"

            class Params:
                def as_dict(self):
                    return {}

            params = Params()

        with pytest.raises(ValueError, match="Unknown action type"):
            # We need to simulate the structure pyparsing returns which is iterable
            # NOTE: internal _to_actions expects list of parsed objects
            parser._to_actions([MockItem()], DSL_CONFIG)

    def test_token_map_get_parser_element_error(self):
        from tiebameow.parser.rule_parser import TokenMap

        tm = TokenMap({FieldType.TITLE: []})
        with pytest.raises(ValueError, match="No tokens configured"):
            tm.get_parser_element(FieldType.TITLE)

    @pytest.mark.usefixtures("mock_now")
    def test_relative_time_seconds_cnl(self, parser: RuleEngineParser, fixed_now):
        rule = "创建时间大于30秒"
        node = parser.parse_rule(rule, mode="cnl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(seconds=30)
        rule2 = "发贴时间小于15时"
        node2 = parser.parse_rule(rule2, mode="cnl")
        assert isinstance(node2, Condition)
        assert node2.value == fixed_now - timedelta(hours=15)

    def test_to_rule_node_list_compat(self, parser):
        item = {"field": ["title"], "op": ["=="], "val": "test"}
        node = parser._to_rule_node(item, DSL_CONFIG)
        assert isinstance(node, Condition)
        assert node.field == FieldType.TITLE
        assert node.operator == OperatorType.EQ

    def test_to_rule_node_unknown_logic(self, parser):
        item1 = {"field": "title", "op": "==", "val": "a"}
        item2 = {"field": "title", "op": "==", "val": "b"}
        group_item = [item1, "UNKNOWN_LOGIC", item2]
        with pytest.raises(ValueError, match="Unknown logic operator"):
            parser._to_rule_node(group_item, DSL_CONFIG)

    def test_to_rule_node_unexpected(self, parser):
        with pytest.raises(ValueError, match="Unexpected parse item"):
            parser._to_rule_node("GARBAGE", DSL_CONFIG)

    def test_dump_rule_string_value(self, parser):
        cond = Condition(field=FieldType.TITLE, operator=OperatorType.EQ, value="foo")
        res = parser.dump_rule(cond, mode="dsl")
        assert 'title=="foo"' in res.replace(" ", "")

    def test_dump_rule_list_strings(self, parser):
        cond = Condition(field=FieldType.TITLE, operator=OperatorType.IN, value=["a", "b"])
        res = parser.dump_rule(cond, mode="dsl")
        assert '["a", "b"]' in res or "['a', 'b']" in res

    def test_dump_actions_full(self, parser):
        actions = [
            Action(type=ActionType.DELETE, params={"reason": "foo"}),
            Action(type=ActionType.BAN, params={"day": 7}),
        ]
        dumped = parser.dump_actions(actions, mode="dsl")
        # standardize quotes for checking
        dumped_fixed = dumped.replace("'", '"')
        assert "DO:" in dumped_fixed
        assert 'delete(reason="foo")' in dumped_fixed
        assert "ban(day=7)" in dumped_fixed

    def test_parse_actions_error(self, parser):
        from pyparsing import ParseException

        # We need to reach the line where parse_string is called.
        # parser._parsers["dsl"][1] is the action parser.
        action_parser = parser._parsers["dsl"][1]

        with patch.object(action_parser, "parse_string", side_effect=ParseException("fail")):
            with pytest.raises(ValueError, match="Action parsing failed"):
                parser.parse_actions("bad input", mode="dsl")
