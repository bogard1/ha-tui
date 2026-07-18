import os, json, ssl, sys, asyncio
import aiohttp, websockets, yaml
from dotenv import load_dotenv
from textual.app import App
from textual.widgets import Static, Header, Footer
from textual.containers import Grid, VerticalScroll

load_dotenv()


def load_config(path="dashboard.yml"):
    with open(path, "r") as f:
        raw = os.path.expandvars(f.read())
    return yaml.safe_load(raw)


# -------- HA Client --------
class HAClient:
    def __init__(self, url, token, verify_ssl=True):
        self.base_url = url.rstrip("/")
        if self.base_url.startswith("https://"):
            self.ws_url = "wss://" + self.base_url[8:] + "/api/websocket"
        else:
            self.ws_url = "ws://" + self.base_url[7:] + "/api/websocket"
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = None
        self.state_cache = {}
        self.history = {}
        self._ws = None

    def _ssl_ctx(self):
        if not self.verify_ssl:
            ctx = ssl.SSLContext()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        return None

    async def connect_ws(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        ssl_ctx = self._ssl_ctx() if self.base_url.startswith("https") else None
        self._ws = await websockets.connect(self.ws_url, ssl=ssl_ctx)
        msg = json.loads(await self._ws.recv())
        if msg["type"] != "auth_required":
            raise RuntimeError(f"Expected auth_required, got: {msg['type']}")
        await self._ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        msg = json.loads(await self._ws.recv())
        if msg["type"] != "auth_ok":
            raise RuntimeError(f"Autenticación fallida: {msg.get('message', msg['type'])}")
        await self._ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))

    async def initial_states(self):
        async with self.session.get(
            f"{self.base_url}/api/states",
            headers={"Authorization": f"Bearer {self.token}"},
            ssl=self._ssl_ctx()
        ) as r:
            r.raise_for_status()
            for st in await r.json():
                self.state_cache[st["entity_id"]] = st
                try:
                    v = float(st.get("state"))
                    self.history.setdefault(st["entity_id"], []).append(v)
                except (ValueError, TypeError):
                    pass

    async def pump(self):
        backoff = 1
        while True:
            try:
                async for raw in self._ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "event" and msg["event"].get("event_type") == "state_changed":
                        new_state = msg["event"]["data"].get("new_state")
                        if new_state:
                            ent = new_state["entity_id"]
                            self.state_cache[ent] = new_state
                            try:
                                v = float(new_state.get("state"))
                                hist = self.history.setdefault(ent, [])
                                hist.append(v)
                                if len(hist) > 600:
                                    self.history[ent] = hist[-600:]
                            except (ValueError, TypeError):
                                pass
                backoff = 1
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            try:
                await self.connect_ws()
            except Exception:
                pass

    async def call_service(self, service: str, payload: dict):
        domain, srv = service.split("/")
        async with self.session.post(
            f"{self.base_url}/api/services/{domain}/{srv}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json=payload,
            ssl=self._ssl_ctx()
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self.session:
            await self.session.close()


# -------- Widgets --------
_ON_STATES = {"on", "open", "detected", "home", "true"}
_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(data, window, cols=36):
    data = data[-window:]
    if not data:
        return "─" * cols
    mn, mx = min(data), max(data)
    rng = (mx - mn) or 1.0
    step = max(1, len(data) // cols)
    return "".join(_SPARK_BLOCKS[min(7, int((x - mn) / rng * 7))] for x in data[::step][:cols])


class ValueWidget(Static):
    def __init__(self, entity, label, unit="", fmt=".2f", state_cache=None, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.unit = unit
        self.fmt = fmt
        self.state_cache = state_cache

    def render(self):
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"{self.label}\n—"
        val = st.get("state", "")
        try:
            val = format(float(val), self.fmt)
        except (ValueError, TypeError):
            pass
        return f"{self.label}\n[b]{val}{self.unit}[/b]"


class BinaryWidget(Static):
    def __init__(self, entity, label, on_text="ON", off_text="off", state_cache=None, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.on_text = on_text
        self.off_text = off_text
        self.state_cache = state_cache

    def render(self):
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"{self.label}\n—"
        text = self.on_text if st.get("state") in _ON_STATES else self.off_text
        return f"{self.label}\n[b]{text}[/b]"


class SparklineWidget(Static):
    def __init__(self, entity, label, window=60, history=None, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.window = window
        self.history = history

    def render(self):
        data = self.history.get(self.entity, []) if self.history else []
        return f"{self.label}\n{_sparkline(data, self.window)}"


class ValueSparklineWidget(Static):
    def __init__(self, entity, label, unit="", fmt=".1f", window=60,
                 state_cache=None, history=None, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.unit = unit
        self.fmt = fmt
        self.window = window
        self.state_cache = state_cache
        self.history = history

    def render(self):
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
    def __init__(self, entity, label, on_text="ON", off_text="off",
                 toggle_service="homeassistant/toggle", state_cache=None, ha=None, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.label = label
        self.on_text = on_text
        self.off_text = off_text
        self.toggle_service = toggle_service
        self.state_cache = state_cache
        self.ha = ha

    async def on_click(self):
        if not self.ha or not self.entity:
            return
        try:
            await self.ha.call_service(self.toggle_service, {"entity_id": self.entity})
        except Exception:
            pass

    def render(self):
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"[dim]{self.label}[/dim]\n—"
        is_on = st.get("state") in _ON_STATES
        icon = "●" if is_on else "○"
        text = self.on_text if is_on else self.off_text
        state = f"[bold yellow]{icon}  {text}[/bold yellow]" if is_on else f"[dim]{icon}  {text}[/dim]"
        return f"{self.label}\n{state}"


class HeadingWidget(Static):
    def __init__(self, text, **kwargs):
        super().__init__(f"[bold]{text}[/bold]", **kwargs)


class ActionWidget(Static):
    def __init__(self, label, service, data=None, ha=None, **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self.service = service
        self.data = data or {}
        self.ha = ha
        self._status = ""

    async def on_click(self):
        self._status = "Ejecutando…"
        self.refresh()
        try:
            await self.ha.call_service(self.service, self.data)
            self._status = "✓"
        except Exception as e:
            self._status = f"Error: {e}"
        self.refresh()

    def render(self):
        status = f"\n[dim]{self._status}[/dim]" if self._status else ""
        return f"[b]{self._label}[/b]{status}"


# -------- App --------
class HADashboard(App):
    CSS = """
    Screen { layout: vertical; }
    Header { dock: top; height: 5; }
    Footer { dock: bottom; height: 1; }
    #page { height: 1fr; margin: 1 0; }
    .grid-1 { grid-size: 1; }
    .grid-2 { grid-size: 2; }
    .grid-3 { grid-size: 3; }
    .grid-4 { grid-size: 4; }
    .rows { grid-size: 1; }
    Grid { grid-gutter: 1; padding: 1 1 0 1; }
    Static { border: round; padding: 1; }
    ValueSparklineWidget { height: 8; }
    ToggleWidget { height: 7; text-align: center; }
    HeadingWidget { column-span: 4; border: none; height: 3; background: $background; padding: 0 1; }
    .section-heading { border: none; height: 3; background: $background; padding: 0 2; }
    .error { border: round; color: $error; margin: 2 4; height: auto; }
    """
    BINDINGS = [
        ("right", "next_page", "→"),
        ("left", "prev_page", "←"),
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "reload_cfg", "Reload"),
        ("q", "quit", "Salir"),
    ]

    def __init__(self, cfg, config_path="dashboard.yml"):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.page_idx = 0
        self.ha = HAClient(
            url=cfg["ha"]["url"],
            token=cfg["ha"]["token"],
            verify_ssl=cfg["ha"].get("verify_ssl", True),
        )
        kb = cfg.get("keybinds", {})
        if kb:
            self.BINDINGS = [
                (kb.get("next_page", "right"), "next_page", "→"),
                (kb.get("prev_page", "left"), "prev_page", "←"),
                (kb.get("reload_config", "r"), "reload_cfg", "Reload"),
                (kb.get("quit", "q"), "quit", "Salir"),
            ]

    async def on_mount(self):
        self.page_container = VerticalScroll(id="page")
        await self.mount(Header(show_clock=True))
        await self.mount(Footer())
        await self.mount(self.page_container)
        try:
            await self.ha.connect_ws()
            await self.ha.initial_states()
        except Exception as e:
            await self.page_container.mount(
                Static(f"[bold]Error conectando a Home Assistant[/bold]\n{e}", classes="error")
            )
            return
        self.run_worker(self.ha.pump(), exclusive=True)
        self.set_interval(self.cfg["ui"].get("refresh_ms", 250) / 1000.0, self.refresh)
        await self.build_page()

    def _make_widget(self, w):
        t = w["type"]
        sc, hist, ha = self.ha.state_cache, self.ha.history, self.ha
        if t == "value":
            return ValueWidget(
                entity=w["entity"], label=w.get("label", w["entity"]),
                unit=w.get("unit", ""), fmt=w.get("fmt", ".2f"), state_cache=sc
            )
        elif t == "binary":
            return BinaryWidget(
                entity=w["entity"], label=w.get("label", w["entity"]),
                on_text=w.get("on_text", "ON"), off_text=w.get("off_text", "off"), state_cache=sc
            )
        elif t == "sparkline":
            return SparklineWidget(
                entity=w["entity"], label=w.get("label", w["entity"]),
                window=int(w.get("window", 60)), history=hist
            )
        elif t == "value_sparkline":
            return ValueSparklineWidget(
                entity=w["entity"], label=w.get("label", w["entity"]),
                unit=w.get("unit", ""), fmt=w.get("fmt", ".1f"),
                window=int(w.get("window", 60)), state_cache=sc, history=hist
            )
        elif t == "toggle":
            return ToggleWidget(
                entity=w["entity"], label=w.get("label", w["entity"]),
                on_text=w.get("on_text", "ON"), off_text=w.get("off_text", "off"),
                toggle_service=w.get("toggle_service", "homeassistant/toggle"),
                state_cache=sc, ha=ha
            )
        elif t == "action":
            return ActionWidget(
                label=w["label"], service=w["service"],
                data=w.get("data", {}), ha=ha
            )
        elif t == "heading":
            return HeadingWidget(w.get("text", ""))
        else:
            return Static(f"Widget '{t}' no soportado")

    async def build_page(self):
        await self.page_container.remove_children()
        page = self.cfg["pages"][self.page_idx]

        if "sections" in page:
            for section in page["sections"]:
                if "title" in section:
                    await self.page_container.mount(
                        Static(f"[bold]{section['title']}[/bold]", classes="section-heading")
                    )
                grid = Grid(classes=section.get("layout", "grid-2"))
                await self.page_container.mount(grid)
                for w in section.get("widgets", []):
                    await grid.mount(self._make_widget(w))
        else:
            grid = Grid(classes=page.get("layout", "grid-2"))
            await self.page_container.mount(grid)
            for w in page.get("widgets", []):
                await grid.mount(self._make_widget(w))

        self.title = f"HA TUI · {page.get('title', page.get('id'))}  ({self.page_idx + 1}/{len(self.cfg['pages'])})"

    def action_next_page(self):
        self.page_idx = (self.page_idx + 1) % len(self.cfg["pages"])
        self.run_worker(self.build_page())

    def action_prev_page(self):
        self.page_idx = (self.page_idx - 1) % len(self.cfg["pages"])
        self.run_worker(self.build_page())

    def action_reload_cfg(self):
        self.cfg = load_config(self.config_path)
        self.run_worker(self.build_page())

    def action_quit(self):
        self.exit()

    async def on_unmount(self):
        await self.ha.close()


if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "dashboard.yml"
    cfg = load_config(config_file)
    asyncio.run(HADashboard(cfg, config_file).run_async())
