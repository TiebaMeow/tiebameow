from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

import aiotieba as tb
from aiotieba import ReqUInfo
from aiotieba.api._classdef import UserInfo
from aiotieba.api.tieba_uid2user_info._classdef import UserInfo_TUid
from aiotieba.enums import PostSortType, ThreadSortType
from aiotieba.exception import BoolResponse, HTTPStatusError, IntResponse, TiebaServerError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    wait_fixed,
)

from ..parser import (
    convert_aiotieba_comment,
    convert_aiotieba_post,
    convert_aiotieba_thread,
    convert_aiotieba_userinfo,
)
from ..utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiolimiter import AsyncLimiter
    from aiotieba.api.get_user_contents._classdef import UserPostss, UserThreads
    from aiotieba.api.tieba_uid2user_info._classdef import UserInfo_TUid
    from aiotieba.typing import Comments, Posts, Threads, UserInfo

    from ..models.dto import CommentDTO, PostDTO, ThreadDTO, UserInfoDTO


class NeedRetryError(Exception):
    pass


class UnretriableError(Exception):
    pass


def _wait_after_error(retry_state: RetryCallState) -> float:
    """
    tenacity的等待回调函数。

    将429错误交由全局冷却逻辑处理，其他错误使用指数退避等待策略。
    """
    outcome = retry_state.outcome
    if outcome is None:
        return wait_exponential_jitter(initial=0.5, max=5.0)(retry_state)

    exc = outcome.exception()
    if isinstance(exc, HTTPStatusError) and exc.code == 429:
        # 如果设置了全局冷却时间，则由with_ensure内部处理等待，这里返回0
        # 否则，将429视为普通错误，使用指数退避
        client = retry_state.args[0]
        if getattr(client, "_cooldown_seconds_429", 0) > 0:
            return wait_fixed(0)(retry_state)

    return wait_exponential_jitter(initial=0.5, max=5.0)(retry_state)


def with_ensure[F: Callable[..., Awaitable[Any]]](func: F) -> F:
    """为Client方法添加重试机制的装饰器。"""

    @wraps(func)
    async def wrapper(self: Client, *args: Any, **kwargs: Any) -> Any:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=_wait_after_error,
                retry=retry_if_exception_type((
                    OSError,
                    asyncio.TimeoutError,
                    TimeoutError,
                    ConnectionError,
                    HTTPStatusError,
                    TiebaServerError,
                    NeedRetryError,
                )),
                reraise=True,
            ):
                with attempt:
                    try:
                        async with self.rate_limiter():
                            result = await func(self, *args, **kwargs)
                        err = getattr(result, "err", None)
                        if err is not None:
                            raise err
                        return result
                    except (HTTPStatusError, TiebaServerError) as err:
                        if err.code == 429:
                            if self._cooldown_seconds_429 > 0:
                                wait_seconds = self._cooldown_seconds_429
                                await self.set_cooldown(wait_seconds)
                                await asyncio.sleep(wait_seconds)
                            logger.debug(f"{func.__name__} received 429 Too Many Requests, retrying...")
                            raise
                        elif err.code in {
                            -65536,
                            11,
                            77,
                            408,
                            4011,
                            110001,
                            220034,
                            230871,
                            300000,
                            1989005,
                            2210002,
                            28113295,
                        }:
                            logger.debug(f"{func.__name__} returned retriable error: {err}, retrying...")
                            raise
                        else:
                            logger.exception(f"{func.__name__} returned unretriable error: {err}")
                            raise UnretriableError from err
                    except Exception as e:
                        if "Connection timeout" in str(e):
                            raise
                        else:
                            logger.exception(f"{func.__name__} raised unretriable exception: {e}")
                            raise UnretriableError from e
        except Exception as e:
            logger.exception(f"{func.__name__}: {e}")
            # 最后一次尝试，不再捕获异常
            async with self.rate_limiter():
                return await func(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class Client(tb.Client):  # type: ignore[misc]
    """扩展的aiotieba客户端，添加了自定义的请求限流和并发控制功能。

    该客户端继承自aiotieba.Client，并在其基础上实现了速率限制和并发控制。
    通过装饰器和上下文管理器的方式，为所有API调用提供统一的速率限制和并发控制。
    同时还添加了对特定错误码的重试机制，以提高请求的成功率。
    """

    def __init__(
        self,
        *args: Any,
        limiter: AsyncLimiter | None = None,
        semaphore: asyncio.Semaphore | None = None,
        cooldown_seconds_429: float = 0.0,
        **kwargs: Any,
    ):
        """初始化扩展的aiotieba客户端。

        Args:
            *args: 传递给父类构造函数的参数。
            limiter: 速率限制器，用于控制每秒请求数。
            semaphore: 信号量，用于控制最大并发数。
            cooldown_seconds: 触发429时的全局冷却秒数。
            **kwargs: 传递给父类构造函数的关键字参数。
        """
        super().__init__(*args, **kwargs)
        self._limiter = limiter
        self._semaphore = semaphore
        self._cooldown_seconds_429 = cooldown_seconds_429
        self._cooldown_until: float = 0.0
        self._cooldown_lock = asyncio.Lock()

    async def __aenter__(self) -> Client:
        await super().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: object = None,
    ) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def set_cooldown(self, duration: float) -> None:
        """设置全局冷却时间，防止多个任务同时设置。"""
        async with self._cooldown_lock:
            cooldown_end_time = time.monotonic() + duration
            self._cooldown_until = max(self._cooldown_until, cooldown_end_time)

    @property
    def limiter(self) -> AsyncLimiter | None:
        """获取速率限制器。"""
        return self._limiter

    @property
    def semaphore(self) -> asyncio.Semaphore | None:
        """获取信号量。"""
        return self._semaphore

    @asynccontextmanager
    async def rate_limiter(self) -> AsyncGenerator[None, None]:
        """获取速率限制和并发控制的上下文管理器，并处理全局冷却。"""
        now = time.monotonic()
        if now < self._cooldown_until:
            wait_time = self._cooldown_until - now
            logger.debug("Global cooldown active. Waiting for %.1f seconds.", wait_time)
            await asyncio.sleep(wait_time)

        async with AsyncExitStack() as stack:
            if self.limiter is not None:
                await stack.enter_async_context(self.limiter)
            if self.semaphore is not None:
                await stack.enter_async_context(self.semaphore)
            yield

    async def get_threads_dto(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: ThreadSortType = ThreadSortType.REPLY,
        is_good: bool = False,
    ) -> list[ThreadDTO]:
        """获取指定贴吧的主题列表，并转换为通用DTO模型。"""
        threads = await self.get_threads(fname_or_fid, pn, rn=rn, sort=sort, is_good=is_good)
        return [convert_aiotieba_thread(t) for t in threads]

    async def get_posts_dto(
        self,
        tid: int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.PostSortType = PostSortType.ASC,
        only_thread_author: bool = False,
        with_comments: bool = False,
        comment_sort_by_agree: bool = True,
        comment_rn: int = 4,
    ) -> list[PostDTO]:
        """获取指定主题贴的回复列表，并转换为通用DTO模型。"""
        posts = await self.get_posts(
            tid,
            pn,
            rn=rn,
            sort=sort,
            only_thread_author=only_thread_author,
            with_comments=with_comments,
            comment_sort_by_agree=comment_sort_by_agree,
            comment_rn=comment_rn,
        )
        return [convert_aiotieba_post(p) for p in posts]

    async def get_comments_dto(
        self,
        tid: int,
        pid: int,
        /,
        pn: int = 1,
        *,
        is_comment: bool = False,
    ) -> list[CommentDTO]:
        """获取指定回复的楼中楼列表，并转换为通用DTO模型。"""
        comments = await self.get_comments(tid, pid, pn, is_comment=is_comment)
        return [convert_aiotieba_comment(c) for c in comments]

    async def anyid_to_user_info(self, uid: int | str, is_tieba_uid: bool = True) -> UserInfoDTO:
        """
        根据任意用户ID获取完整的用户信息，并转换为通用DTO模型。

        Args:
            uid: 用户ID，可以是贴吧UID或用户ID。
            is_tieba_uid: 指示uid是否为贴吧UID，默认为True。
        """
        if is_tieba_uid and isinstance(uid, int):
            user_tuid = await self.tieba_uid2user_info(uid)
            user = await self.get_user_info(user_tuid.user_id)
        else:
            user = await self.get_user_info(uid)
        return convert_aiotieba_userinfo(user)

    async def get_nickname_old(self, user_id: int) -> str:
        user_info = await self.get_user_info(user_id, require=ReqUInfo.BASIC)
        return str(user_info.nick_name_old)

    # 以下为重写的 aiotieba.Client API，添加了 @with_ensure 装饰器

    # 获取贴子内容 #

    @with_ensure
    async def get_threads(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.ThreadSortType = ThreadSortType.REPLY,
        is_good: bool = False,
    ) -> Threads:
        return await super().get_threads(fname_or_fid, pn, rn=rn, sort=sort, is_good=is_good)

    @with_ensure
    async def get_posts(
        self,
        tid: int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.PostSortType = PostSortType.ASC,
        only_thread_author: bool = False,
        with_comments: bool = False,
        comment_sort_by_agree: bool = True,
        comment_rn: int = 4,
    ) -> Posts:
        return await super().get_posts(
            tid,
            pn,
            rn=rn,
            sort=sort,
            only_thread_author=only_thread_author,
            with_comments=with_comments,
            comment_sort_by_agree=comment_sort_by_agree,
            comment_rn=comment_rn,
        )

    @with_ensure
    async def get_comments(
        self,
        tid: int,
        pid: int,
        /,
        pn: int = 1,
        *,
        is_comment: bool = False,
    ) -> Comments:
        return await super().get_comments(tid, pid, pn, is_comment=is_comment)

    @with_ensure
    async def get_user_threads(
        self,
        id_: str | int | None = None,
        pn: int = 1,
        *,
        public_only: bool = False,
    ) -> UserThreads:
        return await super().get_user_threads(id_, pn, public_only=public_only)

    @with_ensure
    async def get_user_posts(
        self,
        id_: str | int | None = None,
        pn: int = 1,
        *,
        rn: int = 20,
    ) -> UserPostss:
        return await super().get_user_posts(id_, pn, rn=rn)

    # 获取用户或贴吧信息 #

    @with_ensure
    async def tieba_uid2user_info(self, tieba_uid: int) -> UserInfo_TUid:
        return await super().tieba_uid2user_info(tieba_uid)

    @with_ensure
    async def get_user_info(self, id_: str | int, /, require: ReqUInfo = ReqUInfo.ALL) -> UserInfo:
        return await super().get_user_info(id_, require)

    @with_ensure
    async def get_self_info(self, require: ReqUInfo = ReqUInfo.ALL) -> UserInfo:
        return await super().get_self_info(require)

    @with_ensure
    async def get_fid(self, fname: str) -> IntResponse:
        return await super().get_fid(fname)

    # 吧务操作 #

    @with_ensure
    async def del_thread(self, fname_or_fid: str | int, /, tid: int) -> BoolResponse:
        return await super().del_thread(fname_or_fid, tid)

    @with_ensure
    async def del_post(self, fname_or_fid: str | int, /, tid: int, pid: int) -> BoolResponse:
        return await super().del_post(fname_or_fid, tid, pid)

    @with_ensure
    async def add_bawu_blacklist(self, fname_or_fid: str | int, /, id_: str | int) -> BoolResponse:
        return await super().add_bawu_blacklist(fname_or_fid, id_)

    @with_ensure
    async def del_bawu_blacklist(self, fname_or_fid: str | int, /, id_: str | int) -> BoolResponse:
        return await super().del_bawu_blacklist(fname_or_fid, id_)

    @with_ensure
    async def block(
        self, fname_or_fid: str | int, /, id_: str | int, *, day: int = 1, reason: str = ""
    ) -> BoolResponse:
        return await super().block(fname_or_fid, id_, day=day, reason=reason)

    @with_ensure
    async def unblock(self, fname_or_fid: str | int, /, id_: str | int) -> BoolResponse:
        return await super().unblock(fname_or_fid, id_)

    @with_ensure
    async def good(self, fname_or_fid: str | int, /, tid: int, *, cname: str = "") -> BoolResponse:
        return await super().good(fname_or_fid, tid, cname=cname)

    @with_ensure
    async def ungood(self, fname_or_fid: str | int, /, tid: int) -> BoolResponse:
        return await super().ungood(fname_or_fid, tid)

    @with_ensure
    async def top(self, fname_or_fid: str | int, /, tid: int, *, is_vip: bool = False) -> BoolResponse:
        return await super().top(fname_or_fid, tid, is_vip=is_vip)

    @with_ensure
    async def untop(self, fname_or_fid: str | int, /, tid: int, *, is_vip: bool = False) -> BoolResponse:
        return await super().untop(fname_or_fid, tid, is_vip=is_vip)
