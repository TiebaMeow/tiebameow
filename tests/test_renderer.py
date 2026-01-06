from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yarl

from tiebameow.models.dto import ThreadDTO, ThreadUserDTO
from tiebameow.renderer import Renderer
from tiebameow.renderer.config import RenderConfig
from tiebameow.renderer.playwright_core import PlaywrightCore
from tiebameow.renderer.style import FONT_URL
from tiebameow.schemas.fragments import TypeFragText

# --- Test PlaywrightCore ---


@pytest.mark.asyncio
async def test_playwright_core_lifecycle():
    """Test launch and close lifecycle of PlaywrightCore."""
    with patch("playwright.async_api.async_playwright") as mock_playwright_cls:
        # Mock Context Manager for async_playwright()
        mock_playwright_mgr = MagicMock()
        mock_playwright_cls.return_value = mock_playwright_mgr

        # Mock the object returned by start()
        mock_playwright_obj = AsyncMock()
        # Ensure start() returns a coroutine that resolves to mock_playwright_obj

        async def async_start():
            return mock_playwright_obj

        mock_playwright_mgr.start.side_effect = async_start

        mock_browser = AsyncMock()
        mock_playwright_obj.chromium.launch.return_value = mock_browser

        core = PlaywrightCore()
        await core.launch()

        assert core.playwright is not None
        assert core.browser is not None
        mock_playwright_obj.chromium.launch.assert_called_once()

        await core.close()
        mock_browser.close.assert_called_once()
        mock_playwright_obj.stop.assert_called_once()
        assert core.browser is None
        assert core.playwright is None


@pytest.mark.asyncio
async def test_playwright_core_render():
    """Test the render method of PlaywrightCore."""
    core = PlaywrightCore()
    core.browser = AsyncMock()
    mock_page = AsyncMock()
    core.browser.new_page.return_value.__aenter__.return_value = mock_page

    config = RenderConfig(width=500, height=100, quality="medium")
    html = "<html>test</html>"
    request_handler = AsyncMock()

    await core.render(html, config, request_handler=request_handler)

    mock_page.set_viewport_size.assert_called_with({"width": 500, "height": 100})
    mock_page.route.assert_called_with("http://tiebameow.local/**", request_handler)
    mock_page.set_content.assert_called_with(html)
    mock_page.wait_for_load_state.assert_called_with("networkidle")
    mock_page.screenshot.assert_called()


# --- Test Renderer Virtual URL Generation ---


def test_renderer_get_portrait_url():
    url = Renderer._get_portrait_url("portrait_id", size="l")
    parsed = yarl.URL(url)
    assert parsed.scheme == "http"
    assert parsed.host == "tiebameow.local"
    assert parsed.path == "/portrait"
    assert parsed.query["id"] == "portrait_id"
    assert parsed.query["size"] == "l"


def test_renderer_get_image_url():
    url = Renderer._get_image_url("image_hash", size="m")
    parsed = yarl.URL(url)
    assert parsed.scheme == "http"
    assert parsed.host == "tiebameow.local"
    assert parsed.path == "/image"
    assert parsed.query["hash"] == "image_hash"
    assert parsed.query["size"] == "m"


def test_renderer_get_forum_icon_url():
    url = Renderer._get_forum_icon_url("forum_name")
    parsed = yarl.URL(url)
    assert parsed.scheme == "http"
    assert parsed.host == "tiebameow.local"
    assert parsed.path == "/forum"
    assert parsed.query["fname"] == "forum_name"


# --- Test Renderer Core Functionality ---


@pytest.fixture
def mock_playwright_core_cls():
    with patch("tiebameow.renderer.renderer.PlaywrightCore") as mock:
        yield mock


@pytest.fixture
def renderer(mock_playwright_core_cls):
    with patch("tiebameow.renderer.renderer.Client") as _:
        r = Renderer()
        r.core = AsyncMock(spec=PlaywrightCore)
        r.core.render = AsyncMock(return_value=b"image_bytes")
        return r


@pytest.mark.asyncio
async def test_renderer_render_image(renderer):
    # Mock jinja2
    mock_template = AsyncMock()
    mock_template.render_async.return_value = "<html></html>"
    renderer.env.get_template = MagicMock(return_value=mock_template)

    await renderer._render_image("test.html", data={})

    renderer.env.get_template.assert_called_with("test.html")
    mock_template.render_async.assert_called()
    renderer.core.render.assert_called_once()
    # Check if request_handler was passed
    call_kwargs = renderer.core.render.call_args.kwargs
    assert call_kwargs["request_handler"] == renderer._handle_route


@pytest.mark.asyncio
async def test_renderer_build_content_context(renderer):
    thread_dto = ThreadDTO.model_construct(
        tid=123,
        pid=456,
        author=ThreadUserDTO.model_construct(
            user_id=1, show_name="user", portrait="portrait_id", level=5, nick_name_new="user"
        ),
        title="Test Thread",
        create_time=1700000000,
        contents=[
            MagicMock(spec=TypeFragText, type=1, text="Content Text", to_proto=lambda: ""),
        ],
        images=[MagicMock(hash="hash1"), MagicMock(hash="hash2")],
    )

    # Since we use model_construct and cached_property, we need to manually set the images property or let it compute
    # It's easier to patch the images property for the DTO since it is a cached property relying on contents
    with patch.object(ThreadDTO, "images", [MagicMock(hash="hash1"), MagicMock(hash="hash2")]):
        ctx = await renderer._build_content_context(thread_dto, max_image_count=1)

    assert ctx["tid"] == 123
    assert ctx["text"] == "Content Text"
    assert "portrait_url" in ctx
    assert "image_url_list" in ctx
    assert len(ctx["image_url_list"]) == 1  # Limited by max_image_count
    assert ctx["remain_image_count"] == 1
    assert "tiebameow.local" in ctx["portrait_url"]
    assert "tiebameow.local" in ctx["image_url_list"][0]


@pytest.mark.asyncio
async def test_handle_route_font(renderer):
    """Test font route interception."""
    mock_route = AsyncMock()
    mock_route.request.url = FONT_URL

    with patch("tiebameow.renderer.renderer.font_path") as mock_path:
        mock_path.exists.return_value = True
        await renderer._handle_route(mock_route)
        mock_route.fulfill.assert_called_with(path=mock_path)

        mock_path.exists.return_value = False
        await renderer._handle_route(mock_route)
        mock_route.abort.assert_called()


@pytest.mark.asyncio
async def test_handle_route_portrait(renderer):
    """Test portrait proxying."""
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/portrait?id=pid&size=s"

    mock_resp = AsyncMock()
    mock_resp.data = b"portrait_data"
    renderer.client.get_image_bytes = AsyncMock(return_value=mock_resp)

    await renderer._handle_route(mock_route)

    renderer.client.get_image_bytes.assert_called()
    # Verify the proxied URL points to baidu
    args, _ = renderer.client.get_image_bytes.call_args
    assert "sys/portraitn/item/pid" in str(args[0])
    mock_route.fulfill.assert_called_with(body=b"portrait_data")


@pytest.mark.asyncio
async def test_handle_route_image(renderer):
    """Test image proxying."""
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/image?hash=hash123&size=s"

    mock_resp = AsyncMock()
    mock_resp.data = b"image_data"
    renderer.client.get_image_bytes = AsyncMock(return_value=mock_resp)

    await renderer._handle_route(mock_route)

    renderer.client.get_image_bytes.assert_called()
    args, _ = renderer.client.get_image_bytes.call_args
    assert "imgsrc.baidu.com" in str(args[0])
    assert "hash123" in str(args[0])
    mock_route.fulfill.assert_called_with(body=b"image_data")


@pytest.mark.asyncio
async def test_handle_route_forum_icon(renderer):
    """Test forum icon proxying."""
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/forum?fname=test_forum"

    mock_forum_info = MagicMock()
    mock_forum_info.small_avatar = "http://icon.url"
    renderer.client.get_forum = AsyncMock(return_value=mock_forum_info)

    mock_resp = AsyncMock()
    mock_resp.data = b"icon_data"
    renderer.client.get_image_bytes = AsyncMock(return_value=mock_resp)

    await renderer._handle_route(mock_route)

    renderer.client.get_forum.assert_called_with("test_forum")
    renderer.client.get_image_bytes.assert_called_with("http://icon.url")
    mock_route.fulfill.assert_called_with(body=b"icon_data")


@pytest.mark.asyncio
async def test_handle_route_external(renderer):
    """Test ignoring non-local domains."""
    mock_route = AsyncMock()
    mock_route.request.url = "http://google.com/something"

    await renderer._handle_route(mock_route)
    mock_route.continue_.assert_called()


@pytest.mark.asyncio
async def test_handle_route_error(renderer):
    """Test exception handling in route handler."""
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/image?hash=bad"

    renderer.client.get_image_bytes.side_effect = Exception("Network Error")

    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()
