from datetime import datetime

from tiebameow.models.dto import (
    BaseUserDTO,
    ShareThreadDTO,
    ThreadDTO,
    ThreadUserDTO,
)
from tiebameow.schemas.fragments import FragTextModel


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
        gender="MALE",
        icons=[],
        is_bawu=False,
        is_vip=False,
        is_god=False,
        priv_like="PUBLIC",
        priv_reply="ALL",
    )
    share_origin = ShareThreadDTO(pid=0, tid=0, fid=0, fname="", author_id=0, title="", contents=[])
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
