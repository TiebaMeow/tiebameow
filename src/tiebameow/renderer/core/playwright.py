from __future__ import annotations

import tempfile
from asyncio import Lock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

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

VALID_BROWSER_ENGINES = Literal["chromium", "firefox", "webkit"]


class PlaywrightCore(CoreBase):
    def __init__(
        self, browser_engine: VALID_BROWSER_ENGINES | None = None, enable_local_file_access: bool = False
    ) -> None:
        if not self.check_installed():
            raise ImportError("playwright is not installed. Please install it with 'pip install playwright'.")

        self.enable_local_file_access = enable_local_file_access
        self.playwright: Playwright | None = None
        self.browser_engine = browser_engine
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
            if self.browser is not None:
                return

            if self.playwright is None:
                from playwright.async_api import async_playwright

                self.playwright = await async_playwright().start()

            if self.browser_engine:
                engine = getattr(self.playwright, self.browser_engine)
                if not engine:
                    raise ValueError(f"Invalid browser engine: {self.browser_engine}")
                try:
                    self.browser = await engine.launch()
                except AttributeError as e:
                    raise ValueError(f"Invalid browser engine: {self.browser_engine}") from e
            else:
                from playwright.async_api import Error

                for engine_name in ["chromium", "firefox", "webkit"]:
                    engine = getattr(self.playwright, engine_name)
                    try:
                        self.browser = await engine.launch()
                        break
                    except Error:
                        continue
                else:
                    self.browser = (
                        await self.playwright.chromium.launch()
                    )  # 使用playwright.chromium作为最后的后备选项，展示原始错误

    async def close(self) -> None:
        async with self._lock:
            if self.browser is not None:
                await self.browser.close()
                self.browser = None
            if self.playwright is not None:
                await self.playwright.stop()
                self.playwright = None

    async def render(self, html: str, config: Config) -> bytes:
        if self.browser is None:
            await self.launch()

        browser = cast("Browser", self.browser)
        async with await browser.new_page(device_scale_factor=QUALITY_MAP_SCALE[config.quality]) as page:
            await page.set_viewport_size({"width": config.width, "height": config.height})

            if self.enable_local_file_access:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
                    f.write(html)
                    temp_path = Path(f.name)

                try:
                    await page.goto(temp_path.as_uri())
                    await page.wait_for_load_state("networkidle")
                    screenshot = await page.screenshot(full_page=True, **QUALITY_MAP_OUTPUT[config.quality])
                finally:
                    temp_path.unlink(missing_ok=True)  # noqa: ASYNC240
                    # TODO use async method
            else:
                await page.set_content(html)
                await page.wait_for_load_state("networkidle")
                screenshot = await page.screenshot(full_page=True, **QUALITY_MAP_OUTPUT[config.quality])
            return screenshot
