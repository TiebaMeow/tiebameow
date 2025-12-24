from __future__ import annotations

from asyncio import Lock
from typing import TYPE_CHECKING, Any

from .base import CoreBase

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

    from ..config import Config


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


class PlaywrightCore(CoreBase):
    def __init__(self) -> None:
        if not self.check_installed():
            raise ImportError("playwright is not installed. Please install it with 'pip install playwright'.")

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._lock = Lock()

    @staticmethod
    def check_installed() -> bool:
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False
        return True

    async def launch(self) -> None:
        async with self._lock:
            if self.browser is None:
                if self.playwright is None:
                    from playwright.async_api import async_playwright

                    self.playwright = await async_playwright().start()
                if self.browser is None:
                    self.browser = await self.playwright.chromium.launch()

    async def close(self) -> None:
        if self.browser is not None:
            await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None

    async def render(self, html: str, config: Config) -> bytes:
        if self.browser is None:
            await self.launch()
        assert self.browser is not None

        page = await self.browser.new_page(device_scale_factor=QUALITY_MAP_SCALE[config.quality])
        await page.set_viewport_size({"width": config.width, "height": config.height})
        await page.set_content(html)
        screenshot = await page.screenshot(full_page=True, **QUALITY_MAP_OUTPUT[config.quality])
        await page.close()
        return screenshot
