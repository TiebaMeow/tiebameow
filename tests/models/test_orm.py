from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from tiebameow.models.dto import BaseUserDTO, CommentDTO, PostDTO, ThreadDTO
from tiebameow.models.orm import (
    ActionsType,
    Comment,
    Fragment,
    FragmentListType,
    MixinBase,
    Post,
    ReviewRules,
    RuleBase,
    RuleNodeType,
    Thread,
    User,
)
from tiebameow.schemas.fragments import FragImageModel, FragTextModel
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

# --- ORM Base Setup for Testing ---


class Base(DeclarativeBase):
    pass


class ORMTestModel(Base):
    __tablename__ = "test_model"
    id: Mapped[int] = mapped_column(primary_key=True)
    contents: Mapped[list[Fragment]] = mapped_column(FragmentListType())


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    RuleBase.metadata.create_all(engine)  # Create table for RuleDBModel and others inherited from RuleBase
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


# --- Custom Type & Integration Tests ---


def test_fragment_list_type(session: Session) -> None:
    # Create data
    fragments = [
        FragTextModel(text="hello"),
        FragImageModel(
            src="src", big_src="big", origin_src="origin", origin_size=100, show_width=100, show_height=100, hash="hash"
        ),
    ]
    obj = ORMTestModel(contents=fragments)
    session.add(obj)
    session.commit()

    # Read data
    loaded_obj = session.execute(select(ORMTestModel)).scalar_one()
    assert len(loaded_obj.contents) == 2
    assert isinstance(loaded_obj.contents[0], FragTextModel)
    assert loaded_obj.contents[0].text == "hello"
    assert isinstance(loaded_obj.contents[1], FragImageModel)
    assert loaded_obj.contents[1].src == "src"


def test_fragment_list_type_empty(session: Session) -> None:
    obj = ORMTestModel(contents=[])
    session.add(obj)
    session.commit()

    loaded_obj = session.execute(select(ORMTestModel)).scalar_one()
    assert loaded_obj.contents == []


def test_fragment_list_type_none(session: Session) -> None:
    type_impl = FragmentListType()
    dialect: Any = None
    assert type_impl.process_bind_param(None, dialect) is None
    assert type_impl.process_result_value(None, dialect) is None


def test_rule_db_model_types(session: Session) -> None:
    # Prepare data
    trigger = RuleGroup(
        logic=LogicType.AND,
        conditions=[
            Condition(field=FieldType.TEXT, operator=OperatorType.CONTAINS, value="spam"),
            Condition(field=FieldType.LEVEL, operator=OperatorType.LT, value=3),
        ],
    )
    actions = Actions(delete=DeleteAction(enabled=True), ban=BanAction(enabled=True, days=1))

    # Create rule
    rule = ReviewRules(
        fid=12345,
        forum_rule_id=1,
        name="Anti-Spam",
        trigger=trigger,
        actions=actions,
    )
    session.add(rule)
    session.commit()

    # Reload and verify
    loaded_rule = session.execute(select(ReviewRules)).scalar_one()

    # Check trigger serialization/deserialization
    assert isinstance(loaded_rule.trigger, RuleGroup)
    assert loaded_rule.trigger.logic == LogicType.AND
    assert len(loaded_rule.trigger.conditions) == 2
    assert isinstance(loaded_rule.trigger.conditions[0], Condition)
    assert loaded_rule.trigger.conditions[0].field == FieldType.TEXT

    # Check actions serialization/deserialization
    assert isinstance(loaded_rule.actions, Actions)
    assert loaded_rule.actions.delete.enabled is True
    assert loaded_rule.actions.ban.enabled is True
    assert loaded_rule.actions.ban.days == 1


def test_rule_node_type_manual_check() -> None:
    type_impl = RuleNodeType()
    dialect: Any = None

    # Bind param
    cond = Condition(field=FieldType.TEXT, operator=OperatorType.EQ, value=1)
    dumped = type_impl.process_bind_param(cond, dialect)
    assert dumped == {"field": "text", "operator": "eq", "value": 1}

    # Result value
    loaded = type_impl.process_result_value(dumped, dialect)
    assert isinstance(loaded, Condition)
    assert loaded.field == FieldType.TEXT

    # None handling
    assert type_impl.process_bind_param(None, dialect) is None
    assert type_impl.process_result_value(None, dialect) is None


def test_actions_type_manual_check() -> None:
    type_impl = ActionsType()
    dialect: Any = None

    # Bind param
    actions = Actions(notify=NotifyAction(enabled=True, template="hi"))
    dumped = type_impl.process_bind_param(actions, dialect)
    assert isinstance(dumped, dict)
    assert dumped["notify"]["enabled"] is True

    # Result value
    loaded = type_impl.process_result_value(dumped, dialect)
    assert isinstance(loaded, Actions)
    assert loaded.notify.enabled is True
    assert loaded.notify.template == "hi"
    assert type_impl.process_bind_param(None, dialect) is None
    assert type_impl.process_result_value(None, dialect) is None


def test_fragment_list_type_postgres():
    type_impl = FragmentListType()
    mock_dialect = Mock()
    mock_dialect.name = "postgresql"
    mock_dialect.type_descriptor = Mock(side_effect=lambda x: x)

    res = type_impl.load_dialect_impl(mock_dialect)
    assert isinstance(res, JSONB)


def test_fragment_list_type_validate_fallback():
    def fallback_func():
        return FragTextModel(text="fallback")

    type_impl = FragmentListType(fallback=fallback_func)
    invalid_item = {"invalid": "data", "type": "non_existent_type"}
    res = type_impl._validate(invalid_item)
    assert isinstance(res, FragTextModel)
    assert res.text == "fallback"


def test_fragment_list_type_validate_raise():
    type_impl = FragmentListType()
    invalid_item = {"type": "unknown_invalid_type", "garbage": 1}
    with pytest.raises(ValidationError):
        type_impl._validate(invalid_item)


def test_rule_node_type_postgres():
    type_impl = RuleNodeType()
    mock_dialect = Mock()
    mock_dialect.name = "postgresql"
    mock_dialect.type_descriptor = Mock(side_effect=lambda x: x)
    res = type_impl.load_dialect_impl(mock_dialect)
    assert isinstance(res, JSONB)


def test_actions_type_postgres():
    type_impl = ActionsType()
    mock_dialect = Mock()
    mock_dialect.name = "postgresql"
    mock_dialect.type_descriptor = Mock(side_effect=lambda x: x)
    res = type_impl.load_dialect_impl(mock_dialect)
    assert isinstance(res, JSONB)


# --- ORM Methods & Mixin Tests ---


class TestORMMethods:
    def test_mixin_to_dict(self):
        class Dummy(MixinBase):
            __tablename__ = "dummy"

            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            name: Mapped[str] = mapped_column(String)

        d = Dummy(id=1, name="foo")

        res = d.to_dict()
        assert res == {"id": 1, "name": "foo"}

    def test_user_from_dto(self):
        dto = BaseUserDTO(user_id=123, portrait="portrait", user_name="name", nick_name_new="nick")

        user = User.from_dto(dto)
        assert user.user_id == 123
        assert user.portrait == "portrait"
        assert user.user_name == "name"
        assert user.nick_name == "nick"

    def test_thread_from_dto(self):
        dto = ThreadDTO.from_incomplete_data({})
        dto.tid = 100
        dto.create_time = datetime.now()
        dto.title = "t"
        dto.text = "txt"
        dto.contents = []
        dto.last_time = datetime.now()
        dto.reply_num = 5
        dto.author.level = 10
        dto.fid = 50
        dto.author_id = 99

        t = Thread.from_dto(dto)
        assert t.tid == 100
        assert t.author_level == 10
        assert t.fid == 50

    def test_post_from_dto(self):
        dto = PostDTO.from_incomplete_data({})
        dto.pid = 200
        dto.create_time = datetime.now()
        dto.text = "p"
        dto.contents = []
        dto.floor = 2
        dto.reply_num = 1
        dto.author.level = 5
        dto.tid = 100
        dto.fid = 50
        dto.author_id = 99

        p = Post.from_dto(dto)
        assert p.pid == 200
        assert p.floor == 2
        assert p.tid == 100

    def test_comment_from_dto(self):
        dto = CommentDTO.from_incomplete_data({})
        dto.cid = 300
        dto.create_time = datetime.now()
        dto.text = "c"
        dto.contents = []
        dto.author.level = 3
        dto.reply_to_id = 88
        dto.pid = 200
        dto.tid = 100
        dto.fid = 50
        dto.author_id = 99

        c = Comment.from_dto(dto)
        assert c.cid == 300
        assert c.reply_to_id == 88

    def test_review_rules_conversion(self):
        trigger = Condition(field=FieldType.TEXT, operator=OperatorType.EQ, value="x")
        act = Actions(delete=DeleteAction(enabled=True))

        rule_data = ReviewRule(
            id=1,
            fid=10,
            forum_rule_id=2,
            uploader_id=3,
            name="test",
            trigger=trigger,
            actions=act,
            target_type=TargetType.POST,
            enabled=True,
            priority=1,
        )

        orm_obj = ReviewRules.from_rule_data(rule_data)
        assert orm_obj.fid == 10
        assert orm_obj.name == "test"

        orm_obj.id = 1
        orm_obj.created_at = datetime.now()
        orm_obj.updated_at = datetime.now()

        out_data = orm_obj.to_rule_data()
        assert out_data.fid == 10
        assert out_data.name == "test"
        assert out_data.trigger == trigger
