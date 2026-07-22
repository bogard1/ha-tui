import pytest
from widgets import (
    ValueWidget, BinaryWidget, SparklineWidget, ValueSparklineWidget,
    ToggleWidget, HeadingWidget, ActionWidget, WeatherWidget,
    make_widget, _sparkline,
)
from textual.widgets import Static


# ── _sparkline ──────────────────────────────────────────────────────────────

def test_sparkline_empty_data():
    result = _sparkline([], 60)
    assert result == "─" * 36

def test_sparkline_respects_window():
    data = list(range(100))
    assert _sparkline(data, 10) == _sparkline(data[-10:], 10)

def test_sparkline_uniform_data():
    result = _sparkline([5.0] * 20, 60)
    assert len(set(result)) == 1

def test_sparkline_length():
    result = _sparkline(list(range(200)), 200)
    assert len(result) <= 36


# ── ValueWidget ──────────────────────────────────────────────────────────────

def test_value_widget_missing_entity():
    w = ValueWidget(entity="sensor.x", label="X", state_cache={})
    result = w.render()
    assert "X" in result
    assert "—" in result

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


# ── BinaryWidget ─────────────────────────────────────────────────────────────

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
    result = w.render()
    assert "X" in result
    assert "─" in result

def test_sparkline_widget_with_history():
    hist = {"sensor.x": [1.0, 2.0, 3.0, 4.0, 5.0]}
    w = SparklineWidget(entity="sensor.x", label="X", window=60, history=hist)
    result = w.render()
    assert "X" in result
    assert "─" not in result


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


# ── ActionWidget ──────────────────────────────────────────────────────────────

def test_action_widget_shows_label():
    w = ActionWidget(label="Activar alarma", service="alarm/arm")
    assert "Activar alarma" in w.render()

def test_action_widget_no_status_initially():
    w = ActionWidget(label="X", service="s/v")
    result = w.render()
    assert "Ejecutando" not in result


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
    w._forecast = []  # force use of attrs forecast
    result = w.render()
    assert "20°" in result
    assert "12°" in result

def test_weather_widget_unknown_condition():
    sc = {"weather.home": {"state": "hailstorm", "attributes": {"temperature": 5}}}
    w = WeatherWidget(entity="weather.home", label="Home", state_cache=sc)
    result = w.render()
    assert "◌" in result


# ── make_widget factory ───────────────────────────────────────────────────────

@pytest.mark.parametrize("cfg,expected_type", [
    ({"type": "value", "entity": "sensor.x"}, ValueWidget),
    ({"type": "binary", "entity": "binary_sensor.x"}, BinaryWidget),
    ({"type": "sparkline", "entity": "sensor.x"}, SparklineWidget),
    ({"type": "value_sparkline", "entity": "sensor.x"}, ValueSparklineWidget),
    ({"type": "toggle", "entity": "light.x"}, ToggleWidget),
    ({"type": "action", "label": "X", "service": "s/v"}, ActionWidget),
    ({"type": "heading", "text": "Title"}, HeadingWidget),
    ({"type": "weather", "entity": "weather.x"}, WeatherWidget),
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
