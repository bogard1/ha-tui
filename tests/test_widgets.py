import pytest
from unittest.mock import AsyncMock, patch
from widgets import (
    ValueWidget, BinaryWidget, SparklineWidget, ValueSparklineWidget,
    ToggleWidget, HeadingWidget, ActionWidget, ClimateWidget, WeatherWidget, SpotifyWidget,
    make_widget, _sparkline,
)
from textual.widgets import Static


# ── _sparkline ───────────────────────────────────────────────────────────────

def test_sparkline_empty_data():
    assert _sparkline([], 60) == "─" * 36

def test_sparkline_respects_window():
    data = list(range(100))
    assert _sparkline(data, 10) == _sparkline(data[-10:], 10)

def test_sparkline_uniform_data():
    result = _sparkline([5.0] * 20, 60)
    assert len(set(result)) == 1

def test_sparkline_length():
    result = _sparkline(list(range(200)), 200)
    assert len(result) <= 36


# ── ValueWidget ───────────────────────────────────────────────────────────────

def test_value_widget_missing_entity():
    w = ValueWidget(entity="sensor.x", label="X", state_cache={})
    assert "X" in w.render()
    assert "—" in w.render()

def test_value_widget_numeric():
    sc = {"sensor.temp": {"state": "23.456"}}
    w = ValueWidget(entity="sensor.temp", label="Temp", unit="°C", fmt=".1f", state_cache=sc)
    result = w.render()
    assert "23.5°C" in result
    assert "Temp" in result

def test_value_widget_non_numeric_state():
    sc = {"sensor.status": {"state": "unavailable"}}
    w = ValueWidget(entity="sensor.status", label="Status", state_cache=sc)
    assert "unavailable" in w.render()

def test_value_widget_default_fmt():
    sc = {"sensor.x": {"state": "1.5"}}
    w = ValueWidget(entity="sensor.x", label="X", state_cache=sc)
    assert "1.50" in w.render()


# ── BinaryWidget ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("state,expected", [
    ("on", "ABIERTA"),
    ("open", "ABIERTA"),
    ("detected", "ABIERTA"),
    ("home", "ABIERTA"),
    ("off", "cerrada"),
    ("closed", "cerrada"),
])
def test_binary_widget_states(state, expected):
    sc = {"binary_sensor.door": {"state": state}}
    w = BinaryWidget(entity="binary_sensor.door", label="Puerta",
                     on_text="ABIERTA", off_text="cerrada", state_cache=sc)
    assert expected in w.render()

def test_binary_widget_missing_entity():
    w = BinaryWidget(entity="binary_sensor.x", label="X",
                     on_text="ON", off_text="off", state_cache={})
    assert "—" in w.render()


# ── SparklineWidget ───────────────────────────────────────────────────────────

def test_sparkline_widget_no_history():
    w = SparklineWidget(entity="sensor.x", label="X", history={})
    assert "─" in w.render()

def test_sparkline_widget_with_history():
    hist = {"sensor.x": [1.0, 2.0, 3.0, 4.0, 5.0]}
    w = SparklineWidget(entity="sensor.x", label="X", window=60, history=hist)
    assert "─" not in w.render()


# ── ValueSparklineWidget ──────────────────────────────────────────────────────

def test_value_sparkline_no_data():
    w = ValueSparklineWidget(entity="sensor.t", label="T", state_cache={}, history={})
    result = w.render()
    assert "T" in result
    assert "—" in result

def test_value_sparkline_with_value_and_history():
    sc = {"sensor.t": {"state": "21.5"}}
    hist = {"sensor.t": [20.0, 21.0, 21.5]}
    w = ValueSparklineWidget(entity="sensor.t", label="Temp", unit="°C", fmt=".1f",
                             state_cache=sc, history=hist)
    result = w.render()
    assert "21.5°C" in result
    assert "Temp" in result

def test_value_sparkline_non_numeric_state():
    sc = {"sensor.t": {"state": "unavailable"}}
    w = ValueSparklineWidget(entity="sensor.t", label="T", state_cache=sc, history={})
    assert "unavailable" in w.render()


# ── ToggleWidget ──────────────────────────────────────────────────────────────

def test_toggle_widget_on():
    sc = {"light.x": {"state": "on"}}
    w = ToggleWidget(entity="light.x", label="Luz", on_text="ON", off_text="off", state_cache=sc)
    result = w.render()
    assert "ON" in result
    assert "●" in result

def test_toggle_widget_off():
    sc = {"light.x": {"state": "off"}}
    w = ToggleWidget(entity="light.x", label="Luz", on_text="ON", off_text="off", state_cache=sc)
    result = w.render()
    assert "off" in result
    assert "○" in result

def test_toggle_widget_missing_entity():
    w = ToggleWidget(entity="light.x", label="Luz", state_cache={})
    assert "—" in w.render()


async def test_toggle_on_click_ha_none():
    w = ToggleWidget(entity="light.x", label="Luz", state_cache={}, ha=None)
    await w.on_click()  # early return, no crash


async def test_toggle_on_click_calls_service():
    mock_ha = AsyncMock()
    w = ToggleWidget(entity="light.x", label="Luz", state_cache={}, ha=mock_ha,
                     toggle_service="homeassistant/toggle")
    await w.on_click()
    mock_ha.call_service.assert_called_once_with("homeassistant/toggle", {"entity_id": "light.x"})


async def test_toggle_on_click_ignores_exception():
    mock_ha = AsyncMock()
    mock_ha.call_service.side_effect = Exception("timeout")
    w = ToggleWidget(entity="light.x", label="Luz", state_cache={}, ha=mock_ha)
    await w.on_click()  # should not raise


# ── ActionWidget ──────────────────────────────────────────────────────────────

# ── ClimateWidget ─────────────────────────────────────────────────────────────

def test_climate_widget_no_state():
    w = ClimateWidget(entity="climate.salon", label="Salón", state_cache={})
    assert "Salón" in w.render()
    assert "—" in w.render()

def test_climate_widget_heating():
    sc = {
        "climate.salon": {
            "state": "heat",
            "attributes": {"current_temperature": 20.5, "temperature": 22.0},
        }
    }
    w = ClimateWidget(entity="climate.salon", label="Salón", unit="°C", state_cache=sc)
    result = w.render()
    assert "20.5°C" in result
    assert "22.0°C" in result
    assert "🔥" in result
    assert "heat" in result

def test_climate_widget_off():
    sc = {
        "climate.salon": {
            "state": "off",
            "attributes": {"current_temperature": 19.0, "temperature": None},
        }
    }
    w = ClimateWidget(entity="climate.salon", label="Salón", state_cache=sc)
    result = w.render()
    assert "19.0°C" in result
    assert "—" in result      # target is None
    assert "○" in result

def test_climate_widget_unknown_mode():
    sc = {"climate.x": {"state": "custom_mode", "attributes": {}}}
    w = ClimateWidget(entity="climate.x", label="X", state_cache=sc)
    assert "◌" in w.render()


# ── ActionWidget ──────────────────────────────────────────────────────────────

def test_action_widget_shows_label():
    w = ActionWidget(label="Activar alarma", service="alarm/arm")
    assert "Activar alarma" in w.render()

def test_action_widget_no_status_initially():
    w = ActionWidget(label="X", service="s/v")
    assert "Ejecutando" not in w.render()


async def test_action_on_click_success():
    mock_ha = AsyncMock()
    w = ActionWidget(label="X", service="button/press", data={"entity_id": "button.x"}, ha=mock_ha)
    with patch.object(w, "refresh"):
        await w.on_click()
    assert w._status == "✓"


async def test_action_on_click_shows_error_on_failure():
    mock_ha = AsyncMock()
    mock_ha.call_service.side_effect = Exception("timeout")
    w = ActionWidget(label="X", service="button/press", ha=mock_ha)
    with patch.object(w, "refresh"):
        await w.on_click()
    assert "Error" in w._status


# ── WeatherWidget ─────────────────────────────────────────────────────────────

def test_weather_widget_no_state():
    w = WeatherWidget(entity="weather.home", label="Home", state_cache={})
    assert "No disponible" in w.render()

def test_weather_widget_current_conditions():
    sc = {
        "weather.home": {
            "state": "sunny",
            "attributes": {
                "temperature": 25,
                "humidity": 60,
                "wind_speed": 15,
                "wind_speed_unit": "km/h",
            },
        }
    }
    w = WeatherWidget(entity="weather.home", label="Casa", unit="°C", state_cache=sc)
    result = w.render()
    assert "25°C" in result
    assert "Casa" in result
    assert "60%" in result
    assert "15 km/h" in result
    assert "☀" in result

def test_weather_widget_forecast():
    sc = {
        "weather.home": {
            "state": "cloudy",
            "attributes": {
                "temperature": 18,
                "forecast": [
                    {"datetime": "2026-07-21T00:00:00", "temperature": 20, "templow": 12, "condition": "sunny"},
                    {"datetime": "2026-07-22T00:00:00", "temperature": 22, "templow": 14, "condition": "cloudy"},
                ],
            },
        }
    }
    w = WeatherWidget(entity="weather.home", label="Home", state_cache=sc)
    w._forecast = []
    result = w.render()
    assert "20°" in result
    assert "12°" in result

def test_weather_widget_forecast_invalid_datetime():
    sc = {
        "weather.home": {
            "state": "cloudy",
            "attributes": {
                "temperature": 18,
                "forecast": [
                    {"datetime": "not-a-date", "temperature": 20, "condition": "sunny"},
                    {"datetime": "", "temperature": 15, "condition": "cloudy"},
                ],
            },
        }
    }
    w = WeatherWidget(entity="weather.home", label="Home", state_cache=sc)
    w._forecast = []
    result = w.render()
    assert "not" in result   # dt[:3] for "not-a-date"
    assert "—" in result     # empty dt → "—"

def test_weather_widget_unknown_condition():
    sc = {"weather.home": {"state": "hailstorm", "attributes": {"temperature": 5}}}
    w = WeatherWidget(entity="weather.home", label="Home", state_cache=sc)
    assert "◌" in w.render()


async def test_weather_refresh_no_ha():
    w = WeatherWidget(entity="weather.home", label="Home", ha=None, state_cache={})
    await w._refresh_forecast()
    assert w._forecast == []


async def test_weather_refresh_dict_response():
    mock_ha = AsyncMock()
    mock_ha.call_service.return_value = {
        "weather.home": {"forecasts": [{"datetime": "2026-07-21", "temperature": 20}]}
    }
    w = WeatherWidget(entity="weather.home", label="Home", ha=mock_ha, state_cache={})
    with patch.object(w, "refresh"):
        await w._refresh_forecast()
    assert len(w._forecast) == 1


async def test_weather_refresh_list_response():
    mock_ha = AsyncMock()
    mock_ha.call_service.return_value = [{"forecasts": [{"datetime": "2026-07-22", "temperature": 18}]}]
    w = WeatherWidget(entity="weather.home", label="Home", ha=mock_ha, state_cache={})
    with patch.object(w, "refresh"):
        await w._refresh_forecast()
    assert len(w._forecast) == 1


async def test_weather_refresh_empty_dict():
    mock_ha = AsyncMock()
    mock_ha.call_service.return_value = {}  # dict but entity key missing
    w = WeatherWidget(entity="weather.home", label="Home", ha=mock_ha, state_cache={})
    await w._refresh_forecast()
    assert w._forecast == []


async def test_weather_refresh_exception():
    mock_ha = AsyncMock()
    mock_ha.call_service.side_effect = Exception("network error")
    w = WeatherWidget(entity="weather.home", label="Home", ha=mock_ha, state_cache={})
    await w._refresh_forecast()  # should not raise
    assert w._forecast == []


# ── make_widget factory ───────────────────────────────────────────────────────

@pytest.mark.parametrize("cfg,expected_type", [
    ({"type": "value", "entity": "sensor.x"}, ValueWidget),
    ({"type": "binary", "entity": "binary_sensor.x"}, BinaryWidget),
    ({"type": "sparkline", "entity": "sensor.x"}, SparklineWidget),
    ({"type": "value_sparkline", "entity": "sensor.x"}, ValueSparklineWidget),
    ({"type": "toggle", "entity": "light.x"}, ToggleWidget),
    ({"type": "action", "label": "X", "service": "s/v"}, ActionWidget),
    ({"type": "heading", "text": "Title"}, HeadingWidget),
    ({"type": "climate", "entity": "climate.x"}, ClimateWidget),
    ({"type": "weather", "entity": "weather.x"}, WeatherWidget),
    ({"type": "spotify", "entity": "media_player.x"}, SpotifyWidget),
])
def test_make_widget_returns_correct_type(cfg, expected_type):
    widget = make_widget(cfg, {}, {}, None)
    assert isinstance(widget, expected_type)

def test_make_widget_unknown_type_returns_static():
    widget = make_widget({"type": "does_not_exist"}, {}, {}, None)
    assert isinstance(widget, Static)

def test_make_widget_label_default_to_entity():
    w = make_widget({"type": "value", "entity": "sensor.temp"}, {}, {}, None)
    assert w.label == "sensor.temp"

def test_make_widget_explicit_label():
    w = make_widget({"type": "value", "entity": "sensor.temp", "label": "Temperatura"}, {}, {}, None)
    assert w.label == "Temperatura"

def test_make_widget_value_sparkline_defaults():
    w = make_widget({"type": "value_sparkline", "entity": "sensor.x"}, {}, {}, None)
    assert w.window == 60
    assert w.fmt == ".1f"
