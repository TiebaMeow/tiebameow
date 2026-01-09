import pytest
from pydantic import ValidationError

from tiebameow.schemas.rules import (
    Action,
    ActionType,
    Condition,
    FieldType,
    LogicType,
    OperatorType,
    ReviewRule,
    RuleGroup,
    TargetType,
)


def test_condition_model() -> None:
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="spam")
    assert cond.field == FieldType.TEXT
    assert cond.operator == OperatorType.CONTAINS
    assert cond.value == "spam"


def test_rule_group_model() -> None:
    cond1 = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="spam")
    cond2 = Condition(field=FieldType.LEVEL, operator=OperatorType.LT, value=3)
    group = RuleGroup(logic=LogicType.AND, conditions=[cond1, cond2])
    assert group.logic == LogicType.AND
    assert len(group.conditions) == 2
    assert group.conditions[0] == cond1


def test_rule_group_nested() -> None:
    cond1 = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="spam")
    cond2 = Condition(field=FieldType.LEVEL, operator=OperatorType.LT, value=3)
    inner_group = RuleGroup(logic=LogicType.OR, conditions=[cond1, cond2])
    outer_group = RuleGroup(logic=LogicType.NOT, conditions=[inner_group])
    assert outer_group.logic == "NOT"
    assert len(outer_group.conditions) == 1
    assert isinstance(outer_group.conditions[0], RuleGroup)


def test_action_model() -> None:
    action = Action(type=ActionType.DELETE, params={"reason": "spam"})
    assert action.type == ActionType.DELETE
    assert action.params == {"reason": "spam"}

    action_default = Action(type=ActionType.BAN)
    assert action_default.type == ActionType.BAN
    assert action_default.params == {}


def test_review_rule_model() -> None:
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="bad")
    action = Action(type=ActionType.DELETE)
    rule = ReviewRule(
        id=1,
        fid=123,
        target_type=TargetType.ALL,
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=[action],
    )
    assert rule.id == 1
    assert rule.fid == 123
    assert rule.target_type == TargetType.ALL
    assert rule.trigger == cond
    assert len(rule.actions) == 1


def test_review_rule_target_type() -> None:
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="bad")
    action = Action(type=ActionType.DELETE)
    rule = ReviewRule(
        id=1,
        fid=123,
        target_type=TargetType.POST,
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=[action],
    )
    assert rule.target_type == TargetType.POST


def test_validate_trigger_compatibility() -> None:
    action = Action(type=ActionType.DELETE)

    # 1. Valid: Thread rule with thread-specific field
    cond_thread = Condition(field=FieldType.TITLE, operator=OperatorType.CONTAINS, value="t")
    rule = ReviewRule(
        id=1,
        fid=123,
        target_type=TargetType.THREAD,
        name="thread rule",
        enabled=True,
        priority=10,
        trigger=cond_thread,
        actions=[action],
    )
    assert rule.target_type == TargetType.THREAD

    # 2. Invalid: Post rule with thread-specific field (title)
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=2,
            fid=123,
            target_type=TargetType.POST,
            name="post rule",
            enabled=True,
            priority=10,
            trigger=cond_thread,
            actions=[action],
        )
    assert "Field 'title' is not valid for target_type 'post'" in str(exc.value)

    # 3. Invalid: Comment rule with reply_num (thread/post only)
    cond_reply = Condition(field=FieldType.REPLY_NUM, operator=OperatorType.GT, value=10)
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=3,
            fid=123,
            target_type=TargetType.COMMENT,
            name="comment rule",
            enabled=True,
            priority=10,
            trigger=cond_reply,
            actions=[action],
        )
    assert "Field 'reply_num' is not valid for target_type 'comment'" in str(exc.value)

    # 4. Valid: Comment rule with common field (text)
    cond_common = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="c")
    ReviewRule(
        id=4,
        fid=123,
        target_type=TargetType.COMMENT,
        name="common rule",
        enabled=True,
        priority=10,
        trigger=cond_common,
        actions=[action],
    )

    # 5. Invalid: All rule with thread-specific field
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=5,
            fid=123,
            target_type=TargetType.ALL,
            name="all rule",
            enabled=True,
            priority=10,
            trigger=cond_thread,
            actions=[action],
        )
    assert "Field 'title' is not valid for target_type 'all'" in str(exc.value)

    # 6. Nested Check
    group_invalid = RuleGroup(
        logic=LogicType.AND,
        conditions=[
            Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="a"),
            Condition(field=FieldType.TITLE, operator=OperatorType.CONTAINS, value="b"),  # Invalid for post
        ],
    )
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=6,
            fid=123,
            target_type=TargetType.POST,
            name="nested rule",
            enabled=True,
            priority=10,
            trigger=group_invalid,
            actions=[action],
        )
    assert "Field 'title' is not valid for target_type 'post'" in str(exc.value)
