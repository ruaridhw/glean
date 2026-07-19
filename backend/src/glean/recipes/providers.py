from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from glean.llm import Feature
from glean.recipes.stored import (
    RecipeImportError,
    RecipeLlmResponse,
    RecipeParseResult,
    stored_from_llm_response,
    stored_from_schema_org,
)

if TYPE_CHECKING:
    from glean.llm import LLMRouter

URL_PARSE_SYSTEM_PROMPT = """You are a recipe extraction assistant. Given HTML from a recipe page,
extract the recipe details into the response schema.
Use null for optional scalar fields that cannot be determined, and empty arrays for list fields when none are present.
Express time fields as ISO 8601 durations (e.g. "PT30M")."""

_DEFAULT_MAX_REDIRECTS = 5
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True)
class FetchedPage:
    url: str
    text: str


class SchemaOrgThenLlmParser:
    """Extract a stored recipe from arbitrary recipe-page HTML."""

    def parse(self, html: str, *, source_url: str, llm_router: LLMRouter) -> RecipeParseResult:
        schema_data = _parse_schema_org_recipe(html)
        if schema_data and schema_data.get("recipeIngredient"):
            recipe = stored_from_schema_org(schema_data, source_url=source_url)
            return RecipeParseResult(
                recipe=recipe,
                parser="schema.org",
                source_url=source_url,
                fetched_url=source_url,
                confidence=1.0,
            )

        messages = [
            SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this HTML:\n\n{html[:8000]}"),
        ]

        try:
            llm_response = llm_router.invoke(Feature.RECIPE_IMPORT, RecipeLlmResponse, messages)
        except ValidationError as exc:
            raise RecipeImportError("invalid_llm_json", "Recipe extraction model returned malformed fields") from exc
        except Exception as exc:
            raise RecipeImportError("llm_failed", "Recipe extraction model failed") from exc

        try:
            recipe = stored_from_llm_response(llm_response, source_url=source_url)
        except RecipeImportError as exc:
            raise RecipeImportError("invalid_recipe", exc.message) from exc

        return RecipeParseResult(
            recipe=recipe,
            parser="llm",
            source_url=source_url,
            fetched_url=source_url,
            confidence=0.75,
        )


def import_url_to_canonical(
    url: str,
    *,
    llm_router: LLMRouter,
    parser: SchemaOrgThenLlmParser | None = None,
) -> RecipeParseResult:
    fetched = fetch_public_https(url)
    result = (parser or SchemaOrgThenLlmParser()).parse(fetched.text, source_url=fetched.url, llm_router=llm_router)
    result.source_url = url
    result.fetched_url = fetched.url
    if result.recipe and result.recipe.provenance:
        result.recipe.provenance.source_url = url
        result.recipe.provenance.fetched_url = fetched.url
    return result


def import_html_to_canonical(
    url: str,
    html: str,
    *,
    llm_router: LLMRouter,
    parser: SchemaOrgThenLlmParser | None = None,
    fetched_url: str | None = None,
) -> RecipeParseResult:
    resolved_url = fetched_url or url
    result = (parser or SchemaOrgThenLlmParser()).parse(html, source_url=resolved_url, llm_router=llm_router)
    result.source_url = url
    result.fetched_url = resolved_url
    if result.recipe and result.recipe.provenance:
        result.recipe.provenance.source_url = url
        result.recipe.provenance.fetched_url = resolved_url
    return result


def fetch_public_https(url: str, *, max_bytes: int = 8_000_000, timeout: float = 10.0) -> FetchedPage:
    current_url = url
    redirects_followed = 0
    browser_challenge_retried = False

    with httpx.Client(follow_redirects=False, timeout=timeout, headers=_BROWSER_HEADERS) as client:
        while True:
            validate_public_https_url(current_url)
            try:
                response_context = _stream_response(client, current_url)
            except httpx.HTTPError as exc:
                raise RecipeImportError("fetch_failed", f"Failed to fetch recipe URL: {current_url}") from exc

            with response_context as response:
                if _is_redirect(response):
                    if redirects_followed >= _DEFAULT_MAX_REDIRECTS:
                        raise RecipeImportError("too_many_redirects", "Too many redirects while fetching recipe URL")
                    location = response.headers.get("location")
                    if not location:
                        raise RecipeImportError("fetch_failed", "Redirect response did not include a Location header")
                    current_url = urljoin(current_url, location)
                    redirects_followed += 1
                    continue

                body = _read_response_body(response, max_bytes=max_bytes)
                if (
                    not browser_challenge_retried
                    and response.status_code == 403
                    and _looks_like_browser_challenge(body)
                ):
                    browser_challenge_retried = True
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RecipeImportError("fetch_failed", f"Recipe URL returned HTTP {response.status_code}") from exc

                return FetchedPage(url=str(response.url), text=_decode_response_text(response, body))


class _ResponseContext:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def __enter__(self) -> httpx.Response:
        return self._response

    def __exit__(self, *_: object) -> None:
        self._response.close()


def _stream_response(client: httpx.Client, url: str) -> Any:
    stream = getattr(client, "stream", None)
    if stream is None:
        return _ResponseContext(client.get(url))
    return stream("GET", url)


def _read_response_body(response: httpx.Response, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_bytes = 0
    for chunk in response.iter_bytes():
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise RecipeImportError("response_too_large", f"Recipe response exceeded {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response_text(response: httpx.Response, body: bytes) -> str:
    encoding = response.encoding or "utf-8"
    return body.decode(encoding, errors="replace")


def _looks_like_browser_challenge(body: bytes) -> bool:
    text = body[:10_000].decode("utf-8", errors="ignore")
    return "Enable JavaScript and cookies to continue" in text or "<title>Simple Page</title>" in text


def validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise RecipeImportError("unsafe_url", "Only HTTPS URLs are allowed")

    if not parsed.hostname:
        raise RecipeImportError("unsafe_url", "Invalid URL: no hostname")

    host = parsed.hostname
    port = parsed.port or 443
    try:
        addrinfos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RecipeImportError("fetch_failed", f"Cannot resolve hostname: {host}") from exc

    if not addrinfos:
        raise RecipeImportError("fetch_failed", f"Cannot resolve hostname: {host}")

    for addrinfo in addrinfos:
        resolved_ip = addrinfo[4][0]
        try:
            addr = ipaddress.ip_address(resolved_ip)
        except ValueError as exc:
            raise RecipeImportError("unsafe_url", f"Invalid IP address resolved: {resolved_ip}") from exc

        if not addr.is_global:
            raise RecipeImportError("unsafe_url", f"URL resolves to a disallowed IP address: {resolved_ip}")


def _parse_schema_org_recipe(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue

        for item in _iter_json_ld_nodes(data):
            if isinstance(item, dict) and _is_recipe_type(item.get("@type")):
                return item

    return None


def _iter_json_ld_nodes(data: Any) -> list[Any]:
    if isinstance(data, list):
        nodes: list[Any] = []
        for item in data:
            nodes.extend(_iter_json_ld_nodes(item))
        return nodes

    if isinstance(data, dict) and "@graph" in data:
        graph = data["@graph"]
        if isinstance(graph, list):
            return graph
        return [graph]

    return [data]


def _is_recipe_type(raw_type: Any) -> bool:
    if isinstance(raw_type, list):
        return "Recipe" in raw_type
    return raw_type == "Recipe"


def _is_redirect(response: httpx.Response) -> bool:
    return 300 <= response.status_code < 400
