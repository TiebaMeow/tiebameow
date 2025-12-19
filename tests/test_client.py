from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiotieba.exception import HTTPStatusError

from tiebameow.client.tieba_client import Client


@pytest.fixture(autouse=True)
def _no_tenacity_wait() -> Iterator[None]:
    # 避免 tenacity 默认指数退避导致测试变慢/偶发超时。
    with patch("tiebameow.client.tieba_client._wait_after_error", new=lambda _retry_state: 0.0):
        yield


@pytest.mark.asyncio
async def test_client_init() -> None:
    client = Client()
    assert client._limiter is None
    assert client._semaphore is None
    assert client._cooldown_seconds_429 == 0.0


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
async def test_with_ensure_retry_success() -> None:
    # Test the retry logic with a mock method
    client = Client()

    mock_func = AsyncMock(return_value="success")

    # We need to decorate the mock function or a wrapper
    from tiebameow.client.tieba_client import with_ensure

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    res = await decorated_func(client)
    assert res == "success"
    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_with_ensure_retry_fail_then_success() -> None:
    client = Client()

    # Fail once with timeout, then succeed
    mock_func = AsyncMock(side_effect=[TimeoutError("timeout"), "success"])

    from tiebameow.client.tieba_client import with_ensure

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    res = await decorated_func(client)
    assert res == "success"
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_with_ensure_retry_429() -> None:
    client = Client(cooldown_seconds_429=0.1)

    # Fail with 429, then succeed
    err_429 = HTTPStatusError(429, "Too Many Requests")
    mock_func = AsyncMock(side_effect=[err_429, "success"])

    from tiebameow.client.tieba_client import with_ensure

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    # Mock set_cooldown & asyncio.sleep to verify it's called without真实等待
    with (
        patch.object(client, "set_cooldown", new_callable=AsyncMock) as mock_cooldown,
        patch("tiebameow.client.tieba_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        res = await decorated_func(client)
        assert res == "success"
        assert mock_func.call_count == 2
        mock_cooldown.assert_awaited_once_with(0.1)
        mock_sleep.assert_any_await(0.1)


@pytest.mark.asyncio
async def test_with_ensure_unretriable() -> None:
    client = Client()

    # Fail with unretriable error
    mock_func = AsyncMock(side_effect=ValueError("Unknown error"))

    from tiebameow.client.tieba_client import with_ensure

    @with_ensure
    async def decorated_func(self: Client, *args: Any, **kwargs: Any) -> Any:
        return await mock_func(self, *args, **kwargs)

    # The wrapper catches UnretriableError and tries one last time without error handling
    # So we expect the original error to bubble up
    with pytest.raises(ValueError, match="Unknown error"):
        await decorated_func(client)

    # Should be called twice:
    # 1. Inside AsyncRetrying -> raises UnretriableError
    # 2. Inside outer except block -> raises ValueError
    assert mock_func.call_count == 2
