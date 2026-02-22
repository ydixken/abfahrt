# BVG Abfahrtsanzeige (Departure Display)

A desktop Python application that simulates a Berlin BVG train departure board. It fetches real-time departure data from the BVG Transport REST API and renders an amber-on-black dot-matrix style display in a Pygame window.

Supports multiple stations with automatic rotation.

## Requirements

- Python 3.12+
- A working internet connection (for live BVG data)

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
```

Press **ESC** or close the window to quit.

## Configuration

Edit `config.yaml` in the project root:

```yaml
stations:                       # Stations to rotate between
  - id: "900023201"             # S Savignyplatz
    name: ""                    # Auto-resolved from API
  - id: "900100003"             # S+U Alexanderplatz
    name: ""

rotation:
  interval_seconds: 10          # Seconds per station before switching

display:
  width: 1520
  height: 180
  fullscreen: false
  fps: 30
  background_color: [0, 0, 0]
  text_color: [255, 170, 0]    # Amber

refresh:
  interval_seconds: 30          # How often to fetch new data
  departure_count: 8            # Max departures to show

filters:                        # Transport types to include
  suburban: true
  subway: true
  tram: true
  bus: false
  ferry: false
  express: true
  regional: true
```

### CLI Overrides

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

## Architecture

```
BVG REST API  -->  api.py (BVGClient)
                      |
                      v
                   models.py (Departure, StationContext)
                      |
                      v
                   app.py (InfoDisplayApp orchestrator)
                    /    \
                   v      v
           renderer.py   display.py
           (PIL Image)   (Pygame window)
```

- **config.py** -- Loads defaults, YAML config, and CLI args
- **models.py** -- `Departure` dataclass with `minutes_until` and `delay_minutes` properties; `StationContext` for per-station state
- **api.py** -- `BVGClient` wrapping the BVG Transport REST API v6
- **renderer.py** -- `DepartureRenderer` producing a PIL Image with dot-matrix fonts, column layout, and S-Bahn icons
- **display.py** -- `DepartureDisplay` managing the Pygame window; `render_error()` for error overlays
- **app.py** -- `InfoDisplayApp` orchestrating multi-station rotation, per-station refresh, and the main loop

## Running Tests

```bash
python -m pytest tests/ -v
```

## API Attribution

This project uses the [BVG Transport REST API v6](https://v6.bvg.transport.rest) (free, no authentication required). Rate limit: 100 requests/minute.

## Fonts

Uses the [Dot Matrix Typeface](https://github.com/DanielHartUK/Dot-Matrix-Typeface) by Daniel Hart, licensed under the SIL Open Font License.
