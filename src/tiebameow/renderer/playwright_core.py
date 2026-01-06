from __future__ import annotations

from asyncio import Lock
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from playwright.async_api import Browser, BrowserContext, Playwright, Route

    from .config import RenderConfig


QUALITY_MAP_SCALE = {
    "low": 1,
    "medium": 1.5,
    "high": 2,
}
QUALITY_MAP_OUTPUT: dict[str, dict[str, Any]] = {
    "low": {
        "type": "jpeg",
        "quality": 60,
    },
    "medium": {
        "type": "jpeg",
        "quality": 80,
    },
    "high": {"type": "png"},
}

VALID_BROWSER_ENGINES = Literal["chromium", "firefox", "webkit"]


class PlaywrightCore:
    def __init__(self, browser_engine: VALID_BROWSER_ENGINES | None = None) -> None:
        if not self.check_installed():
            raise ImportError(
                "playwright is not installed. Please install it with 'pip install tiebameow[renderer]'.\n"
                "You may also need to run 'playwright install' to install the necessary browsers."
            )

        self.playwright: Playwright | None = None
        self.browser_engine = browser_engine or "chromium"
        self.browser: Browser | None = None
        self.contexts: dict[str, BrowserContext] = {}
        self._lock = Lock()

    @staticmethod
    def check_installed() -> bool:
        """检查Playwright包是否已安装。"""
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False
        return True

    async def _launch(self) -> None:
        """在获取锁的前提下，启动Playwright和浏览器实例。"""
        if self.browser is not None:
            return

        if self.playwright is None:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()

        engine = getattr(self.playwright, self.browser_engine)
        if not engine:
            raise ValueError(f"Invalid browser engine: {self.browser_engine}")
        try:
            self.browser = await engine.launch()
        except AttributeError as e:
            raise ValueError(f"Invalid browser engine: {self.browser_engine}") from e

    async def launch(self) -> None:
        """启动Playwright和浏览器实例。"""
        async with self._lock:
            await self._launch()

    async def close(self) -> None:
        """关闭所有浏览器上下文和浏览器实例。"""
        async with self._lock:
            for context in self.contexts.values():
                await context.close()
            self.contexts.clear()

            if self.browser is not None:
                await self.browser.close()
                self.browser = None
            if self.playwright is not None:
                await self.playwright.stop()
                self.playwright = None

    async def _get_context(self, quality: str) -> BrowserContext:
        """获取指定渲染图片质量的浏览器上下文。"""
        if quality in self.contexts:
            return self.contexts[quality]

        async with self._lock:
            if quality in self.contexts:
                return self.contexts[quality]

            if self.browser is None:
                await self._launch()

            browser = cast("Browser", self.browser)
            scale = QUALITY_MAP_SCALE.get(quality, 1)
            context = await browser.new_context(device_scale_factor=scale)
            self.contexts[quality] = context
            return context

    async def render(
        self,
        html: str,
        config: RenderConfig,
        element: str | None = None,
        request_handler: Callable[[Route], Awaitable[None]] | None = None,
    ) -> bytes:
        """使用Playwright渲染HTML为图片。

        Args:
            html: 要渲染的HTML内容
            config: 渲染配置
            element: 可选的CSS选择器，指定要截图的元素；如果为None，则截图整个页面
            request_handler: 可选的请求处理函数，用于拦截和处理页面请求

        Returns:
            渲染后的图片字节内容
        """
        context = await self._get_context(config.quality)
        page = await context.new_page()

        try:
            await page.set_viewport_size({"width": config.width, "height": config.height})

            if request_handler:
                await page.route("http://tiebameow.local/**", request_handler)

            await page.set_content(html)
            await page.wait_for_load_state("networkidle")

            if element:
                screenshot = await page.locator(element).screenshot(**QUALITY_MAP_OUTPUT[config.quality])
            else:
                screenshot = await page.screenshot(full_page=True, **QUALITY_MAP_OUTPUT[config.quality])
            return screenshot
        finally:
            await page.close()
