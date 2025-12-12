from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..models.dto import CommentDTO, PostDTO, ShareThreadDTO, ThreadDTO, UserDTO
from ..schemas.fragments import FRAG_MAP, Fragment, FragUnknownModel
from ..utils.time_utils import SHANGHAI_TZ

if TYPE_CHECKING:
    import aiotieba
    import aiotieba.api.get_threads
    import aiotieba.api.get_posts
    import aiotieba.api.get_comments

    type AiotiebaType = aiotieba.typing.Thread | aiotieba.typing.Post | aiotieba.typing.Comment
    type AiotiebaUserType = aiotieba.api.get_threads.UserInfo_t | aiotieba.api.get_posts.UserInfo_p | aiotieba.api.get_comments.UserInfo_c


def convert_aiotieba_fragment(obj: AiotiebaType) -> Fragment:
    source_type_name = type(obj).__name__
    target_model_name = source_type_name.rsplit("_", 1)[0]

    target_model = FRAG_MAP.get(target_model_name)

    if target_model is None:
        return FragUnknownModel(raw_data=repr(obj))

    data_dict = dataclasses.asdict(obj)
    return target_model(**data_dict)


def convert_aiotieba_content_list(contents: list[Any]) -> list[Fragment]:
    if not contents:
        return []
    return [convert_aiotieba_fragment(frag) for frag in contents]


def convert_aiotieba_user(user: AiotiebaUserType) -> UserDTO:
    return UserDTO(
        user_id=user.user_id,
        portrait=user.portrait,
        user_name=user.user_name,
        nick_name=user.nick_name,
        level=user.level,
        glevel=getattr(user, "glevel", None),
        ip=getattr(user, "ip", None),
        gender=user.gender.name if hasattr(user, "gender") else None,
        icons=user.icons if hasattr(user, "icons") else None,
        is_bawu=getattr(user, "is_bawu", None),
        is_vip=getattr(user, "is_vip", None),
        is_god=user.is_god,
        priv_like=user.priv_like.name if hasattr(user, "priv_like") else None,
        priv_reply=user.priv_reply.name if hasattr(user, "priv_reply") else None,
    )


def convert_aiotieba_share_thread(share_thread: aiotieba.api.get_threads.ShareThread) -> ShareThreadDTO:
    return ShareThreadDTO(
        pid=share_thread.pid,
        tid=share_thread.tid,
        fid=share_thread.fid,
        fname=share_thread.fname,
        author_id=share_thread.author_id,
        title=share_thread.title,
        contents=convert_aiotieba_content_list(share_thread.contents.objs),
    )


def convert_aiotieba_thread(tb_thread: aiotieba.typing.Thread) -> ThreadDTO:
    """
    将 aiotieba 的 Thread 对象转换为 tiebameow 的通用模型
    """
    return ThreadDTO(
        pid=tb_thread.pid,
        tid=tb_thread.tid,
        fid=tb_thread.fid,
        fname=tb_thread.fname,
        author_id=tb_thread.author_id,
        author=convert_aiotieba_user(tb_thread.user),
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


def convert_aiotieba_post(tb_post: aiotieba.typing.Post) -> PostDTO:
    return PostDTO(
        pid=tb_post.pid,
        tid=tb_post.tid,
        fid=tb_post.fid,
        fname=tb_post.fname,
        author_id=tb_post.author_id,
        author=convert_aiotieba_user(tb_post.user),
        contents=convert_aiotieba_content_list(tb_post.contents.objs),
        sign=tb_post.sign,
        is_aimeme=tb_post.is_aimeme,
        is_thread_author=tb_post.is_thread_author,
        agree_num=tb_post.agree,
        disagree_num=tb_post.disagree,
        reply_num=tb_post.reply_num,
        create_time=datetime.fromtimestamp(tb_post.create_time, SHANGHAI_TZ),
        floor=tb_post.floor,
    )


def convert_aiotieba_comment(tb_comment: aiotieba.typing.Comment) -> CommentDTO:
    return CommentDTO(
        cid=tb_comment.pid,
        pid=tb_comment.ppid,
        tid=tb_comment.tid,
        fid=tb_comment.fid,
        fname=tb_comment.fname,
        author_id=tb_comment.author_id,
        author=convert_aiotieba_user(tb_comment.user),
        contents=convert_aiotieba_content_list(tb_comment.contents.objs),
        reply_to_id=tb_comment.reply_to_id,
        is_thread_author=tb_comment.is_thread_author,
        agree_num=tb_comment.agree,
        disagree_num=tb_comment.disagree,
        create_time=datetime.fromtimestamp(tb_comment.create_time, SHANGHAI_TZ),
        floor=tb_comment.floor,
    )
