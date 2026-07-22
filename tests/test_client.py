import asyncio, json, ssl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ha_client import HAClient


# ── URL / init ───────────────────────────────────────────────────────────────

def test_http_url_to_ws():
    c = HAClient("http://192.168.1.100:8123", "token")
    assert c.ws_url == "ws://192.168.1.100:8123/api/websocket"
    assert c.base_url == "http://192.168.1.100:8123"

def test_https_url_to_wss():
    c = HAClient("https://home.example.com", "token")
    assert c.ws_url == "wss://home.example.com/api/websocket"
    assert c.base_url == "https://home.example.com"

def test_trailing_slash_stripped():
    c = HAClient("http://192.168.1.100:8123/", "token")
    assert c.base_url == "http://192.168.1.100:8123"
    assert c.ws_url == "ws://192.168.1.100:8123/api/websocket"

def test_ssl_ctx_verify_true_returns_none():
    c = HAClient("http://test.local", "token", verify_ssl=True)
    assert c._ssl_ctx() is None

def test_ssl_ctx_verify_false_returns_context():
    c = HAClient("http://test.local", "token", verify_ssl=False)
    ctx = c._ssl_ctx()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE

def test_initial_state_empty():
    c = HAClient("http://test.local", "token")
    assert c.state_cache == {}
    assert c.history == {}
    assert c.session is None
    assert c._ws is None

def test_history_trimming_logic():
    c = HAClient("http://test.local", "token")
    ent = "sensor.x"
    c.history[ent] = list(range(601))
    if len(c.history[ent]) > 600:
        c.history[ent] = c.history[ent][-600:]
    assert len(c.history[ent]) == 600
    assert c.history[ent][0] == 1

def test_call_service_splits_domain():
    domain, srv = "homeassistant/toggle".split("/")
    assert domain == "homeassistant"
    assert srv == "toggle"


# ── connect_ws ────────────────────────────────────────────────────────────────

def _fake_ws(recv_payloads):
    ws = MagicMock()
    ws.recv = AsyncMock(side_effect=[json.dumps(p) for p in recv_payloads])
    ws.send = AsyncMock()
    return ws


async def test_connect_ws_success():
    client = HAClient("http://test.local", "mytoken")
    ws = _fake_ws([{"type": "auth_required"}, {"type": "auth_ok"}])

    with patch("ha_client.aiohttp.ClientSession") as mock_cls, \
         patch("ha_client.websockets.connect", new_callable=AsyncMock, return_value=ws):
        await client.connect_ws()

    assert client._ws is ws
    assert client.session is mock_cls.return_value
    assert client.connected is True
    assert ws.send.call_count == 2  # auth + subscribe


async def test_connect_ws_reuses_existing_session():
    client = HAClient("http://test.local", "token")
    existing = MagicMock()
    client.session = existing
    ws = _fake_ws([{"type": "auth_required"}, {"type": "auth_ok"}])

    with patch("ha_client.aiohttp.ClientSession") as mock_cls, \
         patch("ha_client.websockets.connect", new_callable=AsyncMock, return_value=ws):
        await client.connect_ws()

    mock_cls.assert_not_called()
    assert client.session is existing


async def test_connect_ws_wrong_first_message():
    client = HAClient("http://test.local", "token")
    ws = _fake_ws([{"type": "unexpected"}])

    with patch("ha_client.aiohttp.ClientSession"), \
         patch("ha_client.websockets.connect", new_callable=AsyncMock, return_value=ws):
        with pytest.raises(RuntimeError, match="Expected auth_required"):
            await client.connect_ws()


async def test_connect_ws_auth_failed():
    client = HAClient("http://test.local", "token")
    ws = _fake_ws([{"type": "auth_required"}, {"type": "auth_invalid", "message": "Bad token"}])

    with patch("ha_client.aiohttp.ClientSession"), \
         patch("ha_client.websockets.connect", new_callable=AsyncMock, return_value=ws):
        with pytest.raises(RuntimeError, match="Autenticación fallida"):
            await client.connect_ws()


# ── initial_states ────────────────────────────────────────────────────────────

def _mock_get(response_data):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=response_data)
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=resp)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


async def test_initial_states_updates_cache_and_history():
    client = HAClient("http://test.local", "token")
    client.session = _mock_get([
        {"entity_id": "sensor.temp", "state": "21.5"},
        {"entity_id": "sensor.door", "state": "on"},
    ])
    await client.initial_states()

    assert client.state_cache["sensor.temp"]["state"] == "21.5"
    assert client.history["sensor.temp"] == [21.5]
    assert "sensor.door" in client.state_cache
    assert "sensor.door" not in client.history  # non-numeric not added


# ── call_service ──────────────────────────────────────────────────────────────

def _mock_post(response_data):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=response_data)
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=resp)
    session.post.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


async def test_call_service_returns_response():
    client = HAClient("http://test.local", "token")
    client.session = _mock_post({"result": "ok"})

    result = await client.call_service("light/turn_on", {"entity_id": "light.test"})

    assert result == {"result": "ok"}
    call_url = client.session.post.call_args[0][0]
    assert call_url == "http://test.local/api/services/light/turn_on"


# ── close ─────────────────────────────────────────────────────────────────────

async def test_close_with_ws_and_session():
    client = HAClient("http://test.local", "token")
    client._ws = AsyncMock()
    client.session = AsyncMock()
    await client.close()
    client._ws.close.assert_called_once()
    client.session.close.assert_called_once()


async def test_close_without_ws_or_session():
    client = HAClient("http://test.local", "token")
    await client.close()  # should not raise


# ── pump ──────────────────────────────────────────────────────────────────────

class _FakeWS:
    def __init__(self, messages):
        self._messages = list(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        raise StopAsyncIteration


def _state_changed_msg(entity_id, state):
    return json.dumps({
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {"new_state": {"entity_id": entity_id, "state": state}},
        },
    })


async def _run_pump_once(client):
    """Run pump until it sleeps, then cancel."""
    async def fake_sleep(_):
        raise asyncio.CancelledError()

    with patch("ha_client.asyncio.sleep", side_effect=fake_sleep), \
         patch.object(client, "connect_ws", new_callable=AsyncMock):
        try:
            await client.pump()
        except asyncio.CancelledError:
            pass


async def test_pump_processes_state_changed():
    client = HAClient("http://test.local", "token")
    client._ws = _FakeWS([_state_changed_msg("sensor.test", "25.0")])
    await _run_pump_once(client)

    assert client.state_cache["sensor.test"]["state"] == "25.0"
    assert client.history["sensor.test"] == [25.0]


async def test_pump_ignores_non_numeric_state():
    client = HAClient("http://test.local", "token")
    client._ws = _FakeWS([_state_changed_msg("binary_sensor.door", "on")])
    await _run_pump_once(client)

    assert "binary_sensor.door" in client.state_cache
    assert "binary_sensor.door" not in client.history


async def test_pump_trims_history_at_600():
    client = HAClient("http://test.local", "token")
    client.history["sensor.x"] = list(range(600))
    client._ws = _FakeWS([_state_changed_msg("sensor.x", "999.0")])
    await _run_pump_once(client)

    assert len(client.history["sensor.x"]) == 600
    assert client.history["sensor.x"][-1] == 999.0


async def test_pump_ignores_null_new_state():
    client = HAClient("http://test.local", "token")
    msg = json.dumps({
        "type": "event",
        "event": {"event_type": "state_changed", "data": {"new_state": None}},
    })
    client._ws = _FakeWS([msg])
    await _run_pump_once(client)

    assert client.state_cache == {}


async def test_pump_calls_on_state_change_callback():
    client = HAClient("http://test.local", "token")
    calls = []
    client.on_state_change = lambda: calls.append(1)
    client._ws = _FakeWS([_state_changed_msg("light.kitchen", "on")])
    await _run_pump_once(client)

    assert len(calls) == 1


async def test_pump_on_state_change_not_called_for_null_state():
    client = HAClient("http://test.local", "token")
    calls = []
    client.on_state_change = lambda: calls.append(1)
    msg = json.dumps({
        "type": "event",
        "event": {"event_type": "state_changed", "data": {"new_state": None}},
    })
    client._ws = _FakeWS([msg])
    await _run_pump_once(client)

    assert len(calls) == 0
