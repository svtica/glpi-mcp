"""Smoke tests for create_ticket.

Covers the requester override: requester_user_id maps to
_users_id_requester, and is omitted entirely when left at None so GLPI
keeps its default (the API session user).
"""

import os
import sys
from pathlib import Path

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


def _input_of(call) -> dict:
    return json.loads(call.request.content)["input"]


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_sets_requester_when_given():
    route = respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Ticket").mock(
        return_value=httpx.Response(201, json={"id": 9001})
    )

    await server.create_ticket(
        name="[Sauvegarde] Job en échec",
        content="<p>test</p>",
        category_id=18,
        priority=4,
        requester_user_id=107,
    )

    sent = _input_of(route.calls[0])
    assert sent["_users_id_requester"] == 107
    assert sent["itilcategories_id"] == 18
    assert "_users_id_assign" not in sent
    assert "_groups_id_assign" not in sent


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_omits_requester_by_default():
    route = respx.post(f"{server.GLPI_URL}{server._API_PREFIX}/Ticket").mock(
        return_value=httpx.Response(201, json={"id": 9002})
    )

    await server.create_ticket(name="Ticket manuel", content="<p>test</p>")

    assert "_users_id_requester" not in _input_of(route.calls[0])
