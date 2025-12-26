from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

import aiotieba as tb
from aiohttp import ClientError, ServerConnectionError, ServerTimeoutError
from aiotieba.exception import BoolResponse, HTTPStatusError, IntResponse, StrResponse, TiebaServerError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..parser import (
    convert_aiotieba_comments,
    convert_aiotieba_posts,
    convert_aiotieba_threads,
    convert_aiotieba_userinfo,
)
from ..utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from aiolimiter import AsyncLimiter
    from aiotieba.api.get_bawu_blacklist._classdef import BawuBlacklistUsers
    from aiotieba.api.get_bawu_postlogs._classdef import Postlogs
    from aiotieba.api.get_bawu_userlogs._classdef import Userlogs
    from aiotieba.api.get_follow_forums._classdef import FollowForums
    from aiotieba.api.get_tab_map._classdef import TabMap
    from aiotieba.api.get_user_contents._classdef import UserPostss, UserThreads
    from aiotieba.api.tieba_uid2user_info._classdef import UserInfo_TUid
    from aiotieba.typing import Comments, Posts, Threads, UserInfo

    from ..models.dto import CommentsDTO, PostsDTO, ThreadsDTO, UserInfoDTO


class AiotiebaError(Exception):
    """基础 aiotieba API 异常"""

    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class RetriableApiError(AiotiebaError):
    """aiotieba 返回的可重试的异常"""


class UnretriableApiError(AiotiebaError):
    """aiotieba 返回的无法重试的异常"""


class ErrorHandler:
    RETRIABLE_CODES: set[int] = {
        -65536,  # 超时
        11,  # 系统繁忙
        77,  # 操作失败
        408,  # 请求超时
        429,  # 过多请求
        4011,  # 需要验证码
        110001,  # 未知错误
        110004,  # tieba_uid2user_info 接口错误
        220034,  # 操作过于频繁
        230871,  # 发贴/删贴过于频繁
        300000,  # 旧版客户端API无法封禁用户名为空用户
        1989005,  # 加载数据失败
        2210002,  # 系统错误
        28113295,
    }

    @classmethod
    def check(cls, result: Any) -> None:
        """解析 aiotieba 返回对象中的 err 字段"""
        err = getattr(result, "err", None)
        if err is None:
            return

        if isinstance(err, (HTTPStatusError, TiebaServerError)):
            code = err.code
            msg = err.msg

            if code in cls.RETRIABLE_CODES:
                raise RetriableApiError(code, msg)

            raise UnretriableApiError(code, msg)

        elif isinstance(err, Exception):
            raise err


def with_ensure[F: Callable[..., Awaitable[Any]]](func: F) -> F:
    """装饰器：为 aiotieba.Client 的方法添加重试和限流支持。"""

    @wraps(func)
    async def wrapper(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await self._request_core(func, *args, **kwargs)

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
        cooldown_429: float = 0.0,
        retry_attempts: int = 3,
        wait_initial: float = 0.5,
        wait_max: float = 5.0,
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
        self._cooldown_429 = cooldown_429
        self._cooldown_until: float = 0.0
        self._cooldown_lock = asyncio.Lock()
        self._retry_attempts = retry_attempts
        self._wait_initial = wait_initial
        self._wait_max = wait_max

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

    @property
    def limiter(self) -> AsyncLimiter | None:
        """获取速率限制器。"""
        return self._limiter

    @property
    def semaphore(self) -> asyncio.Semaphore | None:
        """获取信号量。"""
        return self._semaphore

    @asynccontextmanager
    async def _with_limits(self) -> AsyncGenerator[None, None]:
        """内部限流上下文管理器"""
        async with AsyncExitStack() as stack:
            if self._limiter:
                await stack.enter_async_context(self._limiter)
            if self._semaphore:
                await stack.enter_async_context(self._semaphore)
            yield

    def _retry_strategy(self) -> AsyncRetrying:
        """为每次请求创建重试器"""
        return AsyncRetrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential_jitter(initial=self._wait_initial, max=self._wait_max),
            retry=retry_if_exception_type((
                OSError,
                TimeoutError,
                ConnectionError,
                ServerTimeoutError,
                ServerConnectionError,
                ClientError,
                HTTPStatusError,
                TiebaServerError,
                RetriableApiError,
            )),
            reraise=True,
        )

    async def _update_cooldown_until(self) -> None:
        """延长全局冷却截止时间"""
        async with self._cooldown_lock:
            new_until = time.monotonic() + self._cooldown_429
            if new_until > self._cooldown_until:
                self._cooldown_until = new_until

    async def _get_cooldown_wait(self) -> float:
        """获取当前需要等待的全局冷却时间（秒）"""
        async with self._cooldown_lock:
            now = time.monotonic()
            return max(0.0, self._cooldown_until - now)

    async def _request_core(self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """核心调度逻辑，处理限流、熔断和错误转换"""
        retrying = self._retry_strategy()
        async for attempt in retrying:
            with attempt:
                wait_time = await self._get_cooldown_wait()
                if wait_time > 0:
                    logger.debug("Global cooldown active. Waiting for {:.1f}s", wait_time)
                    await asyncio.sleep(wait_time)

                async with self._with_limits():
                    result = await func(self, *args, **kwargs)

                try:
                    ErrorHandler.check(result)
                except RetriableApiError as e:
                    if e.code == 429 and self._cooldown_429 > 0:
                        await self._update_cooldown_until()
                    logger.warning("Retrying {} due to: {}", func.__name__, e)
                    raise
                except UnretriableApiError:
                    raise

                return result

    # 以下为直接返回DTO模型的封装方法

    # 获取贴子内容 #

    async def get_threads_dto(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.ThreadSortType = tb.ThreadSortType.REPLY,
        is_good: bool = False,
    ) -> ThreadsDTO:
        """获取指定贴吧的主题列表，并转换为通用DTO模型。"""
        threads = await self.get_threads(fname_or_fid, pn, rn=rn, sort=sort, is_good=is_good)
        return convert_aiotieba_threads(threads)

    async def get_posts_dto(
        self,
        tid: int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.PostSortType = tb.PostSortType.ASC,
        only_thread_author: bool = False,
        with_comments: bool = False,
        comment_sort_by_agree: bool = True,
        comment_rn: int = 4,
    ) -> PostsDTO:
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
        return convert_aiotieba_posts(posts)

    async def get_comments_dto(
        self,
        tid: int,
        pid: int,
        /,
        pn: int = 1,
        *,
        is_comment: bool = False,
    ) -> CommentsDTO:
        """获取指定回复的楼中楼列表，并转换为通用DTO模型。"""
        comments = await self.get_comments(tid, pid, pn, is_comment=is_comment)
        return convert_aiotieba_comments(comments)

    # 获取用户信息 #

    async def anyid2user_info_dto(self, uid: int | str, is_tieba_uid: bool = True) -> UserInfoDTO:
        """
        根据任意用户ID获取完整的用户信息，并转换为通用DTO模型。

        Args:
            uid: 用户ID，可以是贴吧ID、user_id、portrait或用户名。
            is_tieba_uid: 指示uid是否为贴吧UID，默认为True。
        """
        if is_tieba_uid and isinstance(uid, int):
            user_tuid = await self.tieba_uid2user_info(uid)
            user = await self.get_user_info(user_tuid.user_id)
        else:
            user = await self.get_user_info(uid)
        return convert_aiotieba_userinfo(user)

    async def get_nickname_old(self, user_id: int) -> str:
        user_info = await self.get_user_info(user_id, require=tb.ReqUInfo.BASIC)
        return str(user_info.nick_name_old)

    # 以下为重写的部分 aiotieba.Client API
    # 添加了 @with_ensure 装饰器以启用重试机制
    # 完全拦截过于魔法，这里仅重写部分常用API

    # 获取贴子内容 #

    @with_ensure
    async def get_threads(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        rn: int = 30,
        sort: tb.ThreadSortType = tb.ThreadSortType.REPLY,
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
        sort: tb.PostSortType = tb.PostSortType.ASC,
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

    # 获取用户信息 #

    @with_ensure
    async def tieba_uid2user_info(self, tieba_uid: int) -> UserInfo_TUid:
        return await super().tieba_uid2user_info(tieba_uid)

    @with_ensure
    async def get_user_info(self, id_: str | int, /, require: tb.ReqUInfo = tb.ReqUInfo.ALL) -> UserInfo:
        return await super().get_user_info(id_, require)

    @with_ensure
    async def get_self_info(self, require: tb.ReqUInfo = tb.ReqUInfo.ALL) -> UserInfo:
        return await super().get_self_info(require)

    @with_ensure
    async def get_follow_forums(self, id_: str | int, /, pn: int = 1, *, rn: int = 50) -> FollowForums:
        return await super().get_follow_forums(id_, pn, rn=rn)

    # 获取贴吧信息 #

    @with_ensure
    async def get_fid(self, fname: str) -> IntResponse:
        return await super().get_fid(fname)

    @with_ensure
    async def get_fname(self, fid: int) -> StrResponse:
        return await super().get_fname(fid)

    @with_ensure
    async def get_tab_map(self, fname_or_fid: str | int) -> TabMap:
        return await super().get_tab_map(fname_or_fid)

    # 吧务查询 #

    @with_ensure
    async def get_bawu_blacklist(self, fname_or_fid: str | int, /, pn: int = 1) -> BawuBlacklistUsers:
        return await super().get_bawu_blacklist(fname_or_fid, pn)

    @with_ensure
    async def get_bawu_postlogs(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        search_value: str = "",
        search_type: tb.BawuSearchType = tb.BawuSearchType.USER,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        op_type: int = 0,
    ) -> Postlogs:
        return await super().get_bawu_postlogs(
            fname_or_fid,
            pn,
            search_value=search_value,
            search_type=search_type,
            start_dt=start_dt,
            end_dt=end_dt,
            op_type=op_type,
        )

    @with_ensure
    async def get_bawu_userlogs(
        self,
        fname_or_fid: str | int,
        /,
        pn: int = 1,
        *,
        search_value: str = "",
        search_type: tb.BawuSearchType = tb.BawuSearchType.USER,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        op_type: int = 0,
    ) -> Userlogs:
        return await super().get_bawu_userlogs(
            fname_or_fid,
            pn,
            search_value=search_value,
            search_type=search_type,
            start_dt=start_dt,
            end_dt=end_dt,
            op_type=op_type,
        )

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
