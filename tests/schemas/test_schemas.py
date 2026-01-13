from typing import Any, cast

import pytest
from pydantic import ValidationError

from tiebameow.schemas.fragments import (
    FragAtModel,
    FragEmojiModel,
    FragImageModel,
    FragItemModel,
    FragLinkModel,
    FragTextModel,
    FragTiebaPlusModel,
    FragUnknownModel,
)
from tiebameow.schemas.rules import (
    Actions,
    BanAction,
    Condition,
    DeleteAction,
    FieldType,
    LogicType,
    NotifyAction,
    OperatorType,
    ReviewRule,
    RuleGroup,
    TargetType,
)

# --- Fragments Tests ---


def test_frag_text_model() -> None:
    model = FragTextModel(text="hello")
    assert model.type == "text"
    assert model.text == "hello"


def test_frag_at_model() -> None:
    model = FragAtModel(text="@user", user_id=123)
    assert model.type == "at"
    assert model.text == "@user"
    assert model.user_id == 123


def test_frag_image_model() -> None:
    model = FragImageModel(
        src="http://src",
        big_src="http://big",
        origin_src="http://origin",
        origin_size=100,
        show_width=100,
        show_height=100,
        hash="hash",
    )
    assert model.type == "image"
    assert model.src == "http://src"


def test_frag_link_model() -> None:
    model = FragLinkModel(text="http://link", title="title", raw_url="http://raw")
    assert model.type == "link"
    assert model.text == "http://link"

    # Test validator
    model_none = FragLinkModel(text="http://link", title="title", raw_url=cast("Any", None))
    assert model_none.raw_url == ""


def test_frag_emoji_model() -> None:
    model = FragEmojiModel(id="1", desc="smile")
    assert model.type == "emoji"
    assert model.id == "1"
    assert model.desc == "smile"


def test_frag_item_model() -> None:
    model = FragItemModel(text="item")
    assert model.type == "item"
    assert model.text == "item"


def test_frag_unknown_model() -> None:
    model = FragUnknownModel(raw_data="some data")
    assert model.type == "unknown"
    assert model.raw_data == "some data"


def test_fragment_union() -> None:
    t = FragTextModel(text="t")
    assert isinstance(t, FragTextModel)


def test_frag_tieba_plus_model_none_url():
    """Test FragTiebaPlusModel with None url."""
    model = FragTiebaPlusModel(url=None)  # type: ignore
    assert model.url == ""
    assert model.type == "tieba_plus"


def test_frag_tieba_plus_model_str_url():
    """Test FragTiebaPlusModel with string url."""
    model = FragTiebaPlusModel(url="http://example.com")
    assert model.url == "http://example.com"


# --- Rules Tests ---


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


def test_actions_model() -> None:
    actions = Actions(delete=DeleteAction(enabled=True))
    assert actions.delete.enabled is True
    assert actions.ban.enabled is False

    actions = Actions(ban=BanAction(enabled=True, days=3))
    assert actions.delete.enabled is False
    assert actions.ban.enabled is True
    assert actions.ban.days == 3

    actions = Actions(notify=NotifyAction(enabled=True, template="tmpl", params={"a": 1}))
    assert actions.notify.enabled is True
    assert actions.notify.template == "tmpl"
    assert actions.notify.params == {"a": 1}


def test_review_rule_model() -> None:
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="bad")
    actions = Actions(delete=DeleteAction(enabled=True))
    rule = ReviewRule(
        id=1,
        fid=123,
        forum_rule_id=1,
        uploader_id=456,
        target_type=TargetType.ALL,
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=actions,
    )
    assert rule.id == 1
    assert rule.fid == 123
    assert rule.target_type == TargetType.ALL
    assert rule.trigger == cond
    assert rule.actions.delete.enabled is True


def test_review_rule_target_type() -> None:
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="bad")
    actions = Actions(delete=DeleteAction(enabled=True))
    rule = ReviewRule(
        id=1,
        fid=123,
        forum_rule_id=1,
        uploader_id=456,
        target_type=TargetType.POST,
        name="test rule",
        enabled=True,
        priority=10,
        trigger=cond,
        actions=actions,
    )
    assert rule.target_type == TargetType.POST


def test_validate_trigger_compatibility() -> None:
    actions = Actions(delete=DeleteAction(enabled=True))

    # 1. Valid: Thread rule with thread-specific field
    cond_thread = Condition(field=FieldType.TITLE, operator=OperatorType.CONTAINS, value="t")
    rule = ReviewRule(
        id=1,
        fid=123,
        forum_rule_id=1,
        uploader_id=456,
        target_type=TargetType.THREAD,
        name="thread rule",
        enabled=True,
        priority=10,
        trigger=cond_thread,
        actions=actions,
    )
    assert rule.target_type == TargetType.THREAD

    # 2. Invalid: Post rule with thread-specific field (title)
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=2,
            fid=123,
            forum_rule_id=2,
            uploader_id=456,
            target_type=TargetType.POST,
            name="post rule",
            enabled=True,
            priority=10,
            trigger=cond_thread,
            actions=actions,
        )
    assert "Field 'title' is not valid for target_type 'post'" in str(exc.value)

    # 3. Invalid: Comment rule with reply_num (thread/post only)
    cond_reply = Condition(field=FieldType.REPLY_NUM, operator=OperatorType.GT, value=10)
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=3,
            fid=123,
            forum_rule_id=3,
            uploader_id=456,
            target_type=TargetType.COMMENT,
            name="comment rule",
            enabled=True,
            priority=10,
            trigger=cond_reply,
            actions=actions,
        )
    assert "Field 'reply_num' is not valid for target_type 'comment'" in str(exc.value)

    # 4. Valid: Comment rule with common field (text)
    cond_common = Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="c")
    ReviewRule(
        id=4,
        fid=123,
        forum_rule_id=4,
        uploader_id=456,
        target_type=TargetType.COMMENT,
        name="common rule",
        enabled=True,
        priority=10,
        trigger=cond_common,
        actions=actions,
    )

    # 5. Invalid: All rule with thread-specific field
    with pytest.raises(ValidationError) as exc:
        ReviewRule(
            id=5,
            fid=123,
            forum_rule_id=5,
            uploader_id=456,
            target_type=TargetType.ALL,
            name="all rule",
            enabled=True,
            priority=10,
            trigger=cond_thread,
            actions=actions,
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
            forum_rule_id=6,
            uploader_id=456,
            target_type=TargetType.POST,
            name="nested rule",
            enabled=True,
            priority=10,
            trigger=group_invalid,
            actions=actions,
        )
    assert "Field 'title' is not valid for target_type 'post'" in str(exc.value)
