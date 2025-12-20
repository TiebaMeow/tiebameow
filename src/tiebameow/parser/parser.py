from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast, overload

from ..models.dto import (
    BaseForumDTO,
    BaseUserDTO,
    CommentDTO,
    CommentpDTO,
    CommentsDTO,
    CommentUserDTO,
    PageInfoDTO,
    PostDTO,
    PostsDTO,
    PostUserDTO,
    ShareThreadDTO,
    ThreadDTO,
    ThreadsDTO,
    ThreadUserDTO,
    UserInfoDTO,
)
from ..schemas.fragments import FRAG_MAP, Fragment, FragUnknownModel
from ..utils.time_utils import SHANGHAI_TZ

if TYPE_CHECKING:
    from aiotieba.api._classdef.contents import (
        FragAt,
        FragEmoji,
        FragImage,
        FragItem,
        FragLink,
        FragText,
        FragTiebaPlus,
        FragUnknown,
        FragVideo,
    )
    from aiotieba.api.get_comments._classdef import Forum_c, Page_c, UserInfo_c
    from aiotieba.api.get_posts._classdef import Comment_p, Forum_p, Page_p, UserInfo_p
    from aiotieba.api.get_threads._classdef import Forum_t, Page_t, ShareThread, UserInfo_t
    from aiotieba.api.tieba_uid2user_info import UserInfo_TUid
    from aiotieba.typing import Comment, Comments, Post, Posts, Thread, Threads, UserInfo

    type AiotiebaType = Thread | Post | Comment
    type AiotiebaFragType = (
        FragAt | FragEmoji | FragImage | FragItem | FragLink | FragText | FragTiebaPlus | FragUnknown | FragVideo
    )
    type AiotiebaUserType = UserInfo_t | UserInfo_p | UserInfo_c | UserInfo_TUid
    type AiotiebaPageType = Page_t | Page_p | Page_c
    type AiotiebaForumType = Forum_t | Forum_p | Forum_c


def convert_aiotieba_fragment(obj: AiotiebaFragType | Any) -> Fragment:
    source_type_name = type(obj).__name__
    target_model_name = source_type_name.rsplit("_", 1)[0]

    target_model = FRAG_MAP.get(target_model_name)

    if target_model is None:
        return FragUnknownModel(raw_data=repr(obj))

    data_dict = dataclasses.asdict(obj)
    return target_model(**data_dict)


def convert_aiotieba_content_list(contents: list[AiotiebaFragType | Any]) -> list[Fragment]:
    if not contents:
        return []
    return [convert_aiotieba_fragment(frag) for frag in contents]


def convert_aiotieba_tiebauiduser(user: UserInfo_TUid) -> BaseUserDTO:
    return BaseUserDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name_new=user.nick_name,
    )


def convert_aiotieba_threaduser(user: UserInfo_t) -> ThreadUserDTO:
    return ThreadUserDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name_new=user.nick_name,
        level=user.level,
        glevel=user.glevel,
        gender=user.gender.name,
        icons=user.icons,
        is_bawu=user.is_bawu,
        is_vip=user.is_vip,
        is_god=user.is_god,
        priv_like=user.priv_like.name,
        priv_reply=user.priv_reply.name,
    )


def convert_aiotieba_postuser(user: UserInfo_p) -> PostUserDTO:
    return PostUserDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name_new=user.nick_name,
        level=user.level,
        glevel=user.glevel,
        gender=user.gender.name,
        ip=user.ip,
        icons=user.icons,
        is_bawu=user.is_bawu,
        is_vip=user.is_vip,
        is_god=user.is_god,
        priv_like=user.priv_like.name,
        priv_reply=user.priv_reply.name,
    )


def convert_aiotieba_commentuser(user: UserInfo_c) -> CommentUserDTO:
    return CommentUserDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name_new=user.nick_name,
        level=user.level,
        gender=user.gender.name,
        icons=user.icons,
        is_bawu=user.is_bawu,
        is_vip=user.is_vip,
        is_god=user.is_god,
        priv_like=user.priv_like.name,
        priv_reply=user.priv_reply.name,
    )


def convert_aiotieba_userinfo(user: UserInfo) -> UserInfoDTO:
    return UserInfoDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name_new=user.nick_name,
        nick_name_old=user.nick_name_old,
        tieba_uid=user.tieba_uid,
        glevel=user.glevel,
        gender=user.gender.name,
        age=user.age,
        post_num=user.post_num,
        agree_num=user.agree_num,
        fan_num=user.fan_num,
        follow_num=user.follow_num,
        forum_num=user.forum_num,
        sign=user.sign,
        ip=user.ip,
        icons=user.icons,
        is_vip=user.is_vip,
        is_god=user.is_god,
        is_blocked=user.is_blocked,
        priv_like=user.priv_like.name,
        priv_reply=user.priv_reply.name,
    )


@overload
def convert_aiotieba_user(user: UserInfo) -> UserInfoDTO: ...


@overload
def convert_aiotieba_user(user: UserInfo_t) -> ThreadUserDTO:  # type: ignore[overload-cannot-match]
    ...


@overload
def convert_aiotieba_user(user: UserInfo_p) -> PostUserDTO:  # type: ignore[overload-cannot-match]
    ...


@overload
def convert_aiotieba_user(user: UserInfo_c) -> CommentUserDTO:  # type: ignore[overload-cannot-match]
    ...


@overload
def convert_aiotieba_user(user: UserInfo_TUid) -> BaseUserDTO:  # type: ignore[overload-cannot-match]
    ...


def convert_aiotieba_user(
    user: UserInfo_TUid | AiotiebaUserType | UserInfo,
) -> BaseUserDTO | ThreadUserDTO | UserInfoDTO:
    if hasattr(user, "tieba_uid"):
        return convert_aiotieba_userinfo(cast("UserInfo", user))
    if hasattr(user, "ip"):
        return convert_aiotieba_postuser(cast("UserInfo_p", user))
    if hasattr(user, "glevel"):
        return convert_aiotieba_threaduser(cast("UserInfo_t", user))
    if hasattr(user, "is_bawu"):
        return convert_aiotieba_commentuser(cast("UserInfo_c", user))
    return convert_aiotieba_tiebauiduser(cast("UserInfo_TUid", user))


def convert_aiotieba_share_thread(share_thread: ShareThread) -> ShareThreadDTO:
    return ShareThreadDTO(
        pid=share_thread.pid,
        tid=share_thread.tid,
        fid=share_thread.fid,
        fname=share_thread.fname,
        author_id=share_thread.author_id,
        title=share_thread.title,
        contents=convert_aiotieba_content_list(share_thread.contents.objs),
    )


def convert_aiotieba_thread(tb_thread: Thread) -> ThreadDTO:
    """
    将 aiotieba 的 Thread 对象转换为 tiebameow 的通用模型
    """
    return ThreadDTO(
        pid=tb_thread.pid,
        tid=tb_thread.tid,
        fid=tb_thread.fid,
        fname=tb_thread.fname,
        author_id=tb_thread.author_id,
        author=convert_aiotieba_threaduser(tb_thread.user),
        title=tb_thread.title,
        contents=convert_aiotieba_content_list(tb_thread.contents.objs),
        is_good=tb_thread.is_good,
        is_top=tb_thread.is_top,
        is_share=tb_thread.is_share,
        is_hide=tb_thread.is_hide,
        is_livepost=tb_thread.is_livepost,
        is_help=tb_thread.is_help,
        agree_num=tb_thread.agree,
        disagree_num=tb_thread.disagree,
        reply_num=tb_thread.reply_num,
        view_num=tb_thread.view_num,
        share_num=tb_thread.share_num,
        create_time=datetime.fromtimestamp(tb_thread.create_time, SHANGHAI_TZ),
        last_time=datetime.fromtimestamp(tb_thread.last_time, SHANGHAI_TZ),
        thread_type=tb_thread.type,
        tab_id=tb_thread.tab_id,
        share_origin=convert_aiotieba_share_thread(tb_thread.share_origin),
    )


def convert_aiotieba_post(tb_post: Post) -> PostDTO:
    return PostDTO(
        pid=tb_post.pid,
        tid=tb_post.tid,
        fid=tb_post.fid,
        fname=tb_post.fname,
        author_id=tb_post.author_id,
        author=convert_aiotieba_postuser(tb_post.user),
        contents=convert_aiotieba_content_list(tb_post.contents.objs),
        sign=tb_post.sign,
        comments=convert_aiotieba_commentsp(tb_post.comments),
        is_aimeme=tb_post.is_aimeme,
        is_thread_author=tb_post.is_thread_author,
        agree_num=tb_post.agree,
        disagree_num=tb_post.disagree,
        reply_num=tb_post.reply_num,
        create_time=datetime.fromtimestamp(tb_post.create_time, SHANGHAI_TZ),
        floor=tb_post.floor,
    )


def convert_aiotieba_comment(tb_comment: Comment) -> CommentDTO:
    return CommentDTO(
        cid=tb_comment.pid,
        pid=tb_comment.ppid,
        tid=tb_comment.tid,
        fid=tb_comment.fid,
        fname=tb_comment.fname,
        author_id=tb_comment.author_id,
        author=convert_aiotieba_commentuser(tb_comment.user),
        contents=convert_aiotieba_content_list(tb_comment.contents.objs),
        reply_to_id=tb_comment.reply_to_id,
        is_thread_author=tb_comment.is_thread_author,
        agree_num=tb_comment.agree,
        disagree_num=tb_comment.disagree,
        create_time=datetime.fromtimestamp(tb_comment.create_time, SHANGHAI_TZ),
        floor=tb_comment.floor,
    )


def convert_aiotieba_commentsp(tb_post_comments: list[Comment_p]) -> list[CommentpDTO]:
    return [
        CommentpDTO(
            cid=comment.pid,
            pid=comment.ppid,
            tid=comment.tid,
            fid=comment.fid,
            fname=comment.fname,
            author_id=comment.author_id,
            contents=convert_aiotieba_content_list(comment.contents.objs),
            reply_to_id=comment.reply_to_id,
            is_thread_author=comment.is_thread_author,
            agree_num=comment.agree,
            disagree_num=comment.disagree,
            create_time=datetime.fromtimestamp(comment.create_time, SHANGHAI_TZ),
            floor=comment.floor,
        )
        for comment in tb_post_comments
    ]


def convert_aiotieba_pageinfo(page: AiotiebaPageType) -> PageInfoDTO:
    return PageInfoDTO(
        page_size=page.page_size,
        current_page=page.current_page,
        total_page=page.total_page,
        total_count=page.total_count,
        has_more=page.has_more,
        has_prev=page.has_prev,
    )


def convert_aiotieba_forum(forum: AiotiebaForumType) -> BaseForumDTO:
    return BaseForumDTO(
        fid=forum.fid,
        fname=forum.fname,
    )


def convert_aiotieba_threads(tb_threads: Threads) -> ThreadsDTO:
    return ThreadsDTO(
        objs=[convert_aiotieba_thread(tb_thread) for tb_thread in tb_threads.objs],
        page=convert_aiotieba_pageinfo(tb_threads.page),
        forum=convert_aiotieba_forum(tb_threads.forum),
    )


def convert_aiotieba_posts(tb_posts: Posts) -> PostsDTO:
    return PostsDTO(
        objs=[convert_aiotieba_post(tb_post) for tb_post in tb_posts.objs],
        page=convert_aiotieba_pageinfo(tb_posts.page),
        forum=convert_aiotieba_forum(tb_posts.forum),
    )


def convert_aiotieba_comments(tb_comments: Comments) -> CommentsDTO:
    return CommentsDTO(
        objs=[convert_aiotieba_comment(tb_comment) for tb_comment in tb_comments.objs],
        page=convert_aiotieba_pageinfo(tb_comments.page),
        forum=convert_aiotieba_forum(tb_comments.forum),
    )
