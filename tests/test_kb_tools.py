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


@pytest.fixture(autouse=True)
def _reset_search_options_cache():
    """Each test starts with a clean discovery cache."""
    server._search_options_cache.clear()
    yield
    server._search_options_cache.clear()


def _params_of(call) -> dict:
    """Return the multi-dict of query params from a captured respx call."""
    return dict(httpx.URL(str(call.request.url)).params.multi_items())


def _stub_listSearchOptions(itemtype: str, mapping: dict) -> None:
    """Mock listSearchOptions for an itemtype with the given column→ID mapping.

    Returned shape mimics GLPI's REST response: numeric keys with a meta
    dict that carries at least the {"field": <column>} attribute.
    """
    payload = {"common": {"name": "Common"}}
    for column, field_id in mapping.items():
        payload[str(field_id)] = {"table": f"glpi_{itemtype.lower()}s", "field": column, "name": column.title()}
    respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/listSearchOptions/{itemtype}"
    ).mock(return_value=httpx.Response(200, json=payload))


def _stub_listSearchOptions_unavailable(itemtype: str) -> None:
    """Mock listSearchOptions returning a GLPI-style error payload."""
    respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/listSearchOptions/{itemtype}"
    ).mock(return_value=httpx.Response(404, json=["ERROR_ENDPOINT_NOT_FOUND", "endpoint missing"]))


@pytest.mark.asyncio
@respx.mock
async def test_search_kb_articles_default_skips_content_field():
    _stub_listSearchOptions("KnowbaseItem", {"name": "6", "answer": "7"})
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
    _stub_listSearchOptions("KnowbaseItem", {"name": "6", "answer": "7"})
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
async def test_search_kb_articles_uses_discovered_field_ids_when_not_six_and_seven():
    # GLPI 11 (or any non-default schema) returns different numeric IDs.
    _stub_listSearchOptions("KnowbaseItem", {"name": "12", "answer": "21"})
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/search/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json={"data": [], "totalcount": 0}))

    await server.search_kb_articles(keywords="vpn", search_content=True)

    assert route.called
    params = _params_of(respx.calls.last)
    assert params.get("criteria[0][field]") == "12"
    assert params.get("criteria[1][field]") == "21"


@pytest.mark.asyncio
@respx.mock
async def test_search_kb_articles_falls_back_to_legacy_ids_when_discovery_unavailable():
    _stub_listSearchOptions_unavailable("KnowbaseItem")
    route = respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/search/KnowbaseItem"
    ).mock(return_value=httpx.Response(200, json={"data": [], "totalcount": 0}))

    await server.search_kb_articles(keywords="vpn", search_content=True)

    assert route.called
    params = _params_of(respx.calls.last)
    # Discovery returned an error payload — defaults must apply.
    assert params.get("criteria[0][field]") == "6"
    assert params.get("criteria[1][field]") == "7"


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
    assert result["_warning"] == server.LABEL_KB_CLAMP_WARNING
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


def test_localized_labels_exist_for_fr_and_en():
    """The new strings must be defined in both language tables."""
    for lang in ("fr", "en"):
        bag = server._MAPPINGS[lang]
        for key in ("HTTP_TIMEOUT_ERROR", "HTTP_TIMEOUT_DETAIL", "KB_CLAMP_WARNING"):
            assert key in bag, f"missing {key} for lang={lang}"
            assert isinstance(bag[key], str)
            assert bag[key].strip(), f"empty {key} for lang={lang}"
    # FR and EN strings should not be identical for any of the three keys
    for key in ("HTTP_TIMEOUT_ERROR", "HTTP_TIMEOUT_DETAIL", "KB_CLAMP_WARNING"):
        assert server._MAPPINGS["fr"][key] != server._MAPPINGS["en"][key], (
            f"{key} should differ between fr and en"
        )


@pytest.mark.asyncio
@respx.mock
async def test_request_returns_structured_error_on_httpx_timeout():
    respx.get(
        f"{server.GLPI_URL}{server._API_PREFIX}/KnowbaseItem"
    ).mock(side_effect=httpx.ReadTimeout("simulated read timeout"))

    result = await server.glpi.get("/KnowbaseItem", params={"range": "0-9"})

    assert isinstance(result, dict)
    assert result.get("error") == server.LABEL_HTTP_TIMEOUT_ERROR
    assert result.get("detail") == server.LABEL_HTTP_TIMEOUT_DETAIL
    assert "30" in result.get("detail", "")
