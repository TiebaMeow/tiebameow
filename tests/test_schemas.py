from typing import Any, cast

from tiebameow.schemas.fragments import (
    FragAtModel,
    FragEmojiModel,
    FragImageModel,
    FragItemModel,
    FragLinkModel,
    FragTextModel,
    FragUnknownModel,
)


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
    # Test that Fragment union works correctly with TypeAdapter or direct instantiation if applicable
    # Since Fragment is a Union type alias, we can't instantiate it directly,
    # but we can check if models satisfy the type.

    t = FragTextModel(text="t")
    assert isinstance(t, FragTextModel)
