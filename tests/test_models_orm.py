from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from tiebameow.models.orm import (
    ActionListType,
    Fragment,
    FragmentListType,
    ReviewRules,
    RuleBase,
    RuleNodeType,
)
from tiebameow.schemas.fragments import FragImageModel, FragTextModel
from tiebameow.schemas.rules import (
    Action,
    ActionType,
    Condition,
    FieldType,
    LogicType,
    OperatorType,
    RuleGroup,
)


# Define a test model using FragmentListType
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
    RuleBase.metadata.create_all(engine)  # Create table for RuleDBModel
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


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
    # Test with None if allowed by model (though mapped_column usually implies not null unless nullable=True)
    # Here we just test the type behavior if we were to pass None to process_bind_param manually
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
    actions = [
        Action(type=ActionType.DELETE),
        Action(type=ActionType.BAN, params={"duration": 1}),
    ]

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
    assert isinstance(loaded_rule.actions, list)
    assert len(loaded_rule.actions) == 2
    assert isinstance(loaded_rule.actions[0], Action)
    assert loaded_rule.actions[0].type == ActionType.DELETE
    assert loaded_rule.actions[1].type == ActionType.BAN
    assert loaded_rule.actions[1].params["duration"] == 1


def test_rule_node_type_manual_check() -> None:
    # Manual check for type decorator logic
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


def test_action_list_type_manual_check() -> None:
    # Manual check for type decorator logic
    type_impl = ActionListType()
    dialect: Any = None

    # Bind param
    actions = [Action(type=ActionType.NOTIFY, params={"msg": "hi"})]
    dumped = type_impl.process_bind_param(actions, dialect)
    assert isinstance(dumped, list)
    assert dumped[0]["type"] == "notify"

    # Result value
    loaded = type_impl.process_result_value(dumped, dialect)
    assert isinstance(loaded, list)
    assert isinstance(loaded[0], Action)
    assert loaded[0].type == ActionType.NOTIFY
    # None handling
    assert type_impl.process_bind_param(None, dialect) is None
    assert type_impl.process_result_value(None, dialect) is None
