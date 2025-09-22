# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based Home Assistant TUI (Text User Interface) dashboard built with Textual. The application provides a terminal-based interface for monitoring and controlling Home Assistant entities through WebSocket connections and REST API calls.

## Architecture

### Core Components

- **Environment Loading** (`ha-tui.py:4,11`): Automatic .env file loading using python-dotenv
  - Loads environment variables from .env file at startup
  - Supports both .env files and system environment variables

- **HAClient** (`ha-tui.py:19-107`): Manages WebSocket connection and REST API communication with Home Assistant
  - Handles authentication, state caching, and real-time event streaming
  - Maintains entity history for sparkline widgets (600 sample rolling window)
  - Provides service call functionality for Home Assistant actions

- **Widget System** (`ha-tui.py:110-182`): Four widget types for different entity display modes
  - `ValueWidget` (`ha-tui.py:110-127`): Displays numeric sensor values with formatting
  - `BinaryWidget` (`ha-tui.py:128-142`): Shows binary states (on/off, open/closed, etc.)
  - `SparklineWidget` (`ha-tui.py:143-162`): ASCII sparkline charts from historical data
  - `ActionWidget` (`ha-tui.py:163-182`): Clickable buttons for Home Assistant service calls

- **HADashboard App** (`ha-tui.py:184-305`): Main Textual application
  - Multi-page navigation with configurable layouts (grid-1/2/3, rows)
  - Real-time UI refresh and keyboard bindings
  - Dynamic page building from YAML configuration

### Configuration System

The app uses multiple configuration sources:

**Environment Variables (.env file or system)**:
- **HA_TOKEN**: Home Assistant long-lived access token
- Automatically loaded from `.env` file if present

**dashboard.yml Configuration**:
- **HA Connection**: URL, token (supports `${HA_TOKEN}` variable substitution), SSL settings
- **Pages**: Multiple dashboard pages with different layouts and widget collections
- **Keybinds**: Customizable keyboard shortcuts
- **UI Settings**: Refresh rate and theme options

## Running the Application

```bash
python ha-tui.py
```

The application expects a `dashboard.yml` file in the current directory. Use `dashboard.yml.example` as a template.

## Environment Setup

### Option 1: Using .env file (Recommended)
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set your Home Assistant token:
   ```
   HA_TOKEN=your_home_assistant_long_lived_access_token_here
   ```

### Option 2: Environment variable
Set your Home Assistant token as an environment variable:
```bash
export HA_TOKEN="your_home_assistant_token"
```

## Dependencies

Install dependencies:
```bash
pip install -r requirements.txt
```

The application requires:
- `aiohttp` - Async HTTP client for REST API calls
- `websockets` - WebSocket client for real-time events
- `textual` - TUI framework
- `pyyaml` - YAML configuration parsing
- `python-dotenv` - Environment variable loading from .env files

## Configuration Structure

- **ha.url**: Home Assistant base URL
- **ha.token**: Long-lived access token (use `${HA_TOKEN}` for env var)
- **ha.verify_ssl**: SSL certificate verification (default: true)
- **pages**: Array of dashboard pages with widgets
- **keybinds**: Custom key mappings for navigation

Widget types support different configuration options:
- **value**: `entity`, `label`, `unit`, `fmt` (number formatting)
- **binary**: `entity`, `label`, `on_text`, `off_text`
- **sparkline**: `entity`, `label`, `window` (sample count)
- **action**: `label`, `service`, `data` (service call parameters)

## Key Navigation

Default keybindings:
- `Tab`: Next page
- `Shift+Tab`: Previous page
- `R`: Reload configuration
- `Q`: Quit application