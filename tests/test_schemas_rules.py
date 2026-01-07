from tiebameow.schemas.rules import Action, Condition, ReviewRule, RuleGroup


def test_condition_model() -> None:
    cond = Condition(field="content", operator="contains", value="spam")
    assert cond.field == "content"
    assert cond.operator == "contains"
    assert cond.value == "spam"


def test_rule_group_model() -> None:
    cond1 = Condition(field="content", operator="contains", value="spam")
    cond2 = Condition(field="author.level", operator="lt", value=3)
    group = RuleGroup(logic="AND", conditions=[cond1, cond2])
    assert group.logic == "AND"
    assert len(group.conditions) == 2
    assert group.conditions[0] == cond1


def test_rule_group_nested() -> None:
    cond1 = Condition(field="content", operator="contains", value="spam")
    cond2 = Condition(field="author.level", operator="lt", value=3)
    inner_group = RuleGroup(logic="OR", conditions=[cond1, cond2])
    outer_group = RuleGroup(logic="NOT", conditions=[inner_group])

    assert outer_group.logic == "NOT"
    assert len(outer_group.conditions) == 1
    assert isinstance(outer_group.conditions[0], RuleGroup)


def test_action_model() -> None:
    action = Action(type="delete", params={"reason": "spam"})
    assert action.type == "delete"
    assert action.params == {"reason": "spam"}

    action_default = Action(type="ban")
    assert action_default.type == "ban"
    assert action_default.params == {}


def test_review_rule_model() -> None:
    cond = Condition(field="content", operator="contains", value="bad")
    action = Action(type="delete")
    rule = ReviewRule(
        id=1,
        fid=123,
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=[action],
    )
    assert rule.id == 1
    assert rule.fid == 123
    assert rule.target_type == "all"
    assert rule.trigger == cond
    assert len(rule.actions) == 1


def test_review_rule_target_type() -> None:
    cond = Condition(field="content", operator="contains", value="bad")
    action = Action(type="delete")
    rule = ReviewRule(
        id=1,
        fid=123,
        target_type="post",
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=[action],
    )
    assert rule.target_type == "post"
