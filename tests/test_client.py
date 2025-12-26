from __future__ import annotations

import asyncio
import time
import types
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, patch

import pytest
from aiotieba.exception import HTTPStatusError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_none

from tiebameow.client.tieba_client import Client, RetriableApiError, UnretriableApiError, with_ensure


class _Result(NamedTuple):
    err: object | None = None


class _AsyncCM:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> None:
        self.entered += 1

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.exited += 1


def _set_no_wait_retry(client: Client, *, attempts: int = 3) -> None:
    def _strategy(self: Client) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_none(),
            retry=retry_if_exception_type((
                OSError,
                TimeoutError,
                ConnectionError,
                RetriableApiError,
            )),
            reraise=True,
        )

    # 以实例属性覆盖方法，便于测试自定义重试配置。
    client._retry_strategy = types.MethodType(_strategy, client)  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_client_init() -> None:
    client = Client()
    assert client._limiter is None
    assert client._semaphore is None
    assert client._cooldown_429 == 0.0


@pytest.mark.asyncio
async def test_client_context_manager() -> None:
    client = Client()
    with (
        patch("tiebameow.client.tieba_client.tb.Client.__aenter__", new_callable=AsyncMock) as mock_aenter,
        patch("tiebameow.client.tieba_client.tb.Client.__aexit__", new_callable=AsyncMock) as mock_aexit,
    ):
        async with client as c:
            assert c is client

        mock_aenter.assert_awaited_once()
        mock_aexit.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_limits_enters_limiter_and_semaphore() -> None:
    limiter = _AsyncCM()
    semaphore = _AsyncCM()
    client = Client(limiter=limiter, semaphore=semaphore)

    async with client._with_limits():
        pass

    assert limiter.entered == 1
    assert limiter.exited == 1
    assert semaphore.entered == 1
    assert semaphore.exited == 1


@pytest.mark.asyncio
async def test_with_ensure_retry_success() -> None:
    client = Client()
    _set_no_wait_retry(client)

    mock_func = AsyncMock(return_value="success")

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    res = await decorated_func(client)
    assert res == "success"
    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_with_ensure_retry_fail_then_success() -> None:
    client = Client()
    _set_no_wait_retry(client, attempts=2)

    mock_func = AsyncMock(side_effect=[TimeoutError("timeout"), "success"])

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    res = await decorated_func(client)
    assert res == "success"
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_request_core_sets_global_cooldown_on_429() -> None:
    client = Client(cooldown_429=0.1)
    _set_no_wait_retry(client, attempts=2)

    # 第一次返回携带 err=429 的结果，触发 RetriableApiError(429) 并设置全局冷却；第二次正常。
    err_429 = HTTPStatusError(429, "Too Many Requests")
    mock_func = AsyncMock(side_effect=[_Result(err_429), _Result(None)])

    with (
        patch("tiebameow.client.tieba_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("tiebameow.client.tieba_client.time.monotonic", new=lambda: 0.0),
    ):

        async def call(self: Client) -> Any:
            return await mock_func(self)

        res = await client._request_core(call)

    assert isinstance(res, _Result)
    assert mock_func.call_count == 2
    mock_sleep.assert_any_await(0.1)


@pytest.mark.asyncio
async def test_request_core_critical_error_no_retry() -> None:
    client = Client()
    _set_no_wait_retry(client, attempts=3)

    err_999 = HTTPStatusError(999, "Critical")
    mock_func = AsyncMock(return_value=_Result(err_999))

    async def call(self: Client) -> Any:
        return await mock_func(self)

    with pytest.raises(UnretriableApiError):
        await client._request_core(call)

    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_wrapped_get_threads_calls_super() -> None:
    client = Client()
    _set_no_wait_retry(client)

    with patch("tiebameow.client.tieba_client.tb.Client.get_threads", new_callable=AsyncMock) as mock_super:
        mock_super.return_value = "threads"
        res = await client.get_threads("test", 1, rn=30)

    assert res == "threads"
    mock_super.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_share_retry_state() -> None:
    client = Client()
    _set_no_wait_retry(client, attempts=2)

    # 每个并发请求各自第一次超时、第二次成功。
    calls_by_task: dict[str, int] = {}

    async def call(self: Client) -> _Result:
        task = asyncio.current_task()
        assert task is not None
        name = task.get_name()
        calls_by_task[name] = calls_by_task.get(name, 0) + 1
        if calls_by_task[name] == 1:
            raise TimeoutError("timeout")
        return _Result(None)

    t1 = asyncio.create_task(client._request_core(call), name="t1")
    t2 = asyncio.create_task(client._request_core(call), name="t2")
    res1, res2 = await asyncio.gather(t1, t2)

    assert isinstance(res1, _Result)
    assert isinstance(res2, _Result)
    assert calls_by_task["t1"] == 2
    assert calls_by_task["t2"] == 2


@pytest.mark.asyncio
async def test_cooldown_until_never_decreases_under_concurrency() -> None:
    client = Client(cooldown_429=0.1)

    # 预先设置一个“更远的冷却截止时间”，后续更新不应把它覆盖为更小值。
    initial = time.monotonic() + 10.0
    client._cooldown_until = initial

    await asyncio.gather(client._update_cooldown_until(), client._update_cooldown_until())
    assert client._cooldown_until >= initial
