from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tiebameow.models.dto import PostDTO, PostUserDTO, ThreadDTO, ThreadUserDTO
from tiebameow.renderer.context import Base64Context
from tiebameow.renderer.core.playwright import PlaywrightCore
from tiebameow.renderer.renderer import Renderer

# --- Test PlaywrightCore ---


@pytest.mark.asyncio
async def test_playwright_core_launch():
    with patch("playwright.async_api.async_playwright") as mock_playwright:
        mock_playwright_context = AsyncMock()
        mock_playwright.return_value = mock_playwright_context

        mock_browser = AsyncMock()
        mock_playwright_context.start.return_value = mock_playwright_context
        mock_playwright_context.chromium.launch.return_value = mock_browser

        core = PlaywrightCore()
        await core.launch()

        assert core.playwright is not None
        assert core.browser is not None
        mock_playwright_context.chromium.launch.assert_called_once()


@pytest.mark.asyncio
async def test_playwright_core_close():
    core = PlaywrightCore()
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    core.browser = mock_browser
    core.playwright = mock_playwright

    await core.close()

    mock_browser.close.assert_called_once()
    mock_playwright.stop.assert_called_once()
    assert core.browser is None
    assert core.playwright is None


# --- Test Renderer ---


@pytest.fixture
def mock_core():
    core = MagicMock(spec=PlaywrightCore)
    core.render = AsyncMock(return_value=b"image_bytes")
    core.close = AsyncMock()
    return core


@pytest.fixture
def mock_context():
    # Create the instance that will be returned by the context manager
    context_instance = MagicMock()
    context_instance.get_portrait_url = AsyncMock(return_value="http://fake.url/portrait")
    context_instance.get_image_url_list = AsyncMock(return_value=[])
    context_instance.get_forum_icon_url = AsyncMock(return_value="http://fake.url/icon")
    # __aenter__ must be an async method that returns the instance
    context_instance.__aenter__ = AsyncMock(return_value=context_instance)
    context_instance.__aexit__ = AsyncMock(return_value=None)
    context_instance.close = AsyncMock()

    # The context class/factory
    context_class = MagicMock()
    context_class.return_value = context_instance
    return context_class


@pytest.fixture
def renderer(mock_core, mock_context):
    return Renderer(core=mock_core, context=mock_context)


@pytest.mark.asyncio
async def test_renderer_render_html(renderer):
    # Mock jinja2 environment and template
    mock_template = AsyncMock()
    mock_template.render_async.return_value = "<html></html>"
    renderer.env.get_template = MagicMock(return_value=mock_template)

    data = {"key": "value"}
    html = await renderer._render_html("test_template.html", data)

    assert html == "<html></html>"
    renderer.env.get_template.assert_called_with("test_template.html")
    mock_template.render_async.assert_called_with(**data)


@pytest.mark.asyncio
async def test_renderer_render_image(renderer):
    # Mock _render_html
    renderer._render_html = AsyncMock(return_value="<html></html>")

    image_bytes = await renderer._render_image("test_template.html")

    assert image_bytes == b"image_bytes"
    renderer._render_html.assert_called_once()
    renderer.core.render.assert_called_once()


@pytest.mark.asyncio
async def test_renderer_render_content(renderer):
    # Mock _render_image
    renderer._render_image = AsyncMock(return_value=b"content_image_bytes")

    thread_dto = ThreadDTO.model_construct(
        tid=123,
        pid=456,
        fname="forum_name",
        author=ThreadUserDTO.model_construct(
            user_id=1, user_name="user", nick_name_new="nickname", portrait="portrait", level=1
        ),
        title="title",
        create_time=1234567890,
        posts=[],
        contents=[],
    )

    image_bytes = await renderer.render_content(thread_dto)

    assert image_bytes == b"content_image_bytes"
    renderer._render_image.assert_called_once()


@pytest.mark.asyncio
async def test_renderer_render_thread_detail(renderer):
    # Mock _render_image
    renderer._render_image = AsyncMock(return_value=b"thread_detail_image_bytes")

    thread_dto = ThreadDTO.model_construct(
        tid=123,
        pid=456,
        fname="forum_name",
        author=ThreadUserDTO.model_construct(
            user_id=1, user_name="user", nick_name_new="nickname", portrait="portrait", level=1
        ),
        title="title",
        create_time=1234567890,
        posts=[],
        contents=[],
        share_num=0,
        agree_num=0,
        reply_num=0,
    )

    post_dto = PostDTO.model_construct(
        pid=789,
        tid=123,
        floor=2,
        author=PostUserDTO.model_construct(
            user_id=2, user_name="user2", nick_name_new="nickname2", portrait="portrait", level=1
        ),
        contents=[],
        create_time=1234567890,
    )

    image_bytes = await renderer.render_thread_detail(thread_dto, [post_dto])

    assert image_bytes == b"thread_detail_image_bytes"
    renderer._render_image.assert_called_once()


# --- Test Base64Context ---


@pytest.mark.asyncio
async def test_base64_context_get_portrait_url():
    with patch("tiebameow.renderer.context.get_portrait", new_callable=AsyncMock) as mock_get_portrait:
        mock_get_portrait.return_value = b"portrait_bytes"

        context = Base64Context()
        # Mock get_client to avoid actual client creation
        with patch.object(Base64Context, "get_client", new_callable=AsyncMock):
            url = await context.get_portrait_url("portrait_id")

            assert url.startswith("data:image/jpeg;base64,")
            assert "cG9ydHJhaXRfYnl0ZXM=" in url  # base64 of "portrait_bytes"


@pytest.mark.asyncio
async def test_base64_context_get_image_url_list():
    with patch("tiebameow.renderer.context.get_images", new_callable=AsyncMock) as mock_get_images:
        mock_get_images.return_value = [b"image1", b"image2"]

        context = Base64Context()
        # Mock get_client
        with patch.object(Base64Context, "get_client", new_callable=AsyncMock):
            urls = await context.get_image_url_list(["hash1", "hash2"])

            assert len(urls) == 2
            assert urls[0].startswith("data:image/jpeg;base64,")
            assert urls[1].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_base64_context_get_forum_icon_url():
    with patch("tiebameow.renderer.context.get_forum_icon", new_callable=AsyncMock) as mock_get_forum_icon:
        mock_get_forum_icon.return_value = b"icon_bytes"

        context = Base64Context()
        # Mock get_client
        with patch.object(Base64Context, "get_client", new_callable=AsyncMock):
            url = await context.get_forum_icon_url("forum_name")

            assert url.startswith("data:image/jpeg;base64,")
            assert "aWNvbl9ieXRlcw==" in url  # base64 of "icon_bytes"
