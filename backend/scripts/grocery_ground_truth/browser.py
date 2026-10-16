"""The only module that imports Playwright: a polite, read-only browser behind `PageSource`."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright  # the dev-only dependency group `audit`

from .retailers import Page

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
MIN_SECONDS_BETWEEN_REQUESTS = 2.5


class PlaywrightPageSource:
    """Fetches pages in headless Chromium, at most one request per `interval` seconds. No login, no basket."""

    def __init__(
        self,
        *,
        interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> PlaywrightPageSource:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._context = self._browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def fetch(self, url: str) -> Page:
        if self._context is None:
            raise RuntimeError("Use the page source as a context manager.")
        if self._last is not None:
            wait = self._interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(4_000)  # these shops render their product details client-side
            return Page(status=response.status if response else 0, html=page.content())
        finally:
            page.close()
            self._last = self._clock()
