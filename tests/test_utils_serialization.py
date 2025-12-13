import pytest

from tiebameow.models.dto import CommentDTO, PostDTO, ThreadDTO
from tiebameow.serialization.serialization import (
    deserialize,
    deserialize_comment,
    deserialize_post,
    deserialize_thread,
    serialize,
)

# Sample User Data
USER_DATA = {
    "user_id": 1812389924,
    "portrait": "tb.1.6a2db2cd.Dsi7jkSnvOYuAuebNB701Q",
    "user_name": "IZUMIKun_",
    "nick_name": "瑞士法郎◎",
    "level": 114514,
    "is_god": False,
}

# Sample Fragment Data
FRAGMENT_DATA = [
    {"type": "text", "text": "中坚甄选有洁哥 正好黄票够了"},
    {"type": "emoji", "id": "image_emoticon3", "desc": "吐舌"},
    {"type": "text", "text": "想抓一只捏\n萌新box质量一般"},
    {"type": "emoji", "id": "image_emoticon66", "desc": "小乖"},
    {"type": "text", "text": "但是洁哥真的好可爱\n求大佬说说她有什么用"},
    {"type": "emoji", "id": "image_emoticon28", "desc": "乖"},
    {
        "type": "image",
        "src": "http://tiebapic.baidu.com/forum/w%3D720%3Bq%3D90%3Bg%3D0/sign=c1046cf64cd162d985ee601e21e4d8d1/d27a1044d688d43f4498b3c03b1ed21b0ef43b4d.jpg?tbpicau=2023-09-01-05_9e31cef67b90f3c61d38abc198416e8a",
        "big_src": "http://tiebapic.baidu.com/forum/w%3D960%3Bq%3D100/sign=67ce6a1c941b0ef46ce89458edff20e7/d27a1044d688d43f4498b3c03b1ed21b0ef43b4d.jpg?tbpicau=2023-09-01-05_a5ac154baad6d0850d7af59765cb33b1",
        "origin_src": "http://tiebapic.baidu.com/forum/pic/item/d27a1044d688d43f4498b3c03b1ed21b0ef43b4d.jpg?tbpicau=2023-09-01-05_c02033df62056b8078ad1354796556b0",
        "origin_size": 536872,
        "show_width": 560,
        "show_height": 583,
        "hash": "d27a1044d688d43f4498b3c03b1ed21b0ef43b4d",
    },
]


def test_serialize_pydantic_model() -> None:
    # Mock a object with model_dump
    class MockModel:
        def model_dump[T](self, mode: T) -> dict[str, T | int]:
            return {"a": 1, "mode": mode}

    obj = MockModel()
    result = serialize(obj)
    assert result == {"a": 1, "mode": "json"}


def test_serialize_plain_object() -> None:
    obj = {"key": "value"}
    result = serialize(obj)
    assert result == obj


def test_deserialize_thread() -> None:
    data = {
        "pid": 1001,
        "tid": 2001,
        "fid": 3001,
        "fname": "test_forum",
        "author_id": 1812389924,
        "author": USER_DATA,
        "title": "Test Thread",
        "contents": FRAGMENT_DATA,
        "is_good": False,
        "is_top": False,
        "is_share": False,
        "is_hide": False,
        "is_livepost": False,
        "is_help": False,
        "agree_num": 10,
        "disagree_num": 0,
        "reply_num": 5,
        "view_num": 100,
        "share_num": 1,
        "create_time": "2023-01-01T12:00:00",
        "last_time": "2023-01-02T12:00:00",
        "thread_type": 0,
        "tab_id": 0,
        "share_origin": {
            "pid": 0,
            "tid": 0,
            "fid": 0,
            "fname": "",
            "author_id": 0,
            "title": "",
            "contents": [],
        },
    }

    # Test normalization of 'user' -> 'author'
    data_with_user = data.copy()
    del data_with_user["author"]
    data_with_user["user"] = USER_DATA

    thread = deserialize_thread(data_with_user)
    assert isinstance(thread, ThreadDTO)
    assert thread.tid == 2001
    assert thread.author.user_id == 1812389924
    assert len(thread.contents) == 7
    assert thread.contents[0].type == "text"
    assert thread.contents[1].type == "emoji"
    assert thread.contents[1].id == "image_emoticon3"
    assert thread.contents[6].type == "image"
    assert thread.contents[6].hash == "d27a1044d688d43f4498b3c03b1ed21b0ef43b4d"

    # Test generic deserialize
    thread_generic = deserialize("thread", data_with_user)
    assert isinstance(thread_generic, ThreadDTO)
    assert thread_generic.tid == 2001


def test_deserialize_post() -> None:
    data = {
        "pid": 1002,
        "tid": 2001,
        "fid": 3001,
        "fname": "test_forum",
        "author_id": 1812389924,
        "user": USER_DATA,  # Test user normalization directly
        "contents": {"objs": FRAGMENT_DATA},  # Test contents normalization (dict -> list)
        "sign": "",
        "is_aimeme": False,
        "is_thread_author": True,
        "agree_num": 5,
        "disagree_num": 0,
        "reply_num": 2,
        "create_time": "2023-01-01T12:30:00",
        "floor": 1,
    }

    post = deserialize_post(data)
    assert isinstance(post, PostDTO)
    assert post.pid == 1002
    assert post.author.user_id == 1812389924
    assert len(post.contents) == 7

    # Test generic deserialize
    post_generic = deserialize("post", data)
    assert isinstance(post_generic, PostDTO)


def test_deserialize_comment() -> None:
    data = {
        "cid": 5001,
        "pid": 1002,
        "tid": 2001,
        "fid": 3001,
        "fname": "test_forum",
        "author_id": 1812389924,
        "user": USER_DATA,
        "contents": FRAGMENT_DATA,
        "reply_to_id": 0,
        "is_thread_author": True,
        "agree_num": 1,
        "disagree_num": 0,
        "create_time": "2023-01-01T13:00:00",
        "floor": 1,
    }

    comment = deserialize_comment(data)
    assert isinstance(comment, CommentDTO)
    assert comment.cid == 5001

    # Test generic deserialize
    comment_generic = deserialize("comment", data)
    assert isinstance(comment_generic, CommentDTO)


def test_deserialize_invalid_type() -> None:
    with pytest.raises(ValueError, match="Unsupported item_type"):
        deserialize("unknown", {})  # type: ignore
