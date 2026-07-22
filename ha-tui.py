import os, sys, asyncio, logging
from typing import Any
import yaml
from dotenv import load_dotenv
from textual.app import App
from textual.widget import Widget
from textual.widgets import Static, Header, Footer
from textual.containers import Grid, VerticalScroll

from ha_client import HAClient
from widgets import make_widget

load_dotenv()

logging.basicConfig(
    filename="ha-tui.log",
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "dashboard.yml") -> dict[str, Any]:
    with open(path, "r") as f:
        raw = os.path.expandvars(f.read())
    return yaml.safe_load(raw)


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
    .grid-5 { grid-size: 5; }
    .rows { grid-size: 1; }
    Grid { height: auto; grid-gutter: 1; padding: 0 1 0 1; }
    Static { border: round; padding: 1; }
    ValueSparklineWidget { height: 8; }
    ToggleWidget { height: 7; text-align: center; }
    ActionWidget { height: 7; text-align: center; }
    ClimateWidget { height: 7; }
    HeadingWidget { column-span: 4; border: none; height: 3; background: $background; padding: 0 1; }
    .section-heading { border: none; height: 1; background: $background; padding: 0 2; margin-top: 1; }
    .error { border: round; color: $error; margin: 2 4; height: auto; }
    WeatherWidget { height: 12; }
    SpotifyWidget { height: 9; padding: 0; border: round; }
    SpotifyWidget #sp-info { border: none; padding: 0 1; height: 1fr; }
    SpotifyWidget #sp-controls { height: 3; }
    SpotifyWidget .sp-btn { width: 1fr; border: none; min-width: 3; }
    """
    BINDINGS = [
        ("right", "next_page", "→"),
        ("left", "prev_page", "←"),
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("r", "reload_cfg", "Reload"),
        ("q", "quit", "Salir"),
    ]

    def __init__(self, cfg: dict[str, Any], config_path: str = "dashboard.yml") -> None:
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.page_idx = 0
        self.ha = HAClient(
            url=cfg["ha"]["url"],
            token=cfg["ha"]["token"],
            verify_ssl=cfg["ha"].get("verify_ssl", True),
        )
        try:
            self._config_mtime = os.path.getmtime(config_path)
        except OSError:
            self._config_mtime = 0.0
        kb = cfg.get("keybinds", {})
        if kb:
            self.BINDINGS = [
                (kb.get("next_page", "right"), "next_page", "→"),
                (kb.get("prev_page", "left"), "prev_page", "←"),
                (kb.get("reload_config", "r"), "reload_cfg", "Reload"),
                (kb.get("quit", "q"), "quit", "Salir"),
            ]

    async def on_mount(self) -> None:
        self.page_container = VerticalScroll(id="page")
        await self.mount(Header(show_clock=True))
        await self.mount(Footer())
        await self.mount(self.page_container)
        try:
            await self.ha.connect_ws()
            await self.ha.initial_states()
        except Exception as e:
            logger.error("Failed to connect to Home Assistant: %s", e)
            await self.page_container.mount(
                Static(f"[bold]Error conectando a Home Assistant[/bold]\n{e}", classes="error")
            )
            return
        self.run_worker(self.ha.pump(), exclusive=True)
        self.ha.on_state_change = self._refresh_page_widgets
        self.set_interval(self.cfg["ui"].get("refresh_ms", 250) / 1000.0, self._update_ui)
        await self.build_page()

    def _refresh_page_widgets(self) -> None:
        for w in self.page_container.query("*"):
            w.refresh()

    def _update_ui(self) -> None:
        self._refresh_page_widgets()
        self.sub_title = "● Conectado" if self.ha.connected else "○ Reconectando…"
        try:
            mtime = os.path.getmtime(self.config_path)
            if mtime != self._config_mtime:
                self._config_mtime = mtime
                logger.info("Config changed, reloading…")
                self.action_reload_cfg()
        except OSError:
            pass

    def _make_widget(self, w: dict[str, Any]) -> Widget:
        return make_widget(w, self.ha.state_cache, self.ha.history, self.ha)

    async def build_page(self) -> None:
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

    def action_next_page(self) -> None:
        self.page_idx = (self.page_idx + 1) % len(self.cfg["pages"])
        self.run_worker(self.build_page())

    def action_prev_page(self) -> None:
        self.page_idx = (self.page_idx - 1) % len(self.cfg["pages"])
        self.run_worker(self.build_page())

    def action_reload_cfg(self) -> None:
        try:
            self.cfg = load_config(self.config_path)
        except Exception as e:
            logger.error("Failed to reload config: %s", e)
            return
        self.run_worker(self.build_page())

    def action_quit(self) -> None:
        self.exit()

    async def on_unmount(self) -> None:
        await self.ha.close()


if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "dashboard.yml"
    cfg = load_config(config_file)
    asyncio.run(HADashboard(cfg, config_file).run_async())
