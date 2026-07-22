import pytest, yaml
from unittest.mock import AsyncMock, MagicMock, patch
from textual.app import App, ComposeResult
from textual.widgets import Static, Button

import ha_tui
from ha_tui import HADashboard, load_config
from widgets import SpotifyWidget, WeatherWidget


# ── load_config ───────────────────────────────────────────────────────────────

def test_load_config_basic(tmp_path):
    f = tmp_path / "test.yml"
    f.write_text("ha:\n  url: 'http://192.168.1.1:8123'\n  token: 'tok'\npages:\n  - id: home\n    title: Home\n    sections: []\n")
    cfg = load_config(str(f))
    assert cfg["ha"]["url"] == "http://192.168.1.1:8123"
    assert cfg["pages"][0]["id"] == "home"


def test_load_config_env_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_HA_TOKEN", "secret123")
    f = tmp_path / "test.yml"
    f.write_text("ha:\n  token: '${TEST_HA_TOKEN}'\n  url: 'http://localhost'\npages: []\n")
    cfg = load_config(str(f))
    assert cfg["ha"]["token"] == "secret123"


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_ha():
    ha = MagicMock()
    ha.state_cache = {}
    ha.history = {}
    ha.connect_ws = AsyncMock()
    ha.initial_states = AsyncMock()
    ha.pump = AsyncMock()
    ha.close = AsyncMock()
    ha.connected = True
    return ha


_MINIMAL_CFG = {
    "ha": {"url": "http://test.local", "token": "tok", "verify_ssl": False},
    "ui": {"refresh_ms": 250},
    "pages": [
        {
            "id": "home", "title": "Home",
            "sections": [
                {
                    "layout": "grid-2",
                    "widgets": [
                        {"type": "value", "entity": "sensor.x", "label": "X"},
                        {"type": "binary", "entity": "binary_sensor.y", "label": "Y"},
                    ],
                }
            ],
        },
        {
            "id": "p2", "title": "Page 2",
            "sections": [{"layout": "grid-1", "widgets": [{"type": "heading", "text": "T"}]}],
        },
    ],
}

_CFG_WITH_TITLE = {
    **_MINIMAL_CFG,
    "pages": [
        {
            "id": "home", "title": "Home",
            "sections": [
                {
                    "title": "Oficina",
                    "layout": "grid-1",
                    "widgets": [{"type": "toggle", "entity": "light.x", "label": "Luz"}],
                }
            ],
        }
    ],
}

_CFG_NO_SECTIONS = {
    "ha": {"url": "http://test.local", "token": "tok"},
    "ui": {"refresh_ms": 250},
    "pages": [
        {
            "id": "home", "title": "Home",
            "layout": "grid-1",
            "widgets": [{"type": "value", "entity": "sensor.x", "label": "X"}],
        }
    ],
}


# ── SpotifyWidget via Textual Pilot ───────────────────────────────────────────

class _SpotifyApp(App):
    CSS = """
    SpotifyWidget { height: 9; border: round; padding: 0; }
    SpotifyWidget #sp-info { border: none; padding: 0 1; height: 1fr; }
    SpotifyWidget #sp-controls { height: 3; }
    SpotifyWidget .sp-btn { width: 1fr; border: none; min-width: 3; }
    """

    def __init__(self, state_cache, ha):
        super().__init__()
        self._sc = state_cache
        self._ha = ha

    def compose(self) -> ComposeResult:
        yield SpotifyWidget("media_player.spotify", "Spotify", self._ha, self._sc, {})


async def test_spotify_unavailable():
    app = _SpotifyApp(state_cache={}, ha=AsyncMock())
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(SpotifyWidget)
        widget._tick()
        await pilot.pause()
        info = app.query_one("#sp-info", Static)
        assert "No disponible" in str(info.render())


async def test_spotify_playing():
    sc = {
        "media_player.spotify": {
            "state": "playing",
            "attributes": {
                "media_title": "Bohemian Rhapsody",
                "media_artist": "Queen",
                "media_position": 60,
                "media_duration": 360,
            },
        }
    }
    app = _SpotifyApp(state_cache=sc, ha=AsyncMock())
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(SpotifyWidget)
        widget._tick()
        await pilot.pause()
        info = app.query_one("#sp-info", Static)
        play_btn = app.query_one("#sp-play", Button)
        assert "Bohemian Rhapsody" in str(info.render())
        assert "Queen" in str(info.render())
        assert "⏸" in str(play_btn.label)


async def test_spotify_paused():
    sc = {
        "media_player.spotify": {
            "state": "paused",
            "attributes": {"media_title": "Song", "media_artist": "Artist",
                           "media_position": 0, "media_duration": 0},
        }
    }
    app = _SpotifyApp(state_cache=sc, ha=AsyncMock())
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(SpotifyWidget)
        widget._tick()
        await pilot.pause()
        play_btn = app.query_one("#sp-play", Button)
        assert "▶" in str(play_btn.label)


async def test_spotify_idle_state():
    sc = {
        "media_player.spotify": {
            "state": "idle",
            "attributes": {"media_position": 0, "media_duration": 0},
        }
    }
    app = _SpotifyApp(state_cache=sc, ha=AsyncMock())
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(SpotifyWidget)
        widget._tick()
        await pilot.pause()
        info = app.query_one("#sp-info", Static)
        assert "idle" in str(info.render())


async def test_spotify_with_progress_bar():
    sc = {
        "media_player.spotify": {
            "state": "playing",
            "attributes": {"media_title": "X", "media_artist": "Y",
                           "media_position": 90, "media_duration": 180},
        }
    }
    app = _SpotifyApp(state_cache=sc, ha=AsyncMock())
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(SpotifyWidget)
        widget._tick()
        await pilot.pause()
        info = app.query_one("#sp-info", Static)
        assert "█" in str(info.render())
        assert "░" in str(info.render())


async def test_spotify_prev_button():
    mock_ha = AsyncMock()
    sc = {
        "media_player.spotify": {
            "state": "playing",
            "attributes": {"media_title": "X", "media_artist": "Y",
                           "media_position": 0, "media_duration": 0},
        }
    }
    app = _SpotifyApp(state_cache=sc, ha=mock_ha)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click("#sp-prev")
        await pilot.pause()
    mock_ha.call_service.assert_called_with(
        "media_player/media_previous_track", {"entity_id": "media_player.spotify"}
    )


async def test_spotify_play_button():
    mock_ha = AsyncMock()
    sc = {"media_player.spotify": {"state": "playing",
                                    "attributes": {"media_position": 0, "media_duration": 0}}}
    app = _SpotifyApp(state_cache=sc, ha=mock_ha)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click("#sp-play")
        await pilot.pause()
    mock_ha.call_service.assert_called_with(
        "media_player/media_play_pause", {"entity_id": "media_player.spotify"}
    )


async def test_spotify_next_button():
    mock_ha = AsyncMock()
    sc = {"media_player.spotify": {"state": "playing",
                                    "attributes": {"media_position": 0, "media_duration": 0}}}
    app = _SpotifyApp(state_cache=sc, ha=mock_ha)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click("#sp-next")
        await pilot.pause()
    mock_ha.call_service.assert_called_with(
        "media_player/media_next_track", {"entity_id": "media_player.spotify"}
    )


# ── WeatherWidget on_mount via Textual Pilot ──────────────────────────────────

class _WeatherApp(App):
    CSS = "WeatherWidget { height: 12; border: round; padding: 1; }"

    def __init__(self, state_cache, ha):
        super().__init__()
        self._sc = state_cache
        self._ha = ha

    def compose(self) -> ComposeResult:
        yield WeatherWidget("weather.home", "Home", ha=self._ha, state_cache=self._sc)


async def test_weather_on_mount_fetches_forecast():
    mock_ha = AsyncMock()
    mock_ha.call_service.return_value = {
        "weather.home": {"forecasts": [{"datetime": "2026-07-21", "temperature": 20, "condition": "sunny"}]}
    }
    sc = {"weather.home": {"state": "sunny", "attributes": {"temperature": 20}}}
    app = _WeatherApp(state_cache=sc, ha=mock_ha)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.2)
        mock_ha.call_service.assert_called()


# ── HADashboard via Textual Pilot ─────────────────────────────────────────────

async def test_dashboard_builds_page():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            assert "Home" in app.title


async def test_dashboard_title_includes_page_count():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            assert "1/2" in app.title


async def test_dashboard_section_title_rendered():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_CFG_WITH_TITLE)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            headings = app.query(".section-heading")
            assert any("Oficina" in str(w.render()) for w in headings)


async def test_dashboard_page_without_sections():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_CFG_NO_SECTIONS)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            assert "Home" in app.title


async def test_dashboard_navigate_next():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            assert app.page_idx == 0
            await pilot.press("right")
            await pilot.pause(0.2)
            assert app.page_idx == 1


async def test_dashboard_navigate_prev_wraps():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("left")
            await pilot.pause(0.2)
            assert app.page_idx == len(_MINIMAL_CFG["pages"]) - 1


async def test_dashboard_reload_config(tmp_path):
    cfg_file = tmp_path / "dash.yml"
    cfg_file.write_text(yaml.dump(_MINIMAL_CFG))
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG, config_path=str(cfg_file))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("r")
            await pilot.pause(0.2)
            assert "Home" in app.title


async def test_dashboard_custom_keybinds():
    cfg = {
        **_MINIMAL_CFG,
        "keybinds": {"next_page": "n", "prev_page": "p", "reload_config": "r", "quit": "q"},
    }
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(cfg)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            assert any(b[0] == "n" for b in app.BINDINGS)


async def test_dashboard_connection_error():
    mock_ha = _mock_ha()
    mock_ha.connect_ws = AsyncMock(side_effect=Exception("Connection refused"))
    with patch("ha_tui.HAClient", return_value=mock_ha):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            errors = app.query(".error")
            assert len(errors) > 0


async def test_dashboard_quit():
    with patch("ha_tui.HAClient", return_value=_mock_ha()):
        app = HADashboard(_MINIMAL_CFG)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await pilot.press("q")
