from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yarl

from tiebameow.models.dto import PostDTO, ThreadDTO, ThreadUserDTO
from tiebameow.renderer import Renderer
from tiebameow.renderer.config import RenderConfig
from tiebameow.renderer.playwright_core import PlaywrightCore
from tiebameow.renderer.style import FONT_URL, get_font_style
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

        # Mock contexts
        mock_context = AsyncMock()
        mock_browser.new_context.return_value = mock_context

        core = PlaywrightCore()
        await core.launch()

        assert core.playwright is not None
        assert core.browser is not None
        mock_playwright_obj.chromium.launch.assert_called_once()

        # Helper to simulate context creation
        await core._get_context("medium")
        assert len(core.contexts) == 1

        await core.close()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright_obj.stop.assert_called_once()
        assert core.browser is None
        assert core.playwright is None
        assert len(core.contexts) == 0


@pytest.mark.asyncio
async def test_playwright_core_render():
    """Test the render method of PlaywrightCore with context reuse."""
    core = PlaywrightCore()
    core.browser = AsyncMock()

    # Setup mocks
    mock_context = AsyncMock()
    core.browser.new_context.return_value = mock_context

    mock_page = AsyncMock()
    mock_context.new_page.return_value = mock_page

    config = RenderConfig(width=500, height=100, quality="medium")
    html = "<html>test</html>"
    request_handler = AsyncMock()

    # First render call - should create context
    await core.render(html, config, request_handler=request_handler)

    core.browser.new_context.assert_called_once()
    mock_context.new_page.assert_called_once()
    mock_page.set_viewport_size.assert_called_with({"width": 500, "height": 100})
    mock_page.route.assert_called_with("http://tiebameow.local/**", request_handler)
    mock_page.set_content.assert_called_with(html)
    mock_page.wait_for_load_state.assert_called_with("networkidle")
    mock_page.screenshot.assert_called()
    mock_page.close.assert_called_once()

    # Second render call with same quality - should reuse context
    await core.render(html, config, request_handler=request_handler)

    # new_context should NOT be called again
    core.browser.new_context.assert_called_once()
    # new_page SHOULD be called again
    assert mock_context.new_page.call_count == 2
    assert mock_page.close.call_count == 2

    # Third render call with DIFFERENT quality - should create NEW context
    config_high = RenderConfig(width=500, height=100, quality="high")
    mock_context_high = AsyncMock()
    mock_page_high = AsyncMock()
    mock_context_high.new_page.return_value = mock_page_high

    # Clear contexts to cleanly test new creation without side_effect complexity on existing mock
    core.contexts.clear()
    core.browser.new_context.reset_mock()
    core.browser.new_context.return_value = mock_context_high

    await core.render(html, config_high, request_handler=request_handler)

    core.browser.new_context.assert_called_once()
    call_kwargs = core.browser.new_context.call_args.kwargs
    assert call_kwargs["device_scale_factor"] == 2  # high quality scale


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


@pytest.mark.asyncio
async def test_render_content_thread(renderer):
    thread_dto = ThreadDTO.from_incomplete_data({
        "tid": 123,
        "pid": 0,
        "fname": "test_forum",
        "title": "Test Title",
        "author": {"user_name": "test_user", "nick_name_new": "test_nick", "portrait": "p1", "level": 1},
    })

    # Patch convert methods if needed, but here we pass DTO
    # Need to patch _render_image to verify it's called
    with patch.object(renderer, "_render_image", AsyncMock(return_value=b"png")) as mock_render:
        mock_forum_info = MagicMock()
        mock_forum_info.small_avatar = "http://avatar"
        renderer.client.get_forum = AsyncMock(return_value=mock_forum_info)

        await renderer.render_content(thread_dto, title="Override Title")

        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert kwargs["data"]["content"]["title"] == "Override Title"
        assert kwargs["data"]["forum"] == "test_forum"
        assert kwargs["data"]["forum_icon_url"] == "http://tiebameow.local/forum?fname=test_forum"


@pytest.mark.asyncio
async def test_render_content_post(renderer):
    post_dto = PostDTO.from_incomplete_data({
        "pid": 111,
        "tid": 123,
        "fname": "test_forum",
        "fid": 1,
        "floor": 2,
        "author": {"user_name": "user", "nick_name_new": "nick", "portrait": "p", "level": 1},
    })

    with patch.object(renderer, "_render_image", AsyncMock(return_value=b"png")) as mock_render:
        await renderer.render_content(post_dto)
        mock_render.assert_called_once()
        context = mock_render.call_args.kwargs["data"]["content"]
        assert context["pid"] == 111
        assert context["floor"] == 2


@pytest.mark.asyncio
async def test_render_thread_detail(renderer):
    thread_dto = ThreadDTO.from_incomplete_data({
        "tid": 123,
        "pid": 0,
        "fname": "bar",
        "fid": 1,
        "title": "Test Title",
        "author": {"user_name": "u", "nick_name_new": "n", "portrait": "p", "level": 1},
    })

    posts = [
        PostDTO.from_incomplete_data({
            "pid": 1,
            "tid": 123,
            "fname": "bar",
            "fid": 1,
            "floor": 1,
            "author": {"user_name": "u", "nick_name_new": "n", "portrait": "p", "level": 1},
        }),
        PostDTO.from_incomplete_data({
            "pid": 2,
            "tid": 123,
            "fname": "bar",
            "fid": 1,
            "floor": 2,
            "author": {"user_name": "u", "nick_name_new": "n", "portrait": "p", "level": 1},
        }),
    ]

    with patch.object(renderer, "_render_image", AsyncMock(return_value=b"png")) as mock_render:
        # Test ignore_first_floor=True (default)
        await renderer.render_thread_detail(thread_dto, posts)

        # Verify passed posts data
        call_kwargs = mock_render.call_args.kwargs
        posts_context = call_kwargs["data"]["posts"]
        # Only floor 2 should remain
        assert len(posts_context) == 1
        assert posts_context[0]["pid"] == 2


@pytest.mark.asyncio
async def test_text_to_image(renderer):
    with patch.object(renderer, "_render_image", AsyncMock(return_value=b"png")) as mock_render:
        await renderer.text_to_image("Hello", title="Title", simple_mode=True)

        assert mock_render.call_args[0][0] == "text_simple.html"
        data = mock_render.call_args.kwargs["data"]
        assert data["text"] == "Hello"
        assert data["title"] == "Title"
        assert mock_render.call_args.kwargs["element"] == ".container"


@pytest.mark.asyncio
async def test_renderer_context_manager():
    # Test own client lifecycle
    with patch("tiebameow.renderer.renderer.Client") as mock_client:
        mock_client_inst = AsyncMock()
        mock_client.return_value = mock_client_inst

        r = Renderer(client=None)
        r.core = AsyncMock()

        async with r:
            mock_client_inst.__aenter__.assert_called()
            r.core.launch.assert_called()

        mock_client_inst.__aexit__.assert_called()
        r.core.close.assert_called()


@pytest.mark.asyncio
async def test_renderer_context_manager_external_client():
    # Test external client lifecycle - should DOES NOT call enter/exit
    external_client = AsyncMock()
    r = Renderer(client=external_client)
    r.core = AsyncMock()

    async with r:
        assert not external_client.__aenter__.called

    assert not external_client.__aexit__.called
    r.core.close.assert_called()


@pytest.mark.asyncio
async def test_renderer_context_manager_error():
    external_client = AsyncMock()
    r = Renderer(client=external_client)
    r.core = AsyncMock()
    r.core.launch.side_effect = Exception("Launch failed")

    with pytest.raises(Exception, match="Launch failed"):
        async with r:
            pass

    r.core.close.assert_called()


def test_format_date():
    from datetime import datetime

    from tiebameow.renderer.renderer import format_date

    # Test float timestamp
    ts = 1700000000.0
    s = format_date(ts)
    assert s == datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

    # Test milliseconds
    ts_ms = 1700000000000
    s = format_date(ts_ms)
    assert s == datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M")


@pytest.mark.asyncio
async def test_renderer_custom_template_dir(tmp_path):
    r = Renderer(template_dir=tmp_path)
    # Check loader type
    assert r.env.loader.__class__.__name__ == "FileSystemLoader"


@pytest.mark.asyncio
async def test_handle_route_portrait_large(renderer):
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/portrait?id=pid&size=l"
    mock_resp = AsyncMock(data=b"data")
    renderer.client.get_image_bytes = AsyncMock(return_value=mock_resp)

    await renderer._handle_route(mock_route)

    args, _ = renderer.client.get_image_bytes.call_args
    assert "/sys/portraith/item/pid" in str(args[0])


@pytest.mark.asyncio
async def test_handle_route_image_sizes(renderer):
    # Test M size
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/image?hash=h&size=m"
    renderer.client.get_image_bytes = AsyncMock(return_value=AsyncMock(data=b"d"))
    await renderer._handle_route(mock_route)
    assert "w=960" in str(renderer.client.get_image_bytes.call_args[0][0])

    # Test L size
    mock_route.request.url = "http://tiebameow.local/image?hash=h&size=l"
    await renderer._handle_route(mock_route)
    assert "/forum/pic/item/h.jpg" in str(renderer.client.get_image_bytes.call_args[0][0])

    # Test unknown size -> abort
    mock_route.request.url = "http://tiebameow.local/image?hash=h&size=xxx"
    mock_route.abort.reset_mock()
    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()


@pytest.mark.asyncio
async def test_handle_route_missing_params(renderer):
    mock_route = AsyncMock()

    # Missing portrait id
    mock_route.request.url = "http://tiebameow.local/portrait"
    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()

    # Missing image hash
    mock_route.request.url = "http://tiebameow.local/image"
    mock_route.abort.reset_mock()
    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()

    # Missing forum fname
    mock_route.request.url = "http://tiebameow.local/forum"
    mock_route.abort.reset_mock()
    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()


@pytest.mark.asyncio
async def test_handle_route_forum_no_avatar(renderer):
    mock_route = AsyncMock()
    mock_route.request.url = "http://tiebameow.local/forum?fname=test"

    mock_info = MagicMock()
    mock_info.small_avatar = ""
    renderer.client.get_forum = AsyncMock(return_value=mock_info)

    await renderer._handle_route(mock_route)
    mock_route.abort.assert_called()


def test_get_font_style_not_exists():
    with patch("pathlib.Path.exists", return_value=False):
        style = get_font_style(16)
        assert "<style>" in style
        assert 'font-family: "Noto Sans SC"' in style
        assert "font-size: 16px" in style
        assert "@font-face" not in style


def test_get_font_style_exists():
    with patch("pathlib.Path.exists", return_value=True):
        style = get_font_style(16)
        assert "<style>" in style
        assert "@font-face" in style
