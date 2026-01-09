"""
Tests for RuleEngineParser with advanced features and error handling.
"""

from __future__ import annotations

import pytest

from tiebameow.parser.rule_parser import RuleEngineParser
from tiebameow.schemas.rules import (
    Condition,
)


@pytest.fixture
def parser():
    """Fixture for RuleEngineParser."""
    return RuleEngineParser()


class TestRuleParserAdvanced:
    """Test suite for advanced parser features explicitly requested."""

    def test_boolean_config_dsl(self, parser: RuleEngineParser):
        """Test configurable booleans in DSL mode."""
        # Standard boolean
        rule_true = parser.parse_rule("is_good == true", mode="dsl")
        assert isinstance(rule_true, Condition)
        assert rule_true.value is True

        rule_false = parser.parse_rule("is_good == false", mode="dsl")
        assert isinstance(rule_false, Condition)
        assert sizeof(rule_false.value) == sizeof(False)  # check strictly? value is boolean
        assert rule_false.value is False

    def test_boolean_config_cnl(self, parser: RuleEngineParser):
        """Test configurable booleans in CNL mode (Custom config applied)."""
        # Chinese boolean "真"
        rule_zhen = parser.parse_rule("精华帖 等于 真", mode="cnl")
        assert isinstance(rule_zhen, Condition)
        assert rule_zhen.value is True

        # Chinese boolean "否"
        rule_fou = parser.parse_rule("精华帖 等于 否", mode="cnl")
        assert isinstance(rule_fou, Condition)
        assert rule_fou.value is False

        # Mixed English in CNL (as configured)
        rule_true = parser.parse_rule("精华帖 等于 true", mode="cnl")
        assert isinstance(rule_true, Condition)
        assert rule_true.value is True

    def test_error_reporting_visualization(self, parser: RuleEngineParser):
        """Test enhanced error reporting with visual indicators."""
        invalid_rule = "level > 10 AND"  # Missing right operand

        with pytest.raises(ValueError, match=r"position") as excinfo:
            parser.parse_rule(invalid_rule, mode="dsl")

        error_msg = str(excinfo.value)
        # Should contain the line content
        assert "level > 10 AND" in error_msg
        # Should contain the pointer ^
        assert "^" in error_msg
        # Should indicate position
        assert "position" in error_msg

    def test_round_trip_stability(self, parser: RuleEngineParser):
        """
        Property-based like test: parse -> dump -> parse -> equal.
        Ensures serializer and parser are in sync.
        """
        # Note: Must use defined FieldType enum values for DSL (e.g. author.user_id)
        original_texts = [
            "author.user_id == 12345",
            "(author.level > 3 OR is_good == true) AND reply_num >= 100",
            "title contains 'spam'",
            "NOT (view_num < 50)",
        ]

        for text in original_texts:
            # 1. Parse original
            ast1 = parser.parse_rule(text, mode="dsl")

            # 2. Dump
            dumped_text = parser.dump_rule(ast1, mode="dsl")

            # 3. Parse dumped text
            ast2 = parser.parse_rule(dumped_text, mode="dsl")

            # 4. Compare ASTs
            assert ast1 == ast2, f"Round trip failed for: {text} -> {dumped_text}"


def sizeof(obj):
    return obj.__sizeof__()
