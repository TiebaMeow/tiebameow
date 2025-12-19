from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from tiebameow.models.orm import Fragment, FragmentListType
from tiebameow.schemas.fragments import FragImageModel, FragTextModel


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
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


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
