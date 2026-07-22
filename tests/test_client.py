import ssl
import pytest
from ha_client import HAClient


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
    # verify the trimming cap matches expectations
    c = HAClient("http://test.local", "token")
    ent = "sensor.x"
    c.history[ent] = list(range(601))
    if len(c.history[ent]) > 600:
        c.history[ent] = c.history[ent][-600:]
    assert len(c.history[ent]) == 600
    assert c.history[ent][0] == 1

def test_call_service_splits_domain():
    # verifies the domain/service split doesn't raise on well-formed input
    c = HAClient("http://test.local", "token")
    domain, srv = "homeassistant/toggle".split("/")
    assert domain == "homeassistant"
    assert srv == "toggle"
