# app.py
import os, asyncio, json, time, ssl, math, sys
import aiohttp, websockets, yaml
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer
from textual.containers import Grid, VerticalScroll
from textual.reactive import reactive

# Load environment variables from .env file
load_dotenv()

# -------- Config --------
def load_config(path="dashboard.yml"):
    with open(path, "r") as f:
        raw = os.path.expandvars(f.read())
    return yaml.safe_load(raw)

# -------- HA Client --------
class HAClient:
    def __init__(self, url, token, verify_ssl=True):
        self.base_url = url.rstrip("/")
        self.ws_url = self.base_url.replace("http", "ws") + "/api/websocket"
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = None
        self.state_cache = {}        # entity_id -> state dict
        self.history = {}            # entity_id -> [float]
        self._ws = None

    async def connect_ws(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        ssl_ctx = None
        if self.base_url.startswith("https") and not self.verify_ssl:
            ssl_ctx = ssl.SSLContext()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        self._ws = await websockets.connect(self.ws_url, ssl=ssl_ctx)
        # Hello
        msg = json.loads(await self._ws.recv())
        assert msg["type"] == "auth_required"
        await self._ws.send(json.dumps({"type":"auth","access_token": self.token}))
        msg = json.loads(await self._ws.recv())
        assert msg["type"] == "auth_ok"
        # Subscribe to state_changed
        await self._ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))

    async def initial_states(self):
        # REST GET /api/states
        async with self.session.get(
            f"{self.base_url}/api/states",
            headers={"Authorization": f"Bearer {self.token}"},
            ssl=False if not self.verify_ssl else None
        ) as r:
            r.raise_for_status()
            data = await r.json()
            temp_sensors = []
            for st in data:
                self.state_cache[st["entity_id"]] = st
                # Initialize history for temperature sensors
                if "temperature" in st["entity_id"]:
                    temp_sensors.append(f"{st['entity_id']}: {st['state']}")
                    try:
                        v = float(st.get("state"))
                        self.history.setdefault(st["entity_id"], []).append(v)
                    except Exception:
                        pass

    async def pump(self):
        # receive events
        while True:
            msg = json.loads(await self._ws.recv())
            if msg.get("type") == "event" and msg["event"].get("event_type") == "state_changed":
                data = msg["event"]["data"]
                new_state = data.get("new_state")
                if new_state:
                    ent = new_state["entity_id"]
                    self.state_cache[ent] = new_state
                    # keep history for sparkline
                    try:
                        v = float(new_state.get("state"))
                        self.history.setdefault(ent, []).append(v)
                        # limit window to 600 samples
                        if len(self.history[ent]) > 600:
                            self.history[ent] = self.history[ent][-600:]
                    except Exception:
                        pass

    async def call_service(self, service: str, payload: dict):
        # service: "domain/service"
        domain, srv = service.split("/")
        async with self.session.post(
            f"{self.base_url}/api/services/{domain}/{srv}",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type":"application/json"},
            json=payload,
            ssl=False if not self.verify_ssl else None
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self.session:
            await self.session.close()

# -------- Widgets --------
class ValueWidget(Static):
    entity = reactive("")
    label = reactive("")
    unit = reactive("")
    fmt = reactive(".2f")
    state_cache = None

    def render(self):
        st = self.state_cache.get(self.entity) if self.state_cache else None
        if not st:
            return f"{self.label}\n—"
        val = st.get("state", "")
        try:
            val = format(float(val), self.fmt)
        except Exception as e:
            val = f"Error: {val}"
        return f"{self.label}\n[b]{val}{self.unit}[/b]"

class BinaryWidget(Static):
    entity = reactive("")
    label = reactive("")
    on_text = reactive("ON")
    off_text = reactive("off")
    state_cache = None

    def render(self):
        st = self.state_cache.get(self.entity)
        if not st:
            return f"{self.label}\n—"
        v = st.get("state")
        text = self.on_text if v in ("on", "open", "detected") else self.off_text
        return f"{self.label}\n[b]{text}[/b]"

class SparklineWidget(Static):
    entity = reactive("")
    label = reactive("")
    window = reactive(60)
    history = None

    def render(self):
        data = (self.history.get(self.entity) or [])[-self.window:] if self.history else []
        if not data:
            return f"{self.label}\n—"
        # simple sparkline ascii
        mn, mx = min(data), max(data)
        rng = (mx - mn) or 1.0
        cols = 40
        step = max(1, len(data)//cols)
        buckets = data[::step][:cols]
        blocks = "▁▂▃▄▅▆▇█"
        s = "".join(blocks[min(7,int((x - mn)/rng*7))] for x in buckets)
        return f"{self.label}\n{s}"

class ActionWidget(Static):
    label = reactive("")
    service = reactive("")
    data = reactive({})
    ha: HAClient = None
    last = ""

    async def on_click(self) -> None:
        self.last = "Ejecutando…"
        self.update(self.render())
        try:
            await self.ha.call_service(self.service, self.data)
            self.last = "OK"
        except Exception as e:
            self.last = f"Error: {e}"
        self.update(self.render())

    def render(self):
        return f"[ACTION] {self.label}\n{self.last}"

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
    .rows { grid-size: 1; }
    Grid { grid-gutter: 1; padding: 1; }
    Static { border: round; padding: 1; }
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
        # Override bindings if custom keybinds are configured
        kb = cfg.get("keybinds", {})
        if kb:
            self.BINDINGS = [
                (kb.get("next_page","right"), "next_page", "→"),
                (kb.get("prev_page","left"), "prev_page", "←"),
                (kb.get("reload_config","r"), "reload_cfg", "Reload"),
                (kb.get("quit","q"), "quit", "Salir"),
            ]

    async def on_mount(self):
        await self.push_screen_ui()
        # HA connections
        await self.ha.connect_ws()
        await self.ha.initial_states()
        self.run_worker(self.ha.pump(), exclusive=True)
        # refresco UI
        self.set_interval(self.cfg["ui"].get("refresh_ms", 250)/1000.0, self.refresh)

    async def push_screen_ui(self):
        self.page_container = VerticalScroll(id="page")
        await self.mount(Header(show_clock=True))
        await self.mount(Footer())
        await self.mount(self.page_container)
        await self.build_page()

    async def build_page(self):
        await self.page_container.remove_children()
        pages = self.cfg["pages"]
        page = pages[self.page_idx]
        grid = Grid(classes=page.get("layout","grid-2"))
        await self.page_container.mount(grid)
        for w in page["widgets"]:
            t = w["type"]
            if t == "value":
                wid = ValueWidget()
                wid.entity = w["entity"]; wid.label=w.get("label",w["entity"])
                wid.unit = w.get("unit",""); wid.fmt = w.get("fmt",".2f")
                wid.state_cache = self.ha.state_cache
                await grid.mount(wid)
            elif t == "binary":
                wid = BinaryWidget()
                wid.entity = w["entity"]; wid.label=w.get("label",w["entity"])
                wid.on_text = w.get("on_text","ON"); wid.off_text = w.get("off_text","off")
                wid.state_cache = self.ha.state_cache
                await grid.mount(wid)
            elif t == "sparkline":
                wid = SparklineWidget()
                wid.entity = w["entity"]; wid.label=w.get("label",w["entity"])
                wid.window = int(w.get("window",60))
                wid.history = self.ha.history
                await grid.mount(wid)
            elif t == "action":
                wid = ActionWidget()
                wid.label = w["label"]; wid.service = w["service"]; wid.data = w.get("data",{})
                wid.ha = self.ha
                await grid.mount(wid)
            else:
                await grid.mount(Static(f"Widget '{t}' no soportado"))

        self.title = f"HA TUI · {page.get('title', page.get('id'))}  ({self.page_idx+1}/{len(self.cfg['pages'])})"

    def action_next_page(self):
        print(f"DEBUG: Next page called, current: {self.page_idx}")
        self.page_idx = (self.page_idx + 1) % len(self.cfg["pages"])
        print(f"DEBUG: Moving to page: {self.page_idx}")
        self.run_worker(self.build_page())

    def action_prev_page(self):
        print(f"DEBUG: Prev page called, current: {self.page_idx}")
        self.page_idx = (self.page_idx - 1) % len(self.cfg["pages"])
        print(f"DEBUG: Moving to page: {self.page_idx}")
        self.run_worker(self.build_page())

    def action_reload_cfg(self):
        # Use same config file that was originally loaded
        self.cfg = load_config(getattr(self, 'config_path', 'dashboard.yml'))
        self.run_worker(self.build_page())

    def action_quit(self):
        self.exit()

    async def on_unmount(self):
        await self.ha.close()

if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "dashboard.yml"
    cfg = load_config(config_file)
    asyncio.run(HADashboard(cfg, config_file).run_async())
