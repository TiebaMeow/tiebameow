import dataclasses
from typing import Any

import pytest


# Mock aiotieba fragment classes as dataclasses because parser uses dataclasses.asdict
# Naming them to match aiotieba classes so parser can map them correctly
@dataclasses.dataclass
class FragText:
    text: str


@dataclasses.dataclass
class FragImage:
    src: str
    big_src: str
    origin_src: str
    origin_size: int
    show_width: int
    show_height: int
    hash: str


@dataclasses.dataclass
class FragAt:
    text: str
    user_id: int


@dataclasses.dataclass
class FragLink:
    text: str
    title: str
    raw_url: str


@dataclasses.dataclass
class FragEmoji:
    id: str
    desc: str


@dataclasses.dataclass
class FragItem:
    text: str


@dataclasses.dataclass
class FragUnknown:
    pass


# Mock aiotieba user and thread classes
class MockUser:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockThread:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def mock_aiotieba_fragments() -> dict[str, Any]:
    return {
        "text": FragText(text="hello"),
        "image": FragImage(
            src="http://src",
            big_src="http://big",
            origin_src="http://origin",
            origin_size=100,
            show_width=100,
            show_height=100,
            hash="hash",
        ),
        "at": FragAt(text="@user", user_id=123),
        "link": FragLink(text="http://link", title="title", raw_url="http://raw"),
        "emoji": FragEmoji(id="1", desc="smile"),
        "item": FragItem(text="item"),
        "unknown": FragUnknown(),
    }
