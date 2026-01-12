import dataclasses
from typing import Any

from aiotieba.api.get_comments._classdef import Comments, Forum_c, UserInfo_c
from aiotieba.api.get_posts._classdef import (
    Comment_p,
    Forum_p,
    Page_p,
    Post,
    Posts,
    ShareThread_pt,
    Thread_p,
    UserInfo_p,
)
from aiotieba.api.get_threads._classdef import Forum_t, ShareThread, Thread, Threads, UserInfo_t
from aiotieba.api.tieba_uid2user_info._classdef import UserInfo_TUid
from aiotieba.enums import Gender, PrivLike, PrivReply
from aiotieba.typing import UserInfo

from tiebameow.parser.parser import (
    convert_aiotieba_comment,
    convert_aiotieba_comments,
    convert_aiotieba_commentsp,
    convert_aiotieba_content_list,
    convert_aiotieba_fragment,
    convert_aiotieba_pageinfo,
    convert_aiotieba_post,
    convert_aiotieba_posts,
    convert_aiotieba_postuser,
    convert_aiotieba_share_thread,
    convert_aiotieba_thread,
    convert_aiotieba_threadp,
    convert_aiotieba_threads,
    convert_aiotieba_threaduser,
    convert_aiotieba_tiebauiduser,
    convert_aiotieba_user,
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

# --- Basic Conversion Tests ---


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
    user = UserInfo_TUid(
        user_id=1,
        nick_name_new="nick_name",
    )
    res = convert_aiotieba_tiebauiduser(user)
    assert res.user_id == 1
    assert res.nick_name == "nick_name"


def test_convert_aiotieba_threaduser() -> None:
    user = UserInfo_t(
        user_id=1,
        gender=Gender.MALE,
    )
    res = convert_aiotieba_threaduser(user)
    assert res.user_id == 1
    assert res.gender == "MALE"


def test_convert_aiotieba_userinfo() -> None:
    user = UserInfo(
        user_id=1,
        post_num=10,
    )
    res = convert_aiotieba_userinfo(user)
    assert res.user_id == 1
    assert res.post_num == 10


# --- Coverage & Complex Case Tests ---


@dataclasses.dataclass
class UnmappedFrag:
    data: str = "test"


def test_convert_fragment_unknown():
    frag = UnmappedFrag()
    res = convert_aiotieba_fragment(frag)
    assert isinstance(res, FragUnknownModel)
    assert "UnmappedFrag" in res.raw_data


def test_convert_content_list_empty():
    assert convert_aiotieba_content_list([]) == []


def test_convert_threaduser_with_gender():
    user = UserInfo_t(
        user_id=1,
        portrait="p",
        user_name="u",
        nick_name_new="n",
        level=1,
        glevel=1,
        icons=[],
        is_bawu=False,
        is_vip=False,
        is_god=False,
        priv_like=PrivLike.PUBLIC,
        priv_reply=PrivReply.ALL,
        gender=Gender.MALE,
    )
    res = convert_aiotieba_threaduser(user)
    assert res.gender == "MALE"
    assert res.priv_like == "PUBLIC"


def test_convert_postuser():
    user = UserInfo_p(ip="127.0.0.1")
    res = convert_aiotieba_postuser(user)
    assert res.ip == "127.0.0.1"


def test_convert_user_dispatch():
    # Helper to create mock objects with specific attributes control

    # UserInfo_TUid
    u_tuid = UserInfo_TUid(user_id=1)
    res1 = convert_aiotieba_user(u_tuid)
    assert res1.user_id == 1

    # UserInfo_t
    u_t = UserInfo_t(user_id=2)
    res2 = convert_aiotieba_user(u_t)
    assert res2.user_id == 2

    # UserInfo_p
    u_p = UserInfo_p(user_id=3, ip="127.0.0.1")
    res3 = convert_aiotieba_user(u_p)
    assert res3.user_id == 3
    assert res3.ip == "127.0.0.1"

    # UserInfo_c
    u_c = UserInfo_c(user_id=4)
    res4 = convert_aiotieba_user(u_c)
    assert res4.user_id == 4

    # UserInfo (has tieba_uid)
    u_i = UserInfo(user_id=5)
    res5 = convert_aiotieba_user(u_i)
    assert res5.user_id == 5


def test_collections_converters():
    # Mocking complex nested structures for Threads, Posts, Comments

    # Threads
    threads = Threads()
    threads.forum = Forum_t(fid=1, fname="f")

    dto_threads = convert_aiotieba_threads(threads)
    assert dto_threads.forum.fid == 1

    # Posts
    posts = Posts()
    posts.forum = Forum_p(fid=2, fname="f")

    dto_posts = convert_aiotieba_posts(posts)
    assert dto_posts.forum.fid == 2

    # Comments
    comments = Comments()
    comments.forum = Forum_c(fid=3, fname="f")

    dto_comments = convert_aiotieba_comments(comments)
    assert dto_comments.forum.fid == 3


def test_convert_complex_objects():

    # 1. Share Thread
    share = ShareThread_pt(
        tid=123,
        fid=456,
        fname="TestBar",
        author_id=789,
        title="ShareTitle",
    )
    # pid is checked via getattr(share, "pid", 0) -> missing pid
    res_share = convert_aiotieba_share_thread(share)
    assert res_share.tid == 123
    assert res_share.pid == 0

    # Share with pid
    share_pid = ShareThread(
        tid=123,
        fid=456,
        fname="TestBar",
        author_id=789,
        title="ShareTitle",
        pid=999,
    )
    res_share2 = convert_aiotieba_share_thread(share_pid)
    assert res_share2.pid == 999

    # 2. Thread
    thread = Thread(
        tid=2001,
        fname="Bar",
        title="ThreadTitle",
        share_origin=share_pid,
    )

    res_thread = convert_aiotieba_thread(thread)
    assert res_thread.tid == 2001
    assert res_thread.share_origin.title == "ShareTitle"

    # 3. Thread_p (Thread in posts)
    threadp = Thread_p(title="ThreadPTitle")
    res_threadp = convert_aiotieba_threadp(threadp)
    assert res_threadp.title == "ThreadPTitle"

    # 4. Post
    comment_p = Comment_p(pid=5001)
    post = Post(pid=3001, comments=[comment_p])

    res_post = convert_aiotieba_post(post)
    assert res_post.pid == 3001
    assert len(res_post.comments) == 1
    assert res_post.comments[0].cid == 5001

    # 5. Comment standalone
    res_comment = convert_aiotieba_comment(comment_p)
    assert res_comment.cid == 5001

    # 6. Commentsp
    res_commentsp = convert_aiotieba_commentsp([comment_p])
    assert len(res_commentsp) == 1

    # 7. PageInfo
    page = Page_p(page_size=30, current_page=1, total_page=5, total_count=150, has_more=True, has_prev=False)
    res_page = convert_aiotieba_pageinfo(page)
    assert res_page.current_page == 1
    assert res_page.has_more is True
