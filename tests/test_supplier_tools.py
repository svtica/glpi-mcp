"""Smoke tests for the supplier / contact / contract tools.

These cover the behaviours that are easy to get wrong:
- list_suppliers builds the right range and searchText params, and the
  only_active filter can be turned off.
- create_* omit every optional field left at None instead of sending
  nulls to GLPI (which would blank out defaults).
- create_contact / create_contract only create the junction-table entry
  when supplier_id is supplied AND the parent creation returned an id.
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

import json  # noqa: E402

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


def _input_of(call) -> dict:
    """Return the {"input": ...} payload sent on a captured respx call."""
    return json.loads(call.request.content)["input"]


# ── list_suppliers ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_suppliers_defaults_to_active_only_with_pagination():
    route = respx.get(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Acme Telecom"}])
    )

    result = await server.list_suppliers()

    assert route.called
    params = _params_of(respx.calls.last)
    assert params.get("range") == "0-49"
    assert params.get("searchText[is_active]") == "1"
    assert "searchText[name]" not in params
    assert result == [{"id": 1, "name": "Acme Telecom"}]


@pytest.mark.asyncio
@respx.mock
async def test_list_suppliers_can_filter_by_name_and_include_inactive():
    respx.get(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier").mock(
        return_value=httpx.Response(200, json=[])
    )

    await server.list_suppliers(
        name_contains="acme", only_active=False, range_start=50, range_limit=25
    )

    params = _params_of(respx.calls.last)
    assert params.get("range") == "50-74"
    assert params.get("searchText[name]") == "acme"
    assert "searchText[is_active]" not in params


# ── create_supplier ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_create_supplier_omits_unset_optional_fields():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier").mock(
        return_value=httpx.Response(201, json={"id": 42, "message": ""})
    )

    result = await server.create_supplier(name="Acme Telecom")

    payload = _input_of(respx.calls.last)
    assert payload == {"name": "Acme Telecom", "is_active": 1}
    assert result["id"] == 42


@pytest.mark.asyncio
@respx.mock
async def test_create_supplier_sends_provided_fields_and_inactive_flag():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier").mock(
        return_value=httpx.Response(201, json={"id": 43})
    )

    await server.create_supplier(
        name="Acme Supplies",
        supplier_type_id=3,
        town="Springfield",
        email="sales@example.com",
        is_active=False,
    )

    payload = _input_of(respx.calls.last)
    assert payload["suppliertypes_id"] == 3
    assert payload["town"] == "Springfield"
    assert payload["email"] == "sales@example.com"
    assert payload["is_active"] == 0
    # Untouched optional fields must not be sent at all.
    assert "fax" not in payload
    assert "website" not in payload


# ── create_contact ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_create_contact_without_supplier_does_not_touch_junction_table():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contact").mock(
        return_value=httpx.Response(201, json={"id": 7})
    )
    link_route = respx.post(
        f"{server.GLPI_URL}{server._API_PREFIX}/Contact_Supplier"
    ).mock(return_value=httpx.Response(201, json={"id": 99}))

    result = await server.create_contact(name="Doe", firstname="Jane")

    assert not link_route.called
    assert "_supplier_link" not in result


@pytest.mark.asyncio
@respx.mock
async def test_create_contact_with_supplier_creates_the_link():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contact").mock(
        return_value=httpx.Response(201, json={"id": 7})
    )
    link_route = respx.post(
        f"{server.GLPI_URL}{server._API_PREFIX}/Contact_Supplier"
    ).mock(return_value=httpx.Response(201, json={"id": 99}))

    result = await server.create_contact(name="Doe", supplier_id=42)

    assert link_route.called
    link_payload = _input_of(link_route.calls.last)
    assert link_payload == {"contacts_id": 7, "suppliers_id": 42}
    assert result["_supplier_link"]["id"] == 99


@pytest.mark.asyncio
@respx.mock
async def test_create_contact_skips_link_when_creation_failed():
    """A GLPI error payload has no 'id' — linking must be skipped."""
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contact").mock(
        return_value=httpx.Response(400, json=["ERROR_GLPI_ADD", "champ manquant"])
    )
    link_route = respx.post(
        f"{server.GLPI_URL}{server._API_PREFIX}/Contact_Supplier"
    ).mock(return_value=httpx.Response(201, json={"id": 99}))

    result = await server.create_contact(name="Doe", supplier_id=42)

    assert not link_route.called
    assert result.get("error") == "ERROR_GLPI_ADD"


# ── create_contract ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_create_contract_omits_unset_optional_fields():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contract").mock(
        return_value=httpx.Response(201, json={"id": 12})
    )

    await server.create_contract(name="Entretien annuel")

    payload = _input_of(respx.calls.last)
    assert payload == {"name": "Entretien annuel"}


@pytest.mark.asyncio
@respx.mock
async def test_create_contract_with_supplier_creates_the_link():
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contract").mock(
        return_value=httpx.Response(201, json={"id": 12})
    )
    link_route = respx.post(
        f"{server.GLPI_URL}{server._API_PREFIX}/Contract_Supplier"
    ).mock(return_value=httpx.Response(201, json={"id": 55}))

    result = await server.create_contract(
        name="Entretien annuel",
        num="CT-2026-014",
        begin_date="2026-01-01",
        duration=36,
        notice=3,
        supplier_id=42,
    )

    payload = _input_of(respx.calls[0])
    assert payload["num"] == "CT-2026-014"
    assert payload["begin_date"] == "2026-01-01"
    assert payload["duration"] == 36
    assert payload["notice"] == 3

    assert link_route.called
    assert _input_of(link_route.calls.last) == {"contracts_id": 12, "suppliers_id": 42}
    assert result["_supplier_link"]["id"] == 55


@pytest.mark.asyncio
@respx.mock
async def test_create_contract_zero_values_are_preserved():
    """0 is a meaningful GLPI value (e.g. notice = no notice period)."""
    respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Contract").mock(
        return_value=httpx.Response(201, json={"id": 13})
    )

    await server.create_contract(name="Contract without notice", notice=0, duration=0)

    payload = _input_of(respx.calls.last)
    assert payload["notice"] == 0
    assert payload["duration"] == 0


# ── update_* ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "tool_name, itemtype",
    [
        ("update_supplier", "Supplier"),
        ("update_contact", "Contact"),
        ("update_contract", "Contract"),
    ],
)
async def test_update_tools_put_only_the_given_fields(tool_name, itemtype):
    route = respx.put(f"{server.GLPI_URL}{server._API_PREFIX}/{itemtype}/42").mock(
        return_value=httpx.Response(200, json=[{"42": True, "message": ""}])
    )

    await getattr(server, tool_name)(42, {"name": "Nouveau nom"})

    assert route.called
    assert _input_of(respx.calls.last) == {"name": "Nouveau nom"}


@pytest.mark.asyncio
@respx.mock
async def test_update_supplier_can_restore_from_trash():
    respx.put(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier/42").mock(
        return_value=httpx.Response(200, json=[{"42": True}])
    )

    await server.update_supplier(42, {"is_deleted": 0})

    assert _input_of(respx.calls.last) == {"is_deleted": 0}


# ── delete_* ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "tool_name, itemtype",
    [
        ("delete_supplier", "Supplier"),
        ("delete_contact", "Contact"),
        ("delete_contract", "Contract"),
    ],
)
async def test_delete_tools_default_to_trash_not_purge(tool_name, itemtype):
    """Without purge=True, force_purge must never reach GLPI."""
    route = respx.delete(f"{server.GLPI_URL}{server._API_PREFIX}/{itemtype}/42").mock(
        return_value=httpx.Response(200, json=[{"42": True}])
    )

    await getattr(server, tool_name)(42)

    assert route.called
    assert "force_purge" not in _params_of(respx.calls.last)


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "tool_name, itemtype",
    [
        ("delete_supplier", "Supplier"),
        ("delete_contact", "Contact"),
        ("delete_contract", "Contract"),
    ],
)
async def test_delete_tools_send_force_purge_when_asked(tool_name, itemtype):
    respx.delete(f"{server.GLPI_URL}{server._API_PREFIX}/{itemtype}/42").mock(
        return_value=httpx.Response(200, json=[{"42": True}])
    )

    await getattr(server, tool_name)(42, purge=True)

    assert _params_of(respx.calls.last).get("force_purge") == "true"


@pytest.mark.asyncio
@respx.mock
async def test_client_delete_without_params_keeps_a_clean_url():
    """Regression guard: the params kwarg must not append a stray '?'."""
    route = respx.delete(f"{server.GLPI_URL}{server._API_PREFIX}/Supplier/42").mock(
        return_value=httpx.Response(200, json=[{"42": True}])
    )

    await server.glpi.delete("/Supplier/42")

    assert route.called
    assert str(respx.calls.last.request.url).endswith("/Supplier/42")


# ── Server instructions ────────────────────────────────────────────────────

def test_server_instructions_carry_the_registry_guardrails():
    """The consuming agent only sees these instructions — keep them intact.

    Each assertion maps to a guardrail that has a real cost if it is dropped:
    duplicate suppliers, a purge that was meant to be a deactivation, or a
    partial update that silently blanks fields.
    """
    text = server.mcp.instructions

    # The pre-existing HTML rule must survive the additions.
    assert "GLPI-compatible HTML" in text
    assert "Never use Markdown" in text

    for fragment in (
        "list_suppliers first",          # check before creating
        "'is_active': 0",                # deactivate rather than delete
        "trash",                         # soft delete is the default
        "'is_deleted': 0",               # how to restore
        "IRREVERSIBLE",                  # purge is called out
        "purge=True on your own initiative",
        "MONTHS",                        # duration convention
        "YYYY-MM-DD",
        "_supplier_link",
        "structured error dicts",        # verify before reporting success
    ):
        assert fragment in text, f"missing guardrail in instructions: {fragment}"


def test_server_instructions_mention_every_write_tool_of_the_registry():
    text = server.mcp.instructions
    for tool_name in (
        "list_suppliers",
        "create_contact",
        "create_contract",
        "update_supplier",
        "delete_supplier",
        "delete_contact",
        "delete_contract",
    ):
        assert tool_name in text, f"{tool_name} not covered by the instructions"


# ── Registration ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_tools_are_registered_with_fastmcp():
    names = {tool.name for tool in await server.mcp.list_tools()}
    for expected in (
        "list_suppliers",
        "create_supplier",
        "create_contact",
        "create_contract",
        "update_supplier",
        "update_contact",
        "update_contract",
        "delete_supplier",
        "delete_contact",
        "delete_contract",
    ):
        assert expected in names, f"{expected} not registered as an MCP tool"
