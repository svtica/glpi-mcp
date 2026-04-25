"""Smoke tests for the knowledge base tools and the httpx timeout guard.

These tests target the behavioural fixes:
- search_kb_articles must not query the article body (criteria[1])
  unless search_content=True is passed explicitly.
- list_kb_articles must clamp range_limit to 10 when range_start > 60
  and range_limit > 10, and surface that via _clamped_range_limit.
- _request must turn an httpx.TimeoutException into a structured
  {"error": "Timeout HTTP", ...} dict.
"""

import os
import sys
from pathlib import Path

# Configure GLPI env BEFORE importing server so the module-level config
# read does not try to load credentials from disk.
os.environ.setdefault("GLPI_URL", "https://glpi.test.local")
os.environ.setdefault("GLPI_APP_TOKEN", "app-token-test")
os.environ.setdefault("GLPI_USER_TOKEN", "user-token-test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402

import server  # noqa: E402


@pytest.fixture(autouse=True)
def _stub_session():
    """Skip the real initSession round trip by injecting a token."""
    server._session_token = "stub-session-token"
    yield
    server._session_token = None


def _params_of(call) -> dict:
    """Return the multi-dict of query params from a captured respx call."""
    return dict(httpx.URL(str(call.request.url)).params.multi_items())


@pytest.mark.asyncio
@respx.mock
async def test_search_kb_articles_default_skips_content_field():
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/search/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json={"data": [], "totalcount": 0}))

    await server.search_kb_articles(keywords="vpn")

    assert route.called, "search endpoint was not called"
    params = _params_of(respx.calls.last)
    assert params.get("criteria[0][field]") == "6"
    assert params.get("criteria[0][value]") == "vpn"
    # criteria[1] must NOT be present in the default mode
    assert "criteria[1][field]" not in params
    assert "criteria[1][value]" not in params


@pytest.mark.asyncio
@respx.mock
async def test_search_kb_articles_with_search_content_includes_body_field():
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/search/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json={"data": [], "totalcount": 0}))

    await server.search_kb_articles(keywords="vpn", search_content=True)

    assert route.called
    params = _params_of(respx.calls.last)
    assert params.get("criteria[0][field]") == "6"
    assert params.get("criteria[1][field]") == "7"
    assert params.get("criteria[1][value]") == "vpn"
    assert params.get("criteria[1][searchtype]") == "contains"


@pytest.mark.asyncio
@respx.mock
async def test_list_kb_articles_clamps_range_limit_when_offset_above_60():
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json=[{"id": 1}, {"id": 2}]))

    result = await server.list_kb_articles(range_start=80, range_limit=50)

    assert route.called
    params = _params_of(respx.calls.last)
    # 80-89 instead of 80-129 because clamped to 10
    assert params.get("range") == "80-89"

    assert isinstance(result, dict)
    assert result["_clamped_range_limit"] == 10
    assert "_warning" in result
    assert "memory_limit" in result["_warning"]
    assert result["items"] == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
@respx.mock
async def test_list_kb_articles_no_clamping_for_small_offset():
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json=[{"id": 1}]))

    result = await server.list_kb_articles(range_start=0, range_limit=50)

    assert route.called
    params = _params_of(respx.calls.last)
    assert params.get("range") == "0-49"
    # Default path returns the bare list, no clamping wrapper
    assert isinstance(result, list)


@pytest.mark.asyncio
@respx.mock
async def test_request_returns_structured_error_on_httpx_timeout():
    respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/KnowbaseItem"
    ).mock(side_effect=httpx.ReadTimeout("simulated read timeout"))

    result = await server.glpi.get("/KnowbaseItem", params={"range": "0-9"})

    assert isinstance(result, dict)
    assert result.get("error") == "Timeout HTTP"
    assert "30" in result.get("detail", "")
