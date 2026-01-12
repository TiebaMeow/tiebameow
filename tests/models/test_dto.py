from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from tiebameow.models.dto import (
    BaseDTO,
    BaseThreadDTO,
    BaseUserDTO,
    CommentDTO,
    PostDTO,
    ThreadDTO,
    ThreadUserDTO,
)
from tiebameow.schemas.fragments import FragAtModel, FragImageModel, FragTextModel

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


class NestedModel(BaseModel):
    name: str


class ParentDTO(BaseDTO):
    nested: NestedModel
    nested_dto: BaseUserDTO
    tags: set[str]
    str_list: list[str]
    str_dict: dict[str, int]
    str_set: set[int]


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


def test_base_dto_zero_values():
    """Test various zero value generations."""
    model = ParentDTO.from_incomplete_data({})
    assert isinstance(model.nested, NestedModel)
    assert model.nested.name == ""
    assert isinstance(model.nested_dto, BaseUserDTO)
    assert model.tags == set()
    assert model.str_list == []
    assert model.str_dict == {}
    assert model.str_set == set()

    obj_none = ParentDTO.from_incomplete_data(None)
    assert isinstance(obj_none.nested, NestedModel)
    assert obj_none.nested.name == ""
    assert isinstance(obj_none.nested_dto, BaseUserDTO)
    assert obj_none.tags == set()
    assert obj_none.str_list == []
    assert obj_none.str_dict == {}
    assert obj_none.str_set == set()


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


def test_base_dto_from_incomplete_data_with_model():
    """Test from_incomplete_data with BaseModel input."""
    input_model = NestedModel(name="test")
    _ = NestedModel.model_validate(input_model)

    class TestDTO(BaseDTO):
        name: str

    res = TestDTO.from_incomplete_data(input_model)
    assert res.name == "test"


def test_get_zero_value_explicit_strings():
    """Test _get_zero_value with explicit string types to hit specific branches."""

    assert BaseDTO._get_zero_value("list[int]") == []
    assert BaseDTO._get_zero_value("dict[str, int]") == {}
    assert BaseDTO._get_zero_value("set[int]") == set()

    assert BaseDTO._get_zero_value(set[int]) == set()

    # Test generic string
    assert BaseDTO._get_zero_value("some_other_type") is None


def test_base_dto_nested_fallback():
    """Test BaseDTO nested model fallback (lines 121-124)."""

    # We need a field that is a BaseModel but NOT a BaseDTO
    class SimpleModel(BaseModel):
        val: int

    class VerifyDTO(BaseDTO):
        nested: SimpleModel

    # from_incomplete_data({}) -> nested is None -> _get_zero_value(SimpleModel)
    # This hits line 123-124: dummy_data construction & validation
    dto = VerifyDTO.from_incomplete_data({})
    assert isinstance(dto.nested, SimpleModel)
    assert dto.nested.val == 0


def test_base_dto_nested_base_dto():
    """Test BaseDTO nested BaseDTO (lines 122)."""

    class InnerDTO(BaseDTO):
        inner_val: int

    class OuterDTO(BaseDTO):
        inner: InnerDTO

    # from_incomplete_data({}) -> inner is None -> _get_zero_value(InnerDTO)
    # InnerDTO is BaseDTO -> returns InnerDTO.from_incomplete_data({})
    dto = OuterDTO.from_incomplete_data({})
    assert isinstance(dto.inner, InnerDTO)
    assert dto.inner.inner_val == 0


def test_thread_dto_properties():
    """Test cached properties of BaseThreadDTO (via ThreadDTO)."""

    # Create manually to populate contents
    contents = [
        FragTextModel(text="Hello"),
        FragImageModel(src="http://img.com"),
        FragAtModel(text="@User", user_id=123),
    ]
    thread = ThreadDTO.from_incomplete_data({"title": "Title", "contents": contents})  # type: ThreadDTO

    assert "Hello" in thread.text
    assert "Title" in thread.full_text
    assert "Hello" in thread.full_text
    assert len(thread.images) == 1
    assert thread.images[0].src == "http://img.com"
    assert len(thread.ats) == 1
    assert thread.ats[0] == 123

    # Test empty contents
    thread_empty = ThreadDTO.from_incomplete_data({"title": "Empty"})
    assert thread_empty.text == ""
    assert thread_empty.images == []
    assert thread_empty.ats == []


def test_post_dto_properties():
    """Test cached properties of PostDTO."""
    contents = [
        FragTextModel(text="PostContent"),
        FragImageModel(src="http://img.com"),
        FragAtModel(text="@User", user_id=456),
    ]
    post = PostDTO.from_incomplete_data({"contents": contents})

    assert "PostContent" in post.text
    assert post.full_text == post.text
    assert len(post.images) == 1
    assert len(post.ats) == 1
    assert post.ats[0] == 456


def test_comment_dto_properties():
    """Test cached properties of CommentDTO."""
    contents = [FragTextModel(text="CommentContent"), FragAtModel(text="@User", user_id=789)]
    comment = CommentDTO.from_incomplete_data({"contents": contents})

    assert "CommentContent" in comment.text
    assert comment.full_text == comment.text
    assert len(comment.ats) == 1
    assert comment.ats[0] == 789


def test_zero_value_union_types():
    from datetime import datetime

    class UnionDTO(BaseDTO):
        opt_int: int | None
        opt_str: str | None
        create_time: datetime

    dto = UnionDTO.from_incomplete_data({})
    assert dto.opt_int is None
    assert dto.opt_str is None
    assert dto.create_time == datetime.fromtimestamp(0)
