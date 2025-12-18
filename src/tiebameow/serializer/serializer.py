from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from ..models.dto import CommentDTO, PostDTO, ThreadDTO

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "serialize",
    "deserialize",
    "deserialize_thread",
    "deserialize_post",
    "deserialize_comment",
]


def serialize(obj: Any) -> Any:
    """将对象序列化为 JSON 可用的字典或列表。"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def _normalize_contents(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("objs", []) or []
    return []


def _normalize_user(data: dict[str, Any]) -> None:
    if "author" not in data and "user" in data:
        data["author"] = data["user"]


def _preprocess_thread(data: Mapping[str, Any]) -> dict[str, Any]:
    d = dict(data)
    if "contents" in d:
        d["contents"] = _normalize_contents(d["contents"])

    _normalize_user(d)

    if "share_origin" in d and isinstance(d["share_origin"], dict):
        so = dict(d["share_origin"])
        if "contents" in so:
            so["contents"] = _normalize_contents(so["contents"])
        d["share_origin"] = so

    return d


def _preprocess_post(data: Mapping[str, Any]) -> dict[str, Any]:
    d = dict(data)
    if "contents" in d:
        d["contents"] = _normalize_contents(d["contents"])

    _normalize_user(d)

    return d


def _preprocess_comment(data: Mapping[str, Any]) -> dict[str, Any]:
    d = dict(data)
    if "contents" in d:
        d["contents"] = _normalize_contents(d["contents"])

    _normalize_user(d)

    return d


def deserialize_thread(data: Mapping[str, Any]) -> ThreadDTO:
    """将 JSON/dict 反序列化为 ThreadDTO 对象。"""
    return ThreadDTO.model_validate(_preprocess_thread(data))


def deserialize_post(data: Mapping[str, Any]) -> PostDTO:
    """将 JSON/dict 反序列化为 PostDTO 对象。"""
    return PostDTO.model_validate(_preprocess_post(data))


def deserialize_comment(data: Mapping[str, Any]) -> CommentDTO:
    """将 JSON/dict 反序列化为 CommentDTO 对象。"""
    return CommentDTO.model_validate(_preprocess_comment(data))


@overload
def deserialize(item_type: Literal["thread"], data: Mapping[str, Any]) -> ThreadDTO: ...


@overload
def deserialize(item_type: Literal["post"], data: Mapping[str, Any]) -> PostDTO: ...


@overload
def deserialize(item_type: Literal["comment"], data: Mapping[str, Any]) -> CommentDTO: ...


def deserialize(
    item_type: Literal["thread", "post", "comment"], data: Mapping[str, Any]
) -> ThreadDTO | PostDTO | CommentDTO:
    """根据类型进行通用反序列化。"""
    if item_type == "thread":
        return deserialize_thread(data)
    if item_type == "post":
        return deserialize_post(data)
    if item_type == "comment":
        return deserialize_comment(data)
    raise ValueError(f"Unsupported item_type: {item_type}")
