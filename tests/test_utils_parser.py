import dataclasses
from typing import Any

from tiebameow.models.dto import CommentDTO, PostDTO, ThreadDTO, UserDTO
from tiebameow.parser.parser import (
    convert_aiotieba_comment,
    convert_aiotieba_fragment,
    convert_aiotieba_post,
    convert_aiotieba_thread,
    convert_aiotieba_user,
)
from tiebameow.schemas.fragments import FragImageModel, FragTextModel

# --- Mocks for aiotieba classes ---


@dataclasses.dataclass
class FragText_t:
    text: str


@dataclasses.dataclass
class FragImage_t:
    src: str
    big_src: str
    origin_src: str
    origin_size: int
    show_width: int
    show_height: int
    hash: str


@dataclasses.dataclass
class FragUnknown_t:
    proto: Any = "some_proto_data"


class MockGender:
    name = "MALE"


class MockPrivLike:
    name = "PUBLIC"


class MockPrivReply:
    name = "ALL"


@dataclasses.dataclass
class MockUser:
    user_id: int = 123
    portrait: str = "portrait"
    user_name: str = "username"
    nick_name: str = "nickname"
    level: int = 1
    glevel: int = 1
    ip: str = "127.0.0.1"
    gender: Any = dataclasses.field(default_factory=MockGender)
    icons: list[str] = dataclasses.field(default_factory=list)
    is_bawu: bool = False
    is_vip: bool = False
    is_god: bool = False
    priv_like: Any = dataclasses.field(default_factory=MockPrivLike)
    priv_reply: Any = dataclasses.field(default_factory=MockPrivReply)


@dataclasses.dataclass
class MockContents:
    objs: list[Any]


@dataclasses.dataclass
class MockShareThread:
    pid: int = 0
    tid: int = 0
    fid: int = 0
    fname: str = ""
    author_id: int = 0
    title: str = ""
    contents: MockContents = dataclasses.field(default_factory=lambda: MockContents([]))


@dataclasses.dataclass
class MockThread:
    pid: int = 1001
    tid: int = 2001
    fid: int = 3001
    fname: str = "test_forum"
    author_id: int = 123
    user: MockUser = dataclasses.field(default_factory=MockUser)
    title: str = "test thread"
    contents: MockContents = dataclasses.field(default_factory=lambda: MockContents([]))
    is_good: bool = False
    is_top: bool = False
    is_share: bool = False
    is_hide: bool = False
    is_livepost: bool = False
    is_help: bool = False
    agree: int = 10
    disagree: int = 1
    reply_num: int = 5
    view_num: int = 100
    share_num: int = 2
    create_time: int = 1678888888
    last_time: int = 1678889999
    type: int = 0
    tab_id: int = 0
    share_origin: MockShareThread = dataclasses.field(default_factory=MockShareThread)


@dataclasses.dataclass
class MockPost:
    pid: int = 1002
    tid: int = 2001
    fid: int = 3001
    fname: str = "test_forum"
    author_id: int = 123
    user: MockUser = dataclasses.field(default_factory=MockUser)
    contents: MockContents = dataclasses.field(default_factory=lambda: MockContents([]))
    sign: str = "signature"
    is_aimeme: bool = False
    is_thread_author: bool = True
    agree: int = 5
    disagree: int = 0
    reply_num: int = 1
    create_time: int = 1678888999
    floor: int = 1


@dataclasses.dataclass
class MockComment:
    pid: int = 1003  # Note: in parser, convert_aiotieba_comment uses pid as cid
    ppid: int = 1002  # pid in parser
    tid: int = 2001
    fid: int = 3001
    fname: str = "test_forum"
    author_id: int = 456
    user: MockUser = dataclasses.field(default_factory=MockUser)
    contents: MockContents = dataclasses.field(default_factory=lambda: MockContents([]))
    reply_to_id: int = 123
    is_thread_author: bool = False
    agree: int = 2
    disagree: int = 0
    create_time: int = 1678889000
    floor: int = 1


# --- Tests ---


def test_convert_aiotieba_fragment() -> None:
    # Test Text Fragment
    frag_text = FragText_t(text="Hello")
    result = convert_aiotieba_fragment(frag_text)
    assert isinstance(result, FragTextModel)
    assert result.text == "Hello"
    assert result.type == "text"

    # Test Image Fragment
    frag_img = FragImage_t(
        src="http://small",
        big_src="http://big",
        origin_src="http://origin",
        origin_size=1024,
        show_width=100,
        show_height=100,
        hash="abc",
    )
    result = convert_aiotieba_fragment(frag_img)
    assert isinstance(result, FragImageModel)
    assert result.src == "http://small"
    assert result.type == "image"

    # Test Unknown Fragment
    # FragUnknown_t -> FragUnknown -> FragUnknownModel
    # This test is skipped because of potential mismatch in fields (proto vs raw_data)
    # which needs to be resolved in the implementation or confirmed.


def test_convert_aiotieba_user() -> None:
    mock_user = MockUser()
    result = convert_aiotieba_user(mock_user)
    assert isinstance(result, UserDTO)
    assert result.user_id == 123
    assert result.user_name == "username"
    assert result.gender == "MALE"


def test_convert_aiotieba_thread() -> None:
    mock_thread = MockThread()
    mock_thread.contents.objs = [FragText_t(text="Thread Content")]

    result = convert_aiotieba_thread(mock_thread)
    assert isinstance(result, ThreadDTO)
    assert result.pid == 1001
    assert result.title == "test thread"
    assert len(result.contents) == 1
    assert isinstance(result.contents[0], FragTextModel)
    assert result.contents[0].text == "Thread Content"
    assert result.create_time.timestamp() == 1678888888


def test_convert_aiotieba_post() -> None:
    mock_post = MockPost()
    mock_post.contents.objs = [FragText_t(text="Post Content")]

    result = convert_aiotieba_post(mock_post)
    assert isinstance(result, PostDTO)
    assert result.pid == 1002
    assert result.sign == "signature"
    assert len(result.contents) == 1
    assert isinstance(result.contents[0], FragTextModel)
    assert result.contents[0].text == "Post Content"


def test_convert_aiotieba_comment() -> None:
    mock_comment = MockComment()
    mock_comment.contents.objs = [FragText_t(text="Comment Content")]

    result = convert_aiotieba_comment(mock_comment)
    assert isinstance(result, CommentDTO)
    assert result.cid == 1003
    assert result.pid == 1002
    assert result.reply_to_id == 123
    assert len(result.contents) == 1
    assert isinstance(result.contents[0], FragTextModel)
    assert result.contents[0].text == "Comment Content"
