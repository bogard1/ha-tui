# HA-TUI — Home Assistant Terminal Dashboard

A terminal dashboard for Home Assistant built with [Textual](https://textual.textualize.io/). Real-time monitoring and control from the command line.

## Features

- **Real-time** — WebSocket connection with automatic reconnection on drops
- **8 widget types** — Values, binaries, sparklines, toggles, actions, headings, and Spotify player
- **Multi-page with sections** — Each section has its own independent layout
- **YAML configurable** — Full dashboard defined in a single file
- **Environment variables** — Secure token via `.env` or system environment variable

## Installation

```bash
# Install dependencies in a virtual environment (recommended)
make install

# Set up .env file
make env
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Make Commands

| Command | Description |
|---------|-------------|
| `make run` | Run the dashboard |
| `make install` | Create virtualenv and install dependencies |
| `make setup` | `install` + create `.env` if it doesn't exist |
| `make env` | Copy `.env.example` → `.env` |
| `make test` | Run tests |
| `make lint` | Check syntax of `ha-tui.py` |
| `make clean` | Remove `__pycache__`, `.pyc` files, and `.venv` |

## Configuration

### 1. Home Assistant Token

Generate a token in HA: **Profile → Long-lived access tokens**

Then add it to your `.env` file:

```
HA_TOKEN=your_token_here
```

### 2. Create `dashboard.yml`

Copy the example and edit it:

```bash
cp dashboard.yml.example dashboard.yml
```

Basic structure:

```yaml
ha:
  url: "http://192.168.1.100:8123"
  token: "${HA_TOKEN}"
  verify_ssl: false

ui:
  refresh_ms: 250

pages:
  - id: "home"
    title: "Home"
    sections:
      - layout: "grid-4"
        widgets:
          - type: "value_sparkline"
            entity: "sensor.living_temperature"
            label: "Living"
            unit: "°C"
            fmt: ".1f"

      - title: "Lights"
        layout: "grid-3"
        widgets:
          - type: "toggle"
            entity: "light.living_main"
            label: "Main"
```

### 3. Run

```bash
make run

# Or with a custom config file:
.venv/bin/python ha-tui.py my-dashboard.yml
```

## Widget Types

### `value` — Numeric value

```yaml
- type: "value"
  entity: "sensor.living_temperature"
  label: "Temperature"
  unit: "°C"
  fmt: ".1f"
```

### `value_sparkline` — Value + history chart

```yaml
- type: "value_sparkline"
  entity: "sensor.living_temperature"
  label: "Living"
  unit: "°C"
  fmt: ".1f"
  window: 60        # last N samples shown in the chart
```

### `binary` — On/off state

```yaml
- type: "binary"
  entity: "binary_sensor.front_door"
  label: "Front door"
  on_text: "OPEN"
  off_text: "closed"
```

### `sparkline` — ASCII history chart

```yaml
- type: "sparkline"
  entity: "sensor.power_consumption"
  label: "Power"
  window: 120
```

### `toggle` — Light/switch control (clickable)

Shows current state and toggles on click.

```yaml
- type: "toggle"
  entity: "light.living_main"
  label: "Main light"
  on_text: "on"
  off_text: "off"
  toggle_service: "homeassistant/toggle"   # optional
```

### `action` — Button that calls a service

```yaml
- type: "action"
  label: "Arm alarm"
  service: "alarm_control_panel/alarm_arm_away"
  data:
    entity_id: "alarm_control_panel.home"
```

### `heading` — Section heading (only in `widgets` mode)

```yaml
- type: "heading"
  text: "Office"
```

### `spotify` — Spotify / media player control

Displays current track, artist, and a progress bar. Includes ⏮ ▶/⏸ ⏭ clickable controls that call the corresponding `media_player` services in Home Assistant.

```yaml
- type: "spotify"
  entity: "media_player.spotify_rodrigo_gonzalez"
  label: "Spotify"
```

The play/pause button updates automatically based on the player state. Shows "No disponible" when the entity is absent or HA is unreachable.

## Layouts

Available for each section:

| Layout | Columns |
|--------|---------|
| `grid-1` | 1 |
| `grid-2` | 2 |
| `grid-3` | 3 |
| `grid-4` | 4 |
| `rows` | 1 (alias for grid-1) |

## Pages with Sections

Each page can have multiple sections, each with its own layout and title:

```yaml
pages:
  - id: "home"
    title: "Home"
    sections:
      - layout: "grid-4"          # no title: widgets only
        widgets: [...]

      - title: "Office"           # with title: shows heading
        layout: "grid-4"
        widgets: [...]

      - title: "Bedroom"
        layout: "grid-2"          # different layout per section
        widgets: [...]
```

## Navigation

Default keybindings (customizable in `dashboard.yml`):

| Key | Action |
|-----|--------|
| `Tab` | Next page |
| `Shift+Tab` | Previous page |
| `R` | Reload configuration |
| `Q` | Quit |

Custom keybindings:

```yaml
keybinds:
  next_page: "tab"
  prev_page: "shift+tab"
  reload_config: "r"
  quit: "q"
```

## Troubleshooting

**Connection error** — Check the URL, token, and that HA is reachable. The error is displayed on screen without closing the app.

**SSL/HTTPS** — For self-signed certificates use `verify_ssl: false`.

**Entity not found** — Widgets show `—` if the entity doesn't exist. Verify the `entity_id` in HA: *Developer Tools → States*.

**Invalid token** — The authentication error is shown on startup. Regenerate the token in HA and update `.env`.

## License

MIT — see `LICENSE` file.
