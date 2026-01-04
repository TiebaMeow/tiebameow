from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tiebameow.models.dto import PostDTO, PostUserDTO, ThreadDTO, ThreadUserDTO
from tiebameow.renderer import Renderer
from tiebameow.renderer.playwright import PlaywrightCore

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
def mock_playwright_core_cls():
    with patch("tiebameow.renderer.renderer.PlaywrightCore") as mock:
        yield mock


@pytest.fixture
def renderer(mock_playwright_core_cls):
    with patch("tiebameow.renderer.renderer.Client") as _:
        r = Renderer()
        # Mock the core instance
        r.core = AsyncMock(spec=PlaywrightCore)
        r.core.render = AsyncMock(return_value=b"image_bytes")
        r.core.close = AsyncMock()
        return r


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
    # Mock _fill_content_urls and _fill_forum_icon_url to avoid network calls
    renderer._fill_content_urls = AsyncMock()
    renderer._fill_forum_icon_url = AsyncMock()

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
    # Mock _fill_content_urls and _fill_forum_icon_url
    renderer._fill_content_urls = AsyncMock()
    renderer._fill_forum_icon_url = AsyncMock()

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


@pytest.mark.asyncio
async def test_get_portrait():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = b"portrait_bytes"
    mock_client.get_image_bytes = AsyncMock(return_value=mock_response)

    # Test with string
    res = await Renderer._get_portrait(mock_client, "portrait_id")
    assert res == b"portrait_bytes"
    mock_client.get_image_bytes.assert_called_once()


@pytest.mark.asyncio
async def test_get_images():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = b"img_bytes"
    mock_client.get_image_bytes = AsyncMock(return_value=mock_response)

    res = await Renderer._get_images(mock_client, ["hash1", "hash2"])
    assert res == [b"img_bytes", b"img_bytes"]
    assert mock_client.get_image_bytes.call_count == 2


@pytest.mark.asyncio
async def test_get_forum_icon():
    mock_client = MagicMock()
    mock_forum = MagicMock()
    mock_forum.small_avatar = "http://avatar.url"
    mock_client.get_forum = AsyncMock(return_value=mock_forum)

    mock_response = MagicMock()
    mock_response.data = b"icon_bytes"
    mock_client.get_image_bytes = AsyncMock(return_value=mock_response)

    res = await Renderer._get_forum_icon(mock_client, "forum_name")
    assert res == b"icon_bytes"
    mock_client.get_forum.assert_called_with("forum_name")
    mock_client.get_image_bytes.assert_called_with("http://avatar.url")
