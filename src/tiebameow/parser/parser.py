from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..models.dto import ThreadDTO
from ..schemas.fragments import FRAG_MAP, Fragment, FragUnknownModel
from ..utils.time_utils import SHANGHAI_TZ

if TYPE_CHECKING:
    import aiotieba.typing as aiotieba

    type AiotiebaType = aiotieba.Thread | aiotieba.Post | aiotieba.Comment


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


def convert_aiotieba_thread(tb_thread: aiotieba.Thread) -> ThreadDTO:
    """
    将 aiotieba 的 Thread 对象转换为 tiebameow 的通用模型
    """
    return ThreadDTO(
        tid=tb_thread.tid,
        fid=tb_thread.fid,
        author_id=tb_thread.user.user_id,
        title=tb_thread.title,
        text=tb_thread.text,
        contents=convert_aiotieba_content_list(tb_thread.contents.objs),
        create_time=datetime.fromtimestamp(tb_thread.create_time, SHANGHAI_TZ),
        last_time=datetime.fromtimestamp(tb_thread.last_time, SHANGHAI_TZ),
        reply_num=tb_thread.reply_num,
    )
