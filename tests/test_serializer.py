from tiebameow.models.dto import CommentDTO, PostDTO, ThreadDTO
from tiebameow.schemas.fragments import FragTextModel
from tiebameow.serializer.serializer import (
    deserialize_comment,
    deserialize_post,
    deserialize_thread,
    serialize,
)


def test_serialize() -> None:
    model = FragTextModel(text="hello")
    res = serialize(model)
    assert res == {"type": "text", "text": "hello"}

    # Test non-model object
    assert serialize("string") == "string"


def test_deserialize_thread() -> None:
    data = {
        "pid": 1,
        "tid": 1,
        "fid": 1,
        "fname": "fname",
        "author_id": 1,
        "author": {
            "user_id": 1,
            "portrait": "p",
            "user_name": "u",
            "nick_name_new": "n",
            "level": 1,
            "glevel": 1,
            "gender": "MALE",
            "icons": [],
            "is_bawu": False,
            "is_vip": False,
            "is_god": False,
            "priv_like": "PUBLIC",
            "priv_reply": "ALL",
        },
        "title": "title",
        "contents": [{"type": "text", "text": "content"}],
        "is_good": False,
        "is_top": False,
        "is_share": False,
        "is_hide": False,
        "is_livepost": False,
        "is_help": False,
        "agree_num": 0,
        "disagree_num": 0,
        "reply_num": 0,
        "view_num": 0,
        "share_num": 0,
        "create_time": "2023-01-01T00:00:00",
        "last_time": "2023-01-01T00:00:00",
        "thread_type": 0,
        "tab_id": 0,
        "share_origin": {"pid": 0, "tid": 0, "fid": 0, "fname": "", "author_id": 0, "title": "", "contents": []},
    }
    thread = deserialize_thread(data)
    assert isinstance(thread, ThreadDTO)
    assert thread.title == "title"
    assert len(thread.contents) == 1


def test_deserialize_thread_normalization() -> None:
    # Test contents normalization (objs wrapper) and user normalization (user -> author)
    data = {
        "pid": 1,
        "tid": 1,
        "fid": 1,
        "fname": "fname",
        "author_id": 1,
        "user": {  # Should be mapped to author
            "user_id": 1,
            "portrait": "p",
            "user_name": "u",
            "nick_name_new": "n",
            "level": 1,
            "glevel": 1,
            "gender": "MALE",
            "icons": [],
            "is_bawu": False,
            "is_vip": False,
            "is_god": False,
            "priv_like": "PUBLIC",
            "priv_reply": "ALL",
        },
        "title": "title",
        "contents": {"objs": [{"type": "text", "text": "content"}]},  # Should be unwrapped
        "is_good": False,
        "is_top": False,
        "is_share": False,
        "is_hide": False,
        "is_livepost": False,
        "is_help": False,
        "agree_num": 0,
        "disagree_num": 0,
        "reply_num": 0,
        "view_num": 0,
        "share_num": 0,
        "create_time": "2023-01-01T00:00:00",
        "last_time": "2023-01-01T00:00:00",
        "thread_type": 0,
        "tab_id": 0,
        "share_origin": {"pid": 0, "tid": 0, "fid": 0, "fname": "", "author_id": 0, "title": "", "contents": []},
    }
    thread = deserialize_thread(data)
    assert thread.author.user_id == 1
    assert len(thread.contents) == 1


def test_deserialize_post() -> None:
    data = {
        "pid": 1,
        "tid": 1,
        "fid": 1,
        "fname": "fname",
        "author_id": 1,
        "author": {
            "user_id": 1,
            "portrait": "p",
            "user_name": "u",
            "nick_name_new": "n",
            "level": 1,
            "glevel": 1,
            "gender": "MALE",
            "ip": "127.0.0.1",
            "icons": [],
            "is_bawu": False,
            "is_vip": False,
            "is_god": False,
            "priv_like": "PUBLIC",
            "priv_reply": "ALL",
        },
        "contents": [{"type": "text", "text": "content"}],
        "sign": "",
        "comments": [
            {
                "cid": 1,
                "pid": 1,
                "tid": 1,
                "fid": 1,
                "fname": "fname",
                "author_id": 1,
                "user": {
                    "user_id": 1,
                    "portrait": "p",
                    "user_name": "u",
                    "nick_name_new": "n",
                    "level": 1,
                    "gender": "MALE",
                    "icons": [],
                    "is_bawu": False,
                    "is_vip": False,
                    "is_god": False,
                    "priv_like": "PUBLIC",
                    "priv_reply": "ALL",
                },
                "contents": [{"type": "text", "text": "content"}],
                "reply_to_id": 0,
                "is_thread_author": False,
                "agree_num": 0,
                "disagree_num": 0,
                "create_time": "2023-01-01T00:00:00",
                "floor": 1,
            }
        ],
        "is_aimeme": False,
        "is_thread_author": False,
        "agree_num": 0,
        "disagree_num": 0,
        "reply_num": 0,
        "create_time": "2023-01-01T00:00:00",
        "floor": 1,
    }
    post = deserialize_post(data)
    assert isinstance(post, PostDTO)
    assert post.pid == 1
    assert post.author.user_id == 1
    assert len(post.contents) == 1
    assert isinstance(post.contents[0], FragTextModel)


def test_deserialize_comment() -> None:
    data = {
        "cid": 1,
        "pid": 1,
        "tid": 1,
        "fid": 1,
        "fname": "fname",
        "author_id": 1,
        "author": {
            "user_id": 1,
            "portrait": "p",
            "user_name": "u",
            "nick_name_new": "n",
            "level": 1,
            "gender": "MALE",
            "icons": [],
            "is_bawu": False,
            "is_vip": False,
            "is_god": False,
            "priv_like": "PUBLIC",
            "priv_reply": "ALL",
        },
        "contents": [{"type": "text", "text": "content"}],
        "reply_to_id": 0,
        "is_thread_author": False,
        "agree_num": 0,
        "disagree_num": 0,
        "create_time": "2023-01-01T00:00:00",
        "floor": 1,
    }
    comment = deserialize_comment(data)
    assert isinstance(comment, CommentDTO)
    assert comment.cid == 1
