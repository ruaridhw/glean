"""Retailer adapters behind one protocol. They parse pages; a `PageSource` (the browser) fetches them."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

from .models import Product, ProductRef


class RetailerBlocked(Exception):
    """The shop served a block or captcha page instead of the page asked for. Never worked around."""


class ProductUnreadable(Exception):
    """A product page with no ingredients list, so there is nothing to classify."""


@dataclass(frozen=True)
class Page:
    status: int
    html: str


class PageSource(Protocol):
    def fetch(self, url: str) -> Page: ...


class RetailerReader(Protocol):
    name: str

    def search(self, query: str) -> list[ProductRef]: ...

    def read(self, ref: ProductRef) -> Product: ...


_BLOCK_STATUSES = {401, 403, 429}
_BLOCK_TEXT = re.compile(
    r"access denied|captcha|security check|verify you are (?:a )?human|unusual traffic|are you a robot",
    re.IGNORECASE,
)


def raise_if_blocked(page: Page) -> None:
    soup = BeautifulSoup(page.html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if page.status in _BLOCK_STATUSES or _BLOCK_TEXT.search(title) or _BLOCK_TEXT.search(soup.get_text(" ")[:2000]):
        raise RetailerBlocked(f"Blocked (HTTP {page.status}, title {title!r})")


_INGREDIENTS_HEADING = re.compile(r"^ingredients$", re.IGNORECASE)
_ALLERGY_HEADING = re.compile(r"^allerg(?:y|en)\s+(?:information|advice)$", re.IGNORECASE)


def _section_text(soup: BeautifulSoup, heading: re.Pattern[str], *, separator: str) -> str:
    """The text under the first heading that matches: its next sibling, line breaks kept as `separator`."""
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if heading.match(tag.get_text(" ", strip=True)):
            body = tag.find_next_sibling()
            if body is not None:
                return re.sub(rf"\s*{re.escape(separator)}\s*", separator, body.get_text(separator, strip=True))
    return ""


def parse_product(page: Page, ref: ProductRef) -> Product:
    raise_if_blocked(page)
    soup = BeautifulSoup(page.html, "html.parser")
    ingredients = _section_text(soup, _INGREDIENTS_HEADING, separator=" ")
    if not ingredients:
        raise ProductUnreadable(f"No ingredients on {ref.url}")
    heading = soup.find("h1")
    return Product(
        retailer=ref.retailer,
        name=heading.get_text(" ", strip=True) if heading else ref.name,
        url=ref.url,
        ingredients_text=ingredients,
        allergy_text=_section_text(soup, _ALLERGY_HEADING, separator="\n"),
    )


class OcadoReader:
    name = "ocado"
    _base = "https://www.ocado.com"

    def __init__(self, source: PageSource) -> None:
        self._source = source

    def search(self, query: str) -> list[ProductRef]:
        page = self._source.fetch(f"{self._base}/search?q={quote(query)}")
        raise_if_blocked(page)
        refs: dict[str, ProductRef] = {}
        for link in BeautifulSoup(page.html, "html.parser").select('a[data-test="fop-product-link"]'):
            title = link.select_one('[data-test="fop-title"]')
            href = link.get("href")
            if title is None or not isinstance(href, str):
                continue
            url = urljoin(self._base, urlsplit(href).path)
            refs.setdefault(url, ProductRef(retailer=self.name, name=title.get_text(strip=True), url=url))
        return list(refs.values())

    def read(self, ref: ProductRef) -> Product:
        return parse_product(self._source.fetch(ref.url), ref)


class SainsburysReader:
    """Selectors follow the manual reading of 2026-10-16; headless Chromium got HTTP 403 from the live shop then."""

    name = "sainsburys"
    _base = "https://www.sainsburys.co.uk"

    def __init__(self, source: PageSource) -> None:
        self._source = source

    def search(self, query: str) -> list[ProductRef]:
        page = self._source.fetch(f"{self._base}/gol-ui/SearchResults/{quote(query)}")
        raise_if_blocked(page)
        refs: dict[str, ProductRef] = {}
        for link in BeautifulSoup(page.html, "html.parser").select('a[href*="/product/"]'):
            href = link.get("href")
            title = link.get_text(" ", strip=True)
            if title and isinstance(href, str):
                url = urljoin(self._base, urlsplit(href).path)
                refs.setdefault(url, ProductRef(retailer=self.name, name=title, url=url))
        return list(refs.values())

    def read(self, ref: ProductRef) -> Product:
        return parse_product(self._source.fetch(ref.url), ref)
