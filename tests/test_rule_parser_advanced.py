import pytest

from tiebameow.parser.rule_parser import RuleEngineParser, TokenMap
from tiebameow.schemas.rules import (
    Condition,
    FieldType,
    LogicType,
    OperatorType,
    RuleGroup,
)


@pytest.fixture
def parser() -> RuleEngineParser:
    return RuleEngineParser()


class TestRuleParserAdvanced:
    # --- TokenMap & Config Tests ---

    def test_token_map_errors(self):
        # Test getting primary token for unknown key
        tm = TokenMap({FieldType.TITLE: "title"})
        with pytest.raises(ValueError, match=f"No tokens defined for {FieldType.IS_GOOD}"):
            tm.get_primary_token(FieldType.IS_GOOD)  # Not in map

        with pytest.raises(ValueError, match=f"No tokens configured for {FieldType.IS_GOOD}"):
            tm.get_parser_element(FieldType.IS_GOOD)

    # --- Dump Tests in Depth ---

    def test_dump_bool_values(self, parser: RuleEngineParser):
        # DSL
        c = Condition(field=FieldType.IS_GOOD, operator=OperatorType.EQ, value=True)
        dumped = parser.dump_rule(c, mode="dsl")
        assert "is_good==true" in dumped.replace(" ", "")

        c = Condition(field=FieldType.IS_GOOD, operator=OperatorType.EQ, value=False)
        dumped = parser.dump_rule(c, mode="dsl")
        assert "is_good==false" in dumped.replace(" ", "")

        # CNL
        c = Condition(field=FieldType.IS_GOOD, operator=OperatorType.EQ, value=True)
        dumped = parser.dump_rule(c, mode="cnl")
        # '加精等于真' or similar
        assert "加精等于真" in dumped

    def test_dump_list_values(self, parser: RuleEngineParser):
        # DSL Strings
        c = Condition(field=FieldType.USER_ID, operator=OperatorType.IN, value=["a", "b"])
        dumped = parser.dump_rule(c, mode="dsl")
        # In DSL it uses [ ]
        assert '["a", "b"]' in dumped or "['a', 'b']" in dumped

        # DSL Numbers
        c = Condition(field=FieldType.LEVEL, operator=OperatorType.IN, value=[1, 2])
        dumped = parser.dump_rule(c, mode="dsl")
        assert "[1, 2]" in dumped

        # CNL - Uses primary token for LBRACK which is '[' in COMMON_PUNCT
        c = Condition(field=FieldType.LEVEL, operator=OperatorType.IN, value=[1, 2])
        dumped = parser.dump_rule(c, mode="cnl")
        assert "[1, 2]" in dumped

    def test_dump_logic_not(self, parser: RuleEngineParser):
        c = Condition(field=FieldType.TITLE, operator=OperatorType.CONTAINS, value="x")
        g = RuleGroup(logic=LogicType.NOT, conditions=[c])

        dumped = parser.dump_rule(g, mode="dsl")
        assert "NOT" in dumped
        assert "(" in dumped

        dumped_cnl = parser.dump_rule(g, mode="cnl")
        assert "非" in dumped_cnl

    def test_dump_unknown_node(self, parser: RuleEngineParser):
        with pytest.raises(ValueError, match="Unknown node type"):
            parser.dump_rule("not a node", mode="dsl")  # type: ignore

    def test_dump_unknown_field_graceful(self, parser: RuleEngineParser):
        # Bypass validation to test dump robustness
        c = Condition.model_construct(field="custom_field", operator=OperatorType.EQ, value=1)
        dumped = parser.dump_rule(c, mode="dsl")
        # Should fallback to using the string directly
        assert "custom_field==1" in dumped.replace(" ", "")

    # --- Scanning & Edge Parsing ---

    def test_scan_rules_mixed(self, parser: RuleEngineParser):
        # Use valid field names for DSL
        text = "bla bla title=='x' bla (author.level>5)"
        nodes = list(parser.scan_rules(text, "dsl"))
        assert len(nodes) >= 2
        assert isinstance(nodes[0], Condition)
        assert nodes[0].field == FieldType.TITLE
        # checking the group/condition
        # The second one might be parsed as a Group(Condition) due to parens or just Condition logic depending on Parser
        # scan_rules yields whatever parse_string matches.
        # (author.level>5) matches parentheses group logic.
        node2 = nodes[1]

        val = None
        if isinstance(node2, Condition):
            val = node2.value
        elif isinstance(node2, RuleGroup) and len(node2.conditions) > 0:
            # Just checking deep value to confirm it parsed
            cond = node2.conditions[0]
            if isinstance(cond, Condition):
                val = cond.value

        assert val == 5

    def test_parse_error_details(self, parser: RuleEngineParser):
        with pytest.raises(ValueError) as exc:  # noqa: PT011
            parser.parse_rule("title contains", mode="dsl")
        assert "Parsing failed at position" in str(exc.value)

    def test_to_rule_node_errors(self, parser: RuleEngineParser):
        # Directly invoking internal methods to force errors hard to reach via parser
        from tiebameow.parser.rule_parser import DSL_CONFIG

        # Unknown op
        item = {"field": "title", "op": "unknown_op", "val": "x"}
        with pytest.raises(ValueError, match="Unknown operator"):
            parser._to_rule_node(item, DSL_CONFIG)

        # Unknown field strict check
        item = {"field": "bad_field", "op": "==", "val": "x"}
        with pytest.raises(ValueError, match="Unknown field"):
            parser._to_rule_node(item, DSL_CONFIG)

    def test_parse_actions_errors(self, parser: RuleEngineParser):
        with pytest.raises(ValueError, match="Action parsing failed"):
            parser.parse_actions("INVALID: syntax", mode="dsl")

    def test_to_actions_errors(self, parser: RuleEngineParser):
        from tiebameow.parser.rule_parser import DSL_CONFIG

        # Test internal conversion with bad type
        # Mock item structure
        class MockItem:
            type = "bad_action"

            class Params:
                def as_dict(self):
                    return {}

            params = Params()

        with pytest.raises(ValueError, match="Unknown action type"):
            # We need to simulate the structure pyparsing returns which is iterable
            parser._to_actions([MockItem()], DSL_CONFIG)
