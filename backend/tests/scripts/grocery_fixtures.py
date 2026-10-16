"""Small hand-made pages shaped like the retailers' (never copies), and a fake browser that serves them."""

from __future__ import annotations

from scripts.grocery_ground_truth import Page


class FakePageSource:
    """Serves pages by URL and records every request, so tests can say how many times the browser was used."""

    def __init__(self, pages: dict[str, Page]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> Page:
        self.requested.append(url)
        return self.pages.get(url, Page(status=404, html="<html><title>Not found</title></html>"))


def ocado_search(*products: tuple[str, str]) -> Page:
    """(name, path) rows as Ocado lays out search results: a concealed image link and a titled link per card."""
    cards = "".join(
        f'<div data-test="carousel-fop-wrapper">'
        f'<a aria-hidden="true" data-test="fop-product-link" href="{path}?list=search&position=1"></a>'
        f'<a aria-hidden="false" data-test="fop-product-link" href="{path}?list=search&position=1">'
        f'<h3 data-test="fop-title">{name}</h3></a></div>'
        for name, path in products
    )
    return Page(status=200, html=f"<html><title>Search - Ocado</title><body>{cards}</body></html>")


def ocado_product(name: str, ingredients: str | None, allergy: str | None = None) -> Page:
    sections = ""
    if ingredients is not None:
        sections += f"<div><h2>Ingredients</h2><div>{ingredients}</div></div>"
    if allergy is not None:
        sections += f"<div><h2>Allergen Information</h2><div>{allergy}</div></div>"
    brand = "<div><h2>Brand</h2><div>Acme</div></div>"
    return Page(
        status=200, html=f"<html><title>{name} - Ocado</title><body><h1>{name}</h1>{brand}{sections}</body></html>"
    )


def sainsburys_search(*products: tuple[str, str]) -> Page:
    items = "".join(
        f'<li class="pt"><a href="https://www.sainsburys.co.uk/gol-ui/product/{slug}">{name}</a></li>'
        for name, slug in products
    )
    return Page(status=200, html=f"<html><title>Search | Sainsbury's</title><body><ul>{items}</ul></body></html>")


def sainsburys_product(name: str, ingredients: str | None, allergy: str | None = None) -> Page:
    sections = ""
    if ingredients is not None:
        sections += f"<section><h3>Ingredients</h3><p>{ingredients}</p></section>"
    if allergy is not None:
        sections += f"<section><h3>Allergy Information</h3><p>{allergy}</p></section>"
    return Page(
        status=200, html=f"<html><title>{name} | Sainsbury's</title><body><h1>{name}</h1>{sections}</body></html>"
    )


ACCESS_DENIED = Page(
    status=403, html="<html><head><title>Access Denied</title></head><body>Access Denied</body></html>"
)
CAPTCHA = Page(
    status=200,
    html="<html><title>One more step</title><body>Please verify you are human. Solve the CAPTCHA.</body></html>",
)
