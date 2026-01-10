from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tiebameow.parser.rule_parser import RuleEngineParser
from tiebameow.schemas.rules import Condition, FieldType, RuleGroup

# Re-import SHANGHAI_TZ from utils to ensure consistency
from tiebameow.utils.time_utils import SHANGHAI_TZ


@pytest.fixture
def parser():
    return RuleEngineParser()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2023, 10, 1, 12, 0, 0, tzinfo=SHANGHAI_TZ)


@pytest.fixture(autouse=True)
def mock_now(monkeypatch, fixed_now):
    # Mock the now_with_tz function in rule_parser module so that logic uses our fixed time
    monkeypatch.setattr("tiebameow.parser.rule_parser.now_with_tz", lambda: fixed_now)


class TestRuleParserDatetime:
    def test_iso_dates_tz_aware(self, parser: RuleEngineParser, fixed_now):
        # 1. Full datetime
        rule = "create_time > '2023-01-01 10:00:00'"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert isinstance(node.value, datetime)
        # Check timezone
        assert node.value.tzinfo is not None
        # It should use the implementation's timezone (Shanghai)
        # 2023-01-01 10:00:00 assuming it's in local/default interpretation which we set to Shanghai in parser
        expected = datetime(2023, 1, 1, 10, 0, 0).replace(tzinfo=SHANGHAI_TZ)
        assert node.value == expected

        # 2. Date only
        rule = "create_time > '2023-01-02'"
        node = parser.parse_rule(rule, mode="dsl")
        expected = datetime(2023, 1, 2, 0, 0, 0).replace(tzinfo=SHANGHAI_TZ)
        assert isinstance(node, Condition)
        assert isinstance(node.value, datetime)
        assert node.value == expected

    def test_relative_dsl(self, parser: RuleEngineParser, fixed_now):
        # fixed_now = 2023-10-01 12:00:00

        # 1d = 2023-09-30 12:00:00
        rule = "create_time > 1d"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert isinstance(node.value, datetime)
        assert node.value == fixed_now - timedelta(days=1)

        # 2h
        rule = "create_time < 2h"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(hours=2)

        # 30m
        rule = "create_time == 30m"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(minutes=30)

        # 10s
        rule = "create_time == 10s"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now - timedelta(seconds=10)

    def test_absolute_cnl(self, parser: RuleEngineParser, fixed_now):
        # fixed_now = 2023-10-01 12:00:00

        cases = [
            ("发贴时间大于 2023年1月1日 0时0分0秒", datetime(2023, 1, 1, 0, 0, 0, tzinfo=SHANGHAI_TZ)),
            ("创建时间大于2023年09月30日 12时00分00秒", datetime(2023, 9, 30, 12, 0, 0, tzinfo=SHANGHAI_TZ)),
            ("创建时间小于 2023年10月01日", datetime(2023, 10, 1, 0, 0, 0, tzinfo=SHANGHAI_TZ)),
            ("创建时间等于2023-09-29 08:30:15", datetime(2023, 9, 29, 8, 30, 15, tzinfo=SHANGHAI_TZ)),
            ("创建时间等于 2023-09-28", datetime(2023, 9, 28, 0, 0, 0, tzinfo=SHANGHAI_TZ)),
        ]

        for text, expected_dt in cases:
            node = parser.parse_rule(text, mode="cnl")
            assert isinstance(node, Condition), f"Failed for {text}"
            assert isinstance(node.value, datetime), f"Failed for {text}"
            assert node.value == expected_dt, f"Failed for {text}"

    def test_relative_cnl(self, parser: RuleEngineParser, fixed_now):
        # fixed_now = 2023-10-01 12:00:00

        cases = [
            ("创建时间大于1天", timedelta(days=1)),
            ("创建时间大于 1 天", timedelta(days=1)),
            ("创建时间大于1天前", timedelta(days=1)),
            ("创建时间大于 2 小时", timedelta(hours=2)),
            ("创建时间大于30 分钟 前", timedelta(minutes=30)),
        ]

        for text, delta in cases:
            node = parser.parse_rule(text, mode="cnl")
            assert isinstance(node, Condition), f"Failed for {text}"
            assert isinstance(node.value, datetime), f"Failed for {text}"
            assert node.value == fixed_now - delta

    def test_now_keyword(self, parser: RuleEngineParser, fixed_now):
        rule = "create_time < NOW"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now

        # Case insensitive
        rule = "create_time < now"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert node.value == fixed_now

    def test_complex_rule_with_datetime(self, parser: RuleEngineParser, fixed_now):
        # (create_time > 1d AND level > 5)
        rule = "(create_time > 1d AND author.level > 5)"
        node = parser.parse_rule(rule, mode="dsl")

        assert isinstance(node, RuleGroup)

        dt_cond = node.conditions[0]  # create_time > 1d
        assert isinstance(dt_cond, Condition)
        assert dt_cond.field == FieldType.CREATE_TIME
        assert dt_cond.value == fixed_now - timedelta(days=1)

        lvl_cond = node.conditions[1]
        assert isinstance(lvl_cond, Condition)
        assert lvl_cond.field == FieldType.LEVEL
        assert lvl_cond.value == 5

    def test_list_contains_datetime(self, parser: RuleEngineParser, fixed_now):
        # create_time in [1d, 2d]
        rule = "create_time in [1d, 2d]"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert isinstance(node.value, list)
        assert node.value[0] == fixed_now - timedelta(days=1)
        assert node.value[1] == fixed_now - timedelta(days=2)

    def test_invalid_formats(self, parser: RuleEngineParser):
        # Should fallback to string or fail
        with pytest.raises(ValueError, match="Parsing failed"):
            parser.parse_rule("create_time == 10x", mode="dsl")

    def test_partial_match_prevention(self, parser: RuleEngineParser):
        # Ensure "1d" is parsed as 1 day, not 1 and then error
        rule = "create_time == 1d"
        node = parser.parse_rule(rule, mode="dsl")
        assert isinstance(node, Condition)
        assert isinstance(node.value, datetime)

    def test_cnl_ambiguity(self, parser: RuleEngineParser):
        # Ensure units are parsed correctly even if surrounded by spaces
        rule = "创建时间 等于 1 天"
        node = parser.parse_rule(rule, mode="cnl")
        assert isinstance(node, Condition)
        assert isinstance(node.value, datetime)

    def test_complex_cnl(self, parser: RuleEngineParser, fixed_now):
        rule = "发贴时间大于1天前且（发贴时间小于NOW并且用户等级大于5）"
        node = parser.parse_rule(rule, mode="cnl")

        assert isinstance(node, RuleGroup)
        dt_cond1 = node.conditions[0]  # 发贴时间大于1天前
        assert isinstance(dt_cond1, Condition)
        assert dt_cond1.field == FieldType.CREATE_TIME
        assert dt_cond1.value == fixed_now - timedelta(days=1)

        subgroup = node.conditions[1]
        assert isinstance(subgroup, RuleGroup)

        dt_cond2 = subgroup.conditions[0]  # 发贴时间小于NOW
        assert isinstance(dt_cond2, Condition)
        assert dt_cond2.value == fixed_now

        lvl_cond = subgroup.conditions[1]  # 用户等级大于5
        assert isinstance(lvl_cond, Condition)
        assert lvl_cond.field == FieldType.LEVEL
        assert lvl_cond.value == 5
