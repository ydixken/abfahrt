# BVG Abfahrtsanzeige (Departure Display)

A desktop Python application that simulates a Berlin BVG train departure board. It fetches real-time departure data from the BVG Transport REST API and renders an amber-on-black display using the FF Transit typeface (the official BVG font) in a Pygame window.

Multi-station rotation, live weather, per-station line filtering, hurry-zone blinking, and more.

## Requirements

- Python 3.12+
- Internet connection (BVG API for departures, Open-Meteo for weather)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd infodisplay

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
```

## Usage

```bash
# Run the live departure display
python -m infodisplay

# Run in fullscreen mode
python -m infodisplay --fullscreen

# Override to a single station (no rotation)
python -m infodisplay --station-id 900100003

# Search for a station ID
python -m infodisplay --search "Alexanderplatz"

# Fetch live departures and print to terminal
python -m infodisplay --fetch-test

# Render a test image to test_output.png
python -m infodisplay --render-test

# Enable debug logging
python -m infodisplay --debug

# Custom refresh and rotation intervals
python -m infodisplay --refresh 15 --rotation 5
```

Press **ESC** or close the window to quit.

### CLI Flags

| Flag | Description |
|------|-------------|
| `--station-id ID` | Single station mode (skips rotation) |
| `--fullscreen` | Run in fullscreen |
| `--refresh N` | Refresh interval in seconds |
| `--rotation N` | Rotation interval in seconds |
| `--search "name"` | Search for a station by name |
| `--fetch-test` | Print live departures to stdout |
| `--render-test` | Save a test render to `test_output.png` |
| `--debug` | Enable debug-level logging |

## Configuration

Edit `config.yaml` in the project root. All sections are optional — defaults are used for anything omitted.

```yaml
stations:                           # Stations to rotate between
  - id: "900120013"                 # BVG station ID (use --search to find)
    name: "Tram Holteistrasse"      # Display name (auto-resolved if empty)
    walking_minutes: 5              # Walking time in minutes (for hurry-zone)
  - id: "900120009"
    name: "U Samariterstrasse"
    walking_minutes: 10
  - id: "900120003"
    name: "S Ostkreuz"
    walking_minutes: 10
    lines: ["S41", "S42"]           # Only show these lines (optional)

rotation:
  interval_seconds: 10              # Seconds per station before switching

display:
  width: 1024                       # Window width in pixels
  height: 256                       # Window height in pixels
  fullscreen: false
  fps: 60
  background_color: [0, 0, 0]      # RGB black
  text_color: [255, 170, 0]        # RGB amber
  show_remarks: false               # Toggle remarks column

refresh:
  interval_seconds: 30              # How often to fetch new departure data
  departure_count: 20               # Max departures to request from API

filters:                            # Transport types to include
  suburban: true                    # S-Bahn
  subway: true                      # U-Bahn
  tram: true                        # Tram / MetroTram
  bus: true                         # Bus
  ferry: false                      # Ferry
  express: true                     # Express (RE, RB)
  regional: true                    # Regional

fonts:                              # Font configuration (optional)
  font_header: "Transit_Wide_Bold.ttf"
  font_main: "Transit_Bold.ttf"
  font_remark: "Transit_Condensed_Normal.ttf"
  station_name_size: 20
  header_size: 13
  departure_size: 18
  remark_size: 13

weather:                            # Weather display (optional)
  latitude: 52.5170                 # Coordinates (default: Berlin Friedrichshain)
  longitude: 13.4540
  refresh_seconds: 600              # Cache duration (10 minutes)
```

## Features

### Multi-Station Rotation

Configure multiple stations and the display rotates between them automatically. Rotation is scroll-gated — it waits for any scrolling remarks to finish before switching. Override to a single station with `--station-id`.

### Per-Station Line Filtering

Add an optional `lines` list to any station to show only specific lines. For example, at Ostkreuz you might only care about the Ringbahn:

```yaml
- id: "900120003"
  name: "S Ostkreuz"
  lines: ["S41", "S42"]
```

When `lines` is omitted or empty, all departures (matching global filters) are shown.

### Weather Display

Current temperature, daily low/high, and 12-hour precipitation forecast are shown in the station header bar. Uses the Open-Meteo API (free, no API key required). Refreshes every 10 minutes by default.

### Hurry-Zone Blinking

Departures within a "hurry zone" blink their time columns to signal you might still catch the train if you hurry. The hurry zone is `walking_minutes - 3` to `walking_minutes`. For example, with `walking_minutes: 10`, departures arriving in 7–10 minutes will blink. Departures below the hurry threshold are filtered out entirely.

### Line Prefixes

- Tram lines are prefixed with **M** (MetroTram branding): `21` → `M21`
- Bus lines are prefixed with **B**: `240` → `B240`

### Departure Time Column

Each row shows the actual departure time as HH:MM (planned time + delay), alongside the minutes-until countdown.

### Delay Display

Delayed departures show the delay as `+Xmin` next to the minutes-until value.

### Remarks Toggle

Set `show_remarks: false` in the display config to hide the remarks column and give more space to the destination column. When enabled, long remarks scroll horizontally with a pause at each end.

### Transport Type Filters

Toggle which transport types to include globally via the `filters` section: S-Bahn, U-Bahn, tram, bus, ferry, express, and regional.

### Dynamic Font Scaling

All font sizes and padding scale dynamically based on display height (`height / 128`), so the layout works at any resolution.

## Architecture

```
BVG REST API  →  api.py (BVGClient)
                    │
                    ▼
                 models.py (Departure, StationContext)
                    │
                    ▼
                 app.py (InfoDisplayApp)
                ╱   │   ╲
               ▼    ▼    ▼
      renderer.py  display.py  weather.py
      (PIL Image)  (Pygame)    (Open-Meteo)
```

| Module | Purpose |
|--------|---------|
| `config.py` | Three-layer config loading: defaults → YAML → CLI args |
| `models.py` | `Departure` dataclass with `minutes_until` and `delay_minutes` properties; `StationContext` for per-station state; `parse_departure()` parser with line prefix logic |
| `api.py` | `BVGClient` wrapping the BVG Transport REST API v6 (departures, station search, name lookup) |
| `renderer.py` | `DepartureRenderer` producing a PIL Image with column layout, dynamic scaling, scrolling text, and blink effects |
| `display.py` | `DepartureDisplay` managing the Pygame window and keyboard/quit events |
| `app.py` | `InfoDisplayApp` orchestrating multi-station rotation, per-station refresh, weather fetching, filtering, and the main loop |
| `weather.py` | `WeatherData` dataclass and `fetch_weather()` using the Open-Meteo free API |

## Project Structure

```
infodisplay/
├── config.yaml                   # Main configuration
├── pyproject.toml                # Build and dependency config
├── README.md
│
├── src/infodisplay/              # Source code
│   ├── __init__.py
│   ├── __main__.py               # Entry point and CLI routing
│   ├── config.py                 # Configuration loading
│   ├── models.py                 # Data models and parsing
│   ├── api.py                    # BVG API client
│   ├── renderer.py               # PIL image rendering
│   ├── display.py                # Pygame display
│   ├── app.py                    # Main orchestrator
│   └── weather.py                # Weather client
│
├── fonts/                        # FF Transit typefaces
│   ├── Transit_Bold.ttf
│   ├── Transit_Condensed_Normal.ttf
│   └── Transit_Wide_Bold.ttf
│
└── tests/                        # Test suite
    ├── conftest.py               # Shared fixtures
    ├── test_config.py
    ├── test_models.py
    ├── test_api.py
    └── test_renderer.py
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## API Attribution

- [BVG Transport REST API v6](https://v6.bvg.transport.rest) — free, no authentication required, rate limit 100 requests/minute
- [Open-Meteo API](https://open-meteo.com/) — free weather API, no API key required

## Fonts

Uses the **FF Transit** typeface family — the official typeface of BVG (Berliner Verkehrsbetriebe). Three variants are included in the `fonts/` directory: Transit Wide Bold, Transit Bold, and Transit Condensed Normal.
