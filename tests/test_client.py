from __future__ import annotations

import asyncio
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
    client._retry_strategy = AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_none(),
        retry=retry_if_exception_type((
            OSError,
            asyncio.TimeoutError,
            ConnectionError,
            RetriableApiError,
        )),
        reraise=True,
    )


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
