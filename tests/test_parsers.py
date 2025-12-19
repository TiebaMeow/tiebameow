from typing import Any

from tiebameow.parser.parser import (
    convert_aiotieba_content_list,
    convert_aiotieba_fragment,
    convert_aiotieba_threaduser,
    convert_aiotieba_tiebauiduser,
    convert_aiotieba_userinfo,
)
from tiebameow.schemas.fragments import (
    FragAtModel,
    FragEmojiModel,
    FragImageModel,
    FragItemModel,
    FragLinkModel,
    FragTextModel,
    FragUnknownModel,
)


class MockUser:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_convert_aiotieba_fragment(mock_aiotieba_fragments: dict[str, Any]) -> None:
    # Text
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["text"])
    assert isinstance(res, FragTextModel)
    assert res.text == "hello"

    # Image
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["image"])
    assert isinstance(res, FragImageModel)
    assert res.src == "http://src"

    # At
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["at"])
    assert isinstance(res, FragAtModel)
    assert res.text == "@user"

    # Link
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["link"])
    assert isinstance(res, FragLinkModel)
    assert res.text == "http://link"

    # Emoji
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["emoji"])
    assert isinstance(res, FragEmojiModel)
    assert res.id == "1"

    # Item
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["item"])
    assert isinstance(res, FragItemModel)
    assert res.text == "item"

    # Unknown
    res = convert_aiotieba_fragment(mock_aiotieba_fragments["unknown"])
    assert isinstance(res, FragUnknownModel)


def test_convert_aiotieba_content_list(mock_aiotieba_fragments: dict[str, Any]) -> None:
    contents = [mock_aiotieba_fragments["text"], mock_aiotieba_fragments["image"]]
    res = convert_aiotieba_content_list(contents)
    assert len(res) == 2
    assert isinstance(res[0], FragTextModel)
    assert isinstance(res[1], FragImageModel)


def test_convert_aiotieba_tiebauiduser() -> None:
    user = MockUser(user_id=1, portrait="portrait", user_name="user_name", nick_name="nick_name")
    res = convert_aiotieba_tiebauiduser(user)
    assert res.user_id == 1
    assert res.nick_name == "nick_name"


def test_convert_aiotieba_threaduser() -> None:
    user = MockUser(
        user_id=1,
        portrait="portrait",
        user_name="user_name",
        nick_name="nick_name",
        level=1,
        glevel=1,
        gender=MockUser(name="MALE"),  # Mock enum
        ip="127.0.0.1",
        icons=[],
        is_bawu=False,
        is_vip=False,
        is_god=False,
        priv_like=MockUser(name="PUBLIC"),
        priv_reply=MockUser(name="ALL"),
    )
    res = convert_aiotieba_threaduser(user)
    assert res.user_id == 1
    assert res.gender == "MALE"


def test_convert_aiotieba_userinfo() -> None:
    user = MockUser(
        user_id=1,
        portrait="portrait",
        user_name="user_name",
        nick_name="nick_name",
        nick_name_old="old",
        tieba_uid=123,
        glevel=1,
        gender=MockUser(name="MALE"),
        age=1.0,
        post_num=10,
        agree_num=10,
        fan_num=10,
        follow_num=10,
        forum_num=10,
        sign="sign",
        ip="127.0.0.1",
        icons=[],
        is_vip=False,
        is_god=False,
        is_blocked=False,
        priv_like=MockUser(name="PUBLIC"),
        priv_reply=MockUser(name="ALL"),
    )
    res = convert_aiotieba_userinfo(user)
    assert res.user_id == 1
    assert res.post_num == 10
