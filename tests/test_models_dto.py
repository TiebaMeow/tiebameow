from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from tiebameow.models.dto import (
    BaseDTO,
    BaseThreadDTO,
    BaseUserDTO,
    PostDTO,
    ThreadDTO,
    ThreadUserDTO,
)
from tiebameow.schemas.fragments import FragTextModel

# --- Test Helpers ---


class SimpleDTO(BaseDTO):
    name: str
    age: int
    score: float
    is_active: bool
    tags: list[str]
    metadata: dict[str, str]


class NestedDTO(BaseDTO):
    id: int
    child: SimpleDTO


class LiteralDTO(BaseDTO):
    mode: Literal["A", "B", "C"]


class PlainModel(BaseModel):
    x: int
    y: int


class WrapperDTO(BaseDTO):
    inner: PlainModel


# --- Normal Tests ---


def test_base_user_dto() -> None:
    user = BaseUserDTO(user_id=1, portrait="portrait", user_name="user_name", nick_name_new="nick_name")
    assert user.nick_name == "nick_name"
    assert user.show_name == "nick_name"

    user_no_nick = BaseUserDTO(user_id=1, portrait="portrait", user_name="user_name", nick_name_new="")
    assert user_no_nick.nick_name == ""
    assert user_no_nick.show_name == "user_name"


def test_thread_user_dto() -> None:
    user = ThreadUserDTO(
        user_id=1,
        portrait="portrait",
        user_name="user_name",
        nick_name_new="nick_name",
        level=1,
        glevel=1,
        gender="MALE",
        icons=[],
        is_bawu=False,
        is_vip=False,
        is_god=False,
        priv_like="PUBLIC",
        priv_reply="ALL",
    )
    assert user.level == 1
    assert user.gender == "MALE"


def test_thread_dto() -> None:
    author = ThreadUserDTO(
        user_id=1,
        portrait="portrait",
        user_name="user_name",
        nick_name_new="nick_name",
        level=1,
        glevel=1,
        gender="MALE",
        icons=[],
        is_bawu=False,
        is_vip=False,
        is_god=False,
        priv_like="PUBLIC",
        priv_reply="ALL",
    )
    share_origin = BaseThreadDTO(pid=0, tid=0, fid=0, fname="", author_id=0, title="", contents=[])
    thread = ThreadDTO(
        pid=1,
        tid=1,
        fid=1,
        fname="fname",
        author_id=1,
        author=author,
        title="title",
        contents=[FragTextModel(text="content")],
        is_good=False,
        is_top=False,
        is_share=False,
        is_hide=False,
        is_livepost=False,
        is_help=False,
        agree_num=0,
        disagree_num=0,
        reply_num=0,
        view_num=0,
        share_num=0,
        create_time=datetime.now(),
        last_time=datetime.now(),
        thread_type=0,
        tab_id=0,
        share_origin=share_origin,
    )
    assert thread.title == "title"
    assert len(thread.contents) == 1
    assert isinstance(thread.contents[0], FragTextModel)
    assert thread.contents[0].text == "content"


# --- Zero-fill Tests ---


def test_base_dto_zero_values() -> None:
    """Test completely empty init fills with zero values."""
    obj = SimpleDTO.from_incomplete_data({})
    assert obj.name == ""
    assert obj.age == 0
    assert obj.score == 0.0
    assert obj.is_active is False
    assert obj.tags == []
    assert obj.metadata == {}

    # Test with None input
    obj_none = SimpleDTO.from_incomplete_data(None)
    assert obj_none.name == ""


def test_base_dto_partial_values() -> None:
    """Test partial data fills missing with zero values."""
    obj = SimpleDTO.from_incomplete_data({"name": "Alice", "age": 30})
    assert obj.name == "Alice"
    assert obj.age == 30
    assert obj.score == 0.0  # Filled
    assert obj.tags == []  # Filled


def test_base_dto_nested() -> None:
    """Test recursion on nested BaseDTO fields."""
    obj = NestedDTO.from_incomplete_data({"id": 1, "child": {"name": "Bob"}})
    assert obj.id == 1
    assert isinstance(obj.child, SimpleDTO)
    assert obj.child.name == "Bob"
    assert obj.child.age == 0  # Filled child field
    assert obj.child.tags == []


def test_base_dto_nested_empty() -> None:
    """Test recursion when nested field is missing entirely."""
    obj = NestedDTO.from_incomplete_data({"id": 1})
    assert obj.id == 1
    assert isinstance(obj.child, SimpleDTO)
    # Child should be created with all zero values
    assert obj.child.name == ""
    assert obj.child.age == 0


def test_base_dto_literal() -> None:
    """Test Literal defaults to first option."""
    obj = LiteralDTO.from_incomplete_data({})
    assert obj.mode == "A"


def test_base_dto_literal_provided() -> None:
    """Test Literal with provided value."""
    obj = LiteralDTO.from_incomplete_data({"mode": "B"})
    assert obj.mode == "B"


def test_base_dto_with_plain_pydantic_model() -> None:
    """Test nesting a plain Pydantic model (not BaseDTO) handles partial filling."""
    # Only partial data for inner model
    obj = WrapperDTO.from_incomplete_data({"inner": {"x": 10}})

    # _get_zero_value for PlainModel should create {x:0, y:0}
    # Then merged with {x: 10} -> {x:10, y:0}
    assert isinstance(obj.inner, PlainModel)
    assert obj.inner.x == 10
    assert obj.inner.y == 0


def test_dto_list_none_handling() -> None:
    # Test that None passed to a list field becomes []
    class ListDTO(BaseDTO):
        items: list[str]

    data = {"items": None}
    dto = ListDTO.from_incomplete_data(data)
    assert dto.items == []


def test_post_dto_comments_none_fix() -> None:
    # Verify the specific user case where 'comments' is None
    data = {"pid": 123, "comments": None}
    # Should not raise ValidationError
    dto = PostDTO.from_incomplete_data(data)
    assert dto.comments == []
    assert dto.pid == 123
