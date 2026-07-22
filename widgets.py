import datetime
from typing import Any
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Button
from textual.containers import Horizontal

_ON_STATES: set[str] = {"on", "open", "detected", "home", "true"}
_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
_WX_ICONS: dict[str, str] = {
    "sunny": "☀", "clear-night": "🌙", "cloudy": "☁",
    "partlycloudy": "⛅", "rainy": "🌧", "pouring": "🌧",
    "snowy": "❄", "snowy-rainy": "🌨", "fog": "🌫",
    "windy": "💨", "windy-variant": "💨",
    "lightning": "⚡", "lightning-rainy": "⛈",
    "hail": "🌨", "exceptional": "⚠",
}
_HVAC_ICONS: dict[str, str] = {
    "heat": "🔥", "cool": "❄", "heat_cool": "♻",
    "auto": "♻", "dry": "💧", "fan_only": "💨", "off": "○",
}


def _sparkline(data: list[float], window: int, cols: int = 36) -> str:
    data = data[-window:]
    if not data:
        return "─" * cols
    mn, mx = min(data), max(data)
    rng = (mx - mn) or 1.0
    step = max(1, len(data) // cols)
    return "".join(_SPARK_BLOCKS[min(7, int((x - mn) / rng * 7))] for x in data[::step][:cols])


class ValueWidget(Static):
    def __init__(self, entity: str, label: str, unit: str = "", fmt: str = ".2f",
                 state_cache: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.unit = unit
        self.fmt = fmt
        self.state_cache = state_cache

    def render(self) -> str:
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"{self.label}\n—"
        val: Any = st.get("state", "")
        try:
            val = format(float(val), self.fmt)
        except (ValueError, TypeError):
            pass
        return f"{self.label}\n[b]{val}{self.unit}[/b]"


class BinaryWidget(Static):
    def __init__(self, entity: str, label: str, on_text: str = "ON", off_text: str = "off",
                 state_cache: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.on_text = on_text
        self.off_text = off_text
        self.state_cache = state_cache

    def render(self) -> str:
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"{self.label}\n—"
        text = self.on_text if st.get("state") in _ON_STATES else self.off_text
        return f"{self.label}\n[b]{text}[/b]"


class SparklineWidget(Static):
    def __init__(self, entity: str, label: str, window: int = 60,
                 history: dict[str, list[float]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.window = window
        self.history = history

    def render(self) -> str:
        data = self.history.get(self.entity, []) if self.history else []
        return f"{self.label}\n{_sparkline(data, self.window)}"


class ValueSparklineWidget(Static):
    DEFAULT_CSS = "ValueSparklineWidget { height: 8; }"

    def __init__(self, entity: str, label: str, unit: str = "", fmt: str = ".1f",
                 window: int = 60, state_cache: dict[str, Any] | None = None,
                 history: dict[str, list[float]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.unit = unit
        self.fmt = fmt
        self.window = window
        self.state_cache = state_cache
        self.history = history

    def render(self) -> str:
        st = self.state_cache.get(self.entity) if self.state_cache else None
        val = "—"
        if st:
            try:
                val = format(float(st.get("state", "")), self.fmt) + self.unit
            except (ValueError, TypeError):
                val = st.get("state", "—")
        data = self.history.get(self.entity, []) if self.history else []
        return f"[dim]{self.label}[/dim]\n[bold]{val}[/bold]\n[yellow]{_sparkline(data, self.window)}[/yellow]"


class ToggleWidget(Static):
    def __init__(self, entity: str, label: str, on_text: str = "ON", off_text: str = "off",
                 toggle_service: str = "homeassistant/toggle",
                 state_cache: dict[str, Any] | None = None, ha: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.on_text = on_text
        self.off_text = off_text
        self.toggle_service = toggle_service
        self.state_cache = state_cache
        self.ha = ha

    async def on_click(self) -> None:
        if not self.ha or not self.entity:
            return
        try:
            await self.ha.call_service(self.toggle_service, {"entity_id": self.entity})
        except Exception:
            pass

    def render(self) -> str:
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"[dim]{self.label}[/dim]\n—"
        is_on = st.get("state") in _ON_STATES
        icon = "●" if is_on else "○"
        text = self.on_text if is_on else self.off_text
        state = f"[bold yellow]{icon}  {text}[/bold yellow]" if is_on else f"[dim]{icon}  {text}[/dim]"
        return f"{self.label}\n{state}"


class HeadingWidget(Static):
    def __init__(self, text: str, **kwargs: Any) -> None:
        super().__init__(f"[bold]{text}[/bold]", **kwargs)


class ActionWidget(Static):
    def __init__(self, label: str, service: str, data: dict[str, Any] | None = None,
                 ha: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._label = label
        self.service = service
        self.data = data or {}
        self.ha = ha
        self._status = ""

    async def on_click(self) -> None:
        self._status = "Ejecutando…"
        self.refresh()
        try:
            await self.ha.call_service(self.service, self.data)
            self._status = "✓"
        except Exception as e:
            self._status = f"Error: {e}"
        self.refresh()

    def render(self) -> str:
        status = f"\n[dim]{self._status}[/dim]" if self._status else ""
        return f"[b]{self._label}[/b]{status}"


class ClimateWidget(Static):
    def __init__(self, entity: str, label: str, unit: str = "°C",
                 state_cache: dict[str, Any] | None = None, ha: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.unit = unit
        self.state_cache = state_cache
        self.ha = ha

    def render(self) -> str:
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"[dim]{self.label}[/dim]\n—"
        attrs = st.get("attributes", {})
        mode = st.get("state", "off")
        current = attrs.get("current_temperature")
        target = attrs.get("temperature")
        icon = _HVAC_ICONS.get(mode, "◌")
        current_str = f"{current}{self.unit}" if current is not None else "—"
        target_str = f"{target}{self.unit}" if target is not None else "—"
        return (
            f"[dim]{self.label}[/dim]\n"
            f"[bold]{current_str}[/bold]  →  [yellow]{target_str}[/yellow]\n"
            f"{icon}  [dim]{mode}[/dim]"
        )


class WeatherWidget(Static):
    def __init__(self, entity: str, label: str, unit: str = "°C",
                 state_cache: dict[str, Any] | None = None, ha: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity = entity
        self._label = label
        self._unit = unit
        self._state_cache = state_cache
        self._ha = ha
        self._forecast: list[dict[str, Any]] = []

    def on_mount(self) -> None:
        self.run_worker(self._refresh_forecast(), exclusive=False)
        self.set_interval(1800, lambda: self.run_worker(self._refresh_forecast(), exclusive=False))

    async def _refresh_forecast(self) -> None:
        if not self._ha:
            return
        try:
            data = await self._ha.call_service(
                "weather/get_forecasts",
                {"entity_id": self._entity, "type": "daily"},
            )
            if isinstance(data, dict):
                self._forecast = data.get(self._entity, {}).get("forecasts", [])
            elif isinstance(data, list) and data:
                self._forecast = data[0].get("forecasts", [])
            if self._forecast:
                self.refresh()
        except Exception:
            pass

    def render(self) -> str:
        state_data = self._state_cache.get(self._entity) if self._state_cache else None
        if not isinstance(state_data, dict):
            return f"{self._label}\n[dim]No disponible[/dim]"

        condition = state_data.get("state", "unknown")
        attrs = state_data.get("attributes", {})
        temp = attrs.get("temperature", "—")
        humidity = attrs.get("humidity")
        wind = attrs.get("wind_speed")
        wind_unit = attrs.get("wind_speed_unit", "")

        icon = _WX_ICONS.get(condition, "◌")
        condition_text = condition.replace("-", " ").title()

        lines = [
            f"{icon}  [bold]{self._label}[/bold]",
            f"[bold]{temp}{self._unit}[/bold]  [dim]{condition_text}[/dim]",
        ]

        extras = []
        if humidity is not None:
            extras.append(f"💧 {humidity}%")
        if wind is not None:
            extras.append(f"💨 {wind}{' ' + wind_unit if wind_unit else ''}")
        if extras:
            lines.append("  ".join(extras))

        forecast = self._forecast or attrs.get("forecast", [])
        if forecast:
            lines.append("[dim]─────────────────[/dim]")
            for f in forecast[:4]:
                dt = f.get("datetime", "")
                high = f.get("temperature", "—")
                low = f.get("templow", "")
                cond = f.get("condition", "")
                ficon = _WX_ICONS.get(cond, "")
                try:
                    day = datetime.datetime.fromisoformat(dt).strftime("%a")
                except Exception:
                    day = dt[:3] if dt else "—"
                temp_str = f"{high}°" + (f"/{low}°" if low != "" else "")
                lines.append(f"[dim]{day}[/dim]  {temp_str}  {ficon}")

        return "\n".join(lines)


class SpotifyWidget(Widget):
    def __init__(self, entity: str, label: str, ha: Any,
                 state_cache: dict[str, Any], history: dict[str, list[float]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity = entity
        self._label = label
        self._ha = ha
        self._state_cache = state_cache
        self._history = history

    def compose(self) -> ComposeResult:
        yield Static("", id="sp-info")
        with Horizontal(id="sp-controls"):
            yield Button("⏮", id="sp-prev", classes="sp-btn")
            yield Button("▶", id="sp-play", classes="sp-btn")
            yield Button("⏭", id="sp-next", classes="sp-btn")

    def on_mount(self) -> None:
        self.set_interval(0.25, self._tick)

    def _tick(self) -> None:
        state_data = self._state_cache.get(self._entity)
        if not isinstance(state_data, dict):
            self.query_one("#sp-info", Static).update(f"[dim]{self._label}\nNo disponible[/dim]")
            return

        state = state_data.get("state", "unknown")
        attrs = state_data.get("attributes", {})
        title = attrs.get("media_title", "")
        artist = attrs.get("media_artist", "")
        position = attrs.get("media_position") or 0
        duration = attrs.get("media_duration") or 0

        lines = [f"[bold]{self._label}[/bold]"]
        if state in ("playing", "paused"):
            if title:
                lines.append(f"[b]{title}[/b]")
            if artist:
                lines.append(f"[dim]{artist}[/dim]")
        else:
            lines.append(f"[dim]{state}[/dim]")

        if duration > 0:
            pct = min(1.0, position / duration)
            bar_width = 26
            filled = int(pct * bar_width)
            lines.append(f"[dim]{'█' * filled}{'░' * (bar_width - filled)}[/dim]")

        self.query_one("#sp-info", Static).update("\n".join(lines))
        play_btn = self.query_one("#sp-play", Button)
        play_btn.label = "⏸" if state == "playing" else "▶"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        try:
            if btn_id == "sp-prev":
                await self._ha.call_service("media_player/media_previous_track",
                                             {"entity_id": self._entity})
            elif btn_id == "sp-play":
                await self._ha.call_service("media_player/media_play_pause",
                                             {"entity_id": self._entity})
            elif btn_id == "sp-next":
                await self._ha.call_service("media_player/media_next_track",
                                             {"entity_id": self._entity})
        except Exception:
            pass


def make_widget(w: dict[str, Any], state_cache: dict[str, Any],
                history: dict[str, list[float]], ha: Any) -> Widget:
    t = w["type"]
    sc, hist = state_cache, history
    if t == "value":
        return ValueWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            unit=w.get("unit", ""), fmt=w.get("fmt", ".2f"), state_cache=sc,
        )
    elif t == "binary":
        return BinaryWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            on_text=w.get("on_text", "ON"), off_text=w.get("off_text", "off"), state_cache=sc,
        )
    elif t == "sparkline":
        return SparklineWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            window=int(w.get("window", 60)), history=hist,
        )
    elif t == "value_sparkline":
        return ValueSparklineWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            unit=w.get("unit", ""), fmt=w.get("fmt", ".1f"),
            window=int(w.get("window", 60)), state_cache=sc, history=hist,
        )
    elif t == "toggle":
        return ToggleWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            on_text=w.get("on_text", "ON"), off_text=w.get("off_text", "off"),
            toggle_service=w.get("toggle_service", "homeassistant/toggle"),
            state_cache=sc, ha=ha,
        )
    elif t == "action":
        return ActionWidget(
            label=w["label"], service=w["service"],
            data=w.get("data", {}), ha=ha,
        )
    elif t == "heading":
        return HeadingWidget(w.get("text", ""))
    elif t == "climate":
        return ClimateWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            unit=w.get("unit", "°C"), state_cache=sc, ha=ha,
        )
    elif t == "weather":
        return WeatherWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            unit=w.get("unit", "°C"), state_cache=sc, ha=ha,
        )
    elif t == "spotify":
        return SpotifyWidget(
            entity=w["entity"], label=w.get("label", w["entity"]),
            ha=ha, state_cache=sc, history=hist,
        )
    else:
        return Static(f"Widget '{t}' no soportado")
