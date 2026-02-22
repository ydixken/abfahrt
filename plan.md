# BVG Train Departure Display - Implementation Plan

## Context

We're building a desktop Python application that mimics a real Berlin train departure board (amber text on black, dot-matrix font). It fetches real-time departure data from the **BVG Transport REST API v6** (free, no auth, 100 req/min) and renders it in a Pygame window simulating an OLED display. Hardware integration comes later - for now we need a development mode with a GUI window.

**Reference screenshot** shows columns: Linie | Ziel | remarks ("Fahrradmitnahme möglich") | Abfahrt von (station + icon) | Abfahrt in (X min). Amber/orange `#FFAA00` text on black.

---

## Project Structure

```
infodisplay/
├── pyproject.toml
├── requirements.txt          # pygame, Pillow, requests, PyYAML, pytest
├── config.yaml               # User-editable config (station, display, filters)
├── .gitignore
├── README.md
├── src/infodisplay/
│   ├── __init__.py
│   ├── __main__.py           # Entry point + CLI routing
│   ├── config.py             # YAML + argparse config loading
│   ├── api.py                # BVG REST API client
│   ├── models.py             # Departure dataclass + parse_departure()
│   ├── renderer.py           # PIL-based board rendering
│   ├── display.py            # Pygame window (simulated OLED)
│   └── app.py                # Main loop orchestrator
├── fonts/                    # Dot Matrix Typeface TTFs (SIL license)
├── assets/                   # S-Bahn icon
└── tests/
    ├── conftest.py           # Fixtures with sample API responses
    ├── test_config.py
    ├── test_models.py
    ├── test_api.py
    └── test_renderer.py
```

## Tech Stack

| Component       | Choice       | Why                                                |
| --------------- | ------------ | -------------------------------------------------- |
| Python          | 3.12+        | Modern, good typing                                |
| Display window  | Pygame       | Pixel-perfect control, smooth refresh, fullscreen  |
| Rendering       | Pillow (PIL) | Text-to-image with TTF fonts, proven approach      |
| HTTP            | requests     | Simple sync HTTP, sufficient for 30s refresh cycle |
| Config          | PyYAML       | Human-readable, overlaid by argparse CLI args      |
| Fonts           | Dot Matrix Typeface | Purpose-built for departure boards, SIL license |
| Tests           | pytest       | Standard                                           |

## API Details

- **Base:** `https://v6.bvg.transport.rest`
- **Departures:** `GET /stops/{id}/departures?duration=60&results=8&suburban=true&subway=true...`
- **Search:** `GET /locations?query=Savignyplatz`
- **Key response fields:** `line.name`, `direction`, `when`, `plannedWhen`, `delay`, `platform`, `remarks[].code` (FK = bicycle)
- **Example station:** Savignyplatz = `900023201`

## Rendering Pipeline

```
                  ┌─ Station A departures ─┐
[BVG API] ───────►│  Station B departures  │──► [renderer.py] ──► [display.py]
  per station     └─ Station C departures ─┘    PIL Image for     Pygame window
                     rotation timer selects     active station
                     active station
```

The app fetches departures for **all configured stations** independently. A rotation timer selects which station is currently active. The renderer produces a PIL `Image` for the active station each frame. The display converts it to a Pygame surface and blits it. Re-rendering every frame ensures the "X min" countdown updates in real time.

## Multi-Station Rotation

The app supports **multiple home stations** and cycles between them automatically. Each station gets its own full-screen departure board. The display rotates between stations on a configurable interval.

**How it works:**
- `config.yaml` defines a `stations` list (replaces single `station`)
- `app.py` maintains a list of station contexts, each with its own cached departures
- A rotation timer switches the active station every N seconds
- The transition is a simple cut (no animation needed initially)
- Each station's data is fetched independently on its own refresh cycle
- The "Abfahrt von" column always shows the currently displayed station's name

## Configuration (`config.yaml`)

```yaml
stations:                       # List of home stations (rotates between them)
  - id: "900023201"
    name: ""                    # Auto-fetched if empty
  - id: "900100003"
    name: ""                    # e.g. Alexanderplatz

rotation:
  interval_seconds: 10          # Seconds per station before switching

display:
  width: 1520
  height: 180
  fullscreen: false
  fps: 30
  background_color: [0, 0, 0]
  text_color: [255, 170, 0]

refresh:
  interval_seconds: 30
  departure_count: 8

filters:
  suburban: true
  subway: true
  tram: true
  bus: false
  ferry: false
  express: true
  regional: true
```

CLI overrides: `--station-id` (single station, skips rotation), `--fullscreen`, `--refresh`, `--rotation`, `--search "name"`, `--fetch-test`, `--render-test`, `--debug`

---

## Milestones

### Milestone 1: Project Scaffolding & Data Layer

**Goal:** Project installs, config loads, data models work. No GUI.

| Task   | Description                                                                                          |
| ------ | ---------------------------------------------------------------------------------------------------- |
| 1.1    | Create directory structure, `pyproject.toml`, `requirements.txt`, `.gitignore`, init git             |
| 1.2    | Download Dot Matrix fonts into `fonts/` (Regular, Bold, BoldTall TTFs)                               |
| 1.3    | Implement `config.py`: nested dataclasses (including `stations` list + `rotation` settings), `load_config()` with defaults → YAML → argparse layering. Support both single `--station-id` CLI override and multi-station via YAML. |
| 1.4    | Implement `models.py`: `Departure` dataclass, `parse_departure()`, `minutes_until` property, `StationContext` dataclass (holds station id/name + cached departures + last fetch time) |
| 1.5    | Write `tests/test_config.py` and `tests/test_models.py`                                             |
| 1.6    | Set up venv, install deps, verify tests pass and `--help` works                                      |

**Deliverable:** `python -m infodisplay --help` works, tests pass.

---

### Milestone 2: BVG API Client

**Goal:** Fetch real departure data and convert to `Departure` objects.

| Task | Description                                                                                               |
| ---- | --------------------------------------------------------------------------------------------------------- |
| 2.1  | Implement `api.py`: `BVGClient` with `get_departures()`, `search_stations()`, `get_station_name()`       |
| 2.2  | Add `fetch_parsed_departures()` helper: calls API, maps through `parse_departure()`, filters, sorts      |
| 2.3  | Write `tests/test_api.py` with mocked requests                                                            |
| 2.4  | Add `--fetch-test` CLI mode: print live departures to stdout as formatted table                           |

**Deliverable:** `python -m infodisplay --fetch-test` prints live BVG departures.

---

### Milestone 3: Rendering Engine

**Goal:** PIL renderer produces a pixel-perfect departure board image.

| Task | Description                                                                                        |
| ---- | -------------------------------------------------------------------------------------------------- |
| 3.1  | Implement `renderer.py`: `DepartureRenderer` with column layout matching screenshot                |
| 3.2  | Create S-Bahn icon asset (`assets/sbahn_icon.png`, 16x16 amber roundel)                           |
| 3.3  | Handle delays visually: append `(+X)` to departure time                                           |
| 3.4  | Add `--render-test` CLI mode: render mock data to `test_output.png` and open it                    |
| 3.5  | Write `tests/test_renderer.py`: correct dimensions, non-empty output, edge cases                   |

**Layout (column positions as % of width):**
- 2% → Linie
- 16% → Ziel
- 35% → Remarks (smaller font, offset down)
- 54% → Abfahrt von (+ S-Bahn icon)
- 98% → Abfahrt in (right-aligned)

**Deliverable:** `python -m infodisplay --render-test` saves a PNG matching the reference screenshot.

---

### Milestone 4: Pygame Display & Main Loop (with Multi-Station Rotation)

**Goal:** Full working application with live data in a Pygame window, rotating between configured stations.

| Task | Description |
| ---- | ----------- |
| 4.1  | Implement `display.py`: `DepartureDisplay` with Pygame window, PIL→surface conversion, event loop |
| 4.2  | Implement `app.py`: `InfoDisplayApp` orchestrator with multi-station rotation: maintain a list of `StationContext` objects, fetch departures for each independently, rotation timer switches active station every N seconds, render the active station's board each frame |
| 4.3  | Wire up `__main__.py`: route to `--fetch-test`, `--render-test`, or full app mode |
| 4.4  | Add error overlay rendering: "Station nicht gefunden", "Keine Abfahrten", network errors |
| 4.5  | Manual integration testing: window, rotation between stations, refresh, ESC to quit, fullscreen, single-station fallback via `--station-id` |

**Rotation logic in `app.py`:**
- On startup, resolve names for all stations in `config.stations`
- Main loop tracks `active_station_index` and `last_rotation_time`
- When `rotation.interval_seconds` elapses, increment index (wrap around)
- Each station's departures are fetched on its own `refresh.interval_seconds` cycle
- If only one station is configured, rotation is disabled

**Deliverable:** `python -m infodisplay` opens a live departure board that rotates between configured stations.

---

### Milestone 5: Polish & Documentation

**Goal:** Production quality - logging, edge cases, station search, README.

| Task | Description                                                                         |
| ---- | ----------------------------------------------------------------------------------- |
| 5.1  | Add logging throughout (INFO default, `--debug` for DEBUG)                          |
| 5.2  | Handle edge cases: long names (truncate with ellipsis), missing data, text overflow |
| 5.3  | Add `--search "name"` CLI mode for interactive station lookup                       |
| 5.4  | Write comprehensive `README.md` with install, config, usage, architecture           |
| 5.5  | Final test pass, fix any gaps                                                       |

**Deliverable:** Polished, documented, tested application.

---

## Error Handling Strategy

| Scenario                 | Handling                                                      |
| ------------------------ | ------------------------------------------------------------- |
| Network/API failure      | Log warning, keep showing last successful data, retry on next interval |
| Malformed API response   | Skip bad departures, don't crash the batch                    |
| Station not found        | Show "Station nicht gefunden" on display                      |
| No departures            | Show "Keine Abfahrten" centered                               |
| Font files missing       | Fail fast with clear error message                            |
| Config file missing      | Use defaults (Savignyplatz, S-Bahn lines)                    |

## Team Composition

| Agent Name | Type | Responsibility |
| ---------- | ---- | -------------- |
| **Team Leader** | coordinator | Orchestration, task management, integration, code review |
| `devops-agent` | `general-purpose` | Project scaffolding, venv, deps, font download, git, CI |
| `data-agent` | `general-purpose` | Config system, data models, BVG API client, station search |
| `render-agent` | `general-purpose` | PIL renderer, S-Bahn icon asset, visual layout fidelity |
| `display-agent` | `general-purpose` | Pygame display window, app orchestrator, logging, README |

### File Ownership (to avoid conflicts)

| Agent | Owns (read/write) | Reads only |
| ----- | ------------------ | ---------- |
| `devops-agent` | `pyproject.toml`, `requirements.txt`, `.gitignore`, `fonts/`, `config.yaml` | everything |
| `data-agent` | `src/infodisplay/config.py`, `src/infodisplay/models.py`, `src/infodisplay/api.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_models.py`, `tests/test_api.py` | `config.yaml` |
| `render-agent` | `src/infodisplay/renderer.py`, `assets/`, `tests/test_renderer.py` | `models.py`, `config.py` |
| `display-agent` | `src/infodisplay/display.py`, `src/infodisplay/app.py`, `src/infodisplay/__main__.py`, `README.md` | all `src/` files |

**Conflict zone:** `__main__.py` is touched by display-agent but depends on interfaces from data-agent and render-agent. The leader should do final integration of CLI flags if conflicts arise.

---

## Task File Specification

The team leader must create tasks using `TaskCreate` at startup. Below is the full task list to create, organized by milestone. Each task includes its ID, title, description, owner, and dependencies.

### Milestone 1: Project Scaffolding & Data Layer

```
Task M1.1 — "Initialize project structure"
  Owner: devops-agent
  Dependencies: none
  Description: Create directory tree (src/infodisplay/, tests/, fonts/, assets/),
    pyproject.toml (name=infodisplay, version=0.1.0, requires-python>=3.12),
    requirements.txt (pygame>=2.5.0, Pillow>=10.0.0, requests>=2.31.0, PyYAML>=6.0, pytest>=7.0.0),
    .gitignore (.venv/, __pycache__/, *.pyc, .pytest_cache/, *.egg-info/, test_output.png),
    src/infodisplay/__init__.py (__version__ = "0.1.0"),
    src/infodisplay/__main__.py (stub),
    tests/__init__.py,
    git init, create venv, pip install deps.

Task M1.2 — "Download Dot Matrix fonts"
  Owner: devops-agent
  Dependencies: M1.1
  Description: Download TTFs from github.com/DanielHartUK/Dot-Matrix-Typeface into fonts/.
    Files needed: Dot Matrix Regular, Bold, Bold Tall.
    Rename to DotMatrix-Regular.ttf, DotMatrix-Bold.ttf, DotMatrix-BoldTall.ttf.
    Add fonts/LICENSE with SIL Open Font License notice.

Task M1.3 — "Implement config.py"
  Owner: data-agent
  Dependencies: M1.1
  Description: Nested dataclasses: StationConfig(id, name), DisplayConfig(width, height,
    fullscreen, fps, background_color, text_color), RefreshConfig(interval_seconds,
    departure_count), FilterConfig(suburban, subway, tram, bus, ferry, express, regional),
    RotationConfig(interval_seconds), FontConfig(header_size, departure_size, remark_size),
    top-level Config with stations: list[StationConfig] + rotation + display + refresh + filters + fonts.
    load_config(): defaults → YAML overlay → argparse overlay.
    CLI args: --station-id (single station override), --fullscreen, --refresh, --rotation,
    --search, --fetch-test, --render-test, --debug.

Task M1.4 — "Implement models.py"
  Owner: data-agent
  Dependencies: M1.1
  Description: Departure dataclass (line_name, line_product, direction, when, planned_when,
    delay_seconds, platform, remarks, is_cancelled) with minutes_until and delay_minutes properties.
    parse_departure(raw: dict) -> Departure function.
    StationContext dataclass (station_id, station_name, departures: list[Departure], last_fetch: float).
    Handle FK remark code → "Fahrradmitnahme möglich".

Task M1.5 — "Write config and model tests"
  Owner: data-agent
  Dependencies: M1.3, M1.4
  Description: tests/conftest.py with sample BVG API JSON fixtures.
    tests/test_config.py: test defaults, YAML overlay, CLI overlay, multi-station config.
    tests/test_models.py: test parse_departure with normal data, null when, null delay,
    empty remarks, minutes_until calculation, StationContext.

Task M1.6 — "Verify M1 deliverables"
  Owner: leader
  Dependencies: M1.1, M1.2, M1.3, M1.4, M1.5
  Description: Run pytest tests/ -v, verify python -m infodisplay --help works.
    Git commit "M1: Project scaffolding and data layer".
```

### Milestone 2: BVG API Client

```
Task M2.1 — "Implement api.py"
  Owner: data-agent
  Dependencies: M1.3, M1.4
  Description: BVGClient class using requests.Session.
    get_departures(station_id) → list[dict]: GET /stops/{id}/departures with filter params, 10s timeout.
    search_stations(query) → list[dict]: GET /locations?query={query}&results=5.
    get_station_name(station_id) → str: GET /stops/{id}, return name.
    fetch_parsed_departures(station_id) → list[Departure]: calls get_departures, maps parse_departure, filters cancelled, sorts by when.

Task M2.2 — "Write API tests"
  Owner: data-agent
  Dependencies: M2.1
  Description: tests/test_api.py using unittest.mock.patch on requests.Session.get.
    Test get_departures with mock response, verify URL and params.
    Test timeout/connection error raises RequestException.
    Test fetch_parsed_departures returns sorted Departure list.

Task M2.3 — "Add --fetch-test CLI mode"
  Owner: data-agent
  Dependencies: M2.1
  Description: In __main__.py, when --fetch-test flag is set, call fetch_parsed_departures
    for all configured stations and print a formatted table to stdout:
    "S7  | S Potsdam Hbf | Fahrradmitnahme möglich | 3 min | +0"

Task M2.4 — "Verify M2 deliverables"
  Owner: leader
  Dependencies: M2.1, M2.2, M2.3
  Description: Run pytest tests/test_api.py -v.
    Run python -m infodisplay --fetch-test and verify live output.
    Git commit "M2: BVG API client".
```

### Milestone 3: Rendering Engine

```
Task M3.1 — "Implement renderer.py"
  Owner: render-agent
  Dependencies: M1.1, M1.2, M1.4
  Description: DepartureRenderer class. Constructor loads fonts from fonts/.
    render(departures, station_name) → PIL Image.
    Layout columns (% of width): 2% Linie, 16% Ziel, 35% Remarks (smaller font, y-offset),
    54% Abfahrt von (+ icon), 98% Abfahrt in (right-aligned).
    Header row with amber text + thin horizontal separator line.
    Each departure row: line name, destination, remarks, station name, "X min".
    Delays shown as "(+X)" appended to time.

Task M3.2 — "Create S-Bahn icon asset"
  Owner: render-agent
  Dependencies: M1.1
  Description: Create assets/sbahn_icon.png — 16x16 amber roundel with "S" on transparent bg.
    Can be generated programmatically with PIL if needed.
    Load in renderer, resize to font height, composite after station name.

Task M3.3 — "Add --render-test CLI mode"
  Owner: render-agent
  Dependencies: M3.1, M3.2
  Description: When --render-test flag, create mock Departure objects (no API),
    render via DepartureRenderer, save to test_output.png, print path.
    Compare visually against Screenshot 2026-02-22 at 20.49.56.png.

Task M3.4 — "Write renderer tests"
  Owner: render-agent
  Dependencies: M3.1
  Description: tests/test_renderer.py: correct image dimensions, non-all-black output,
    0 departures shows header, overflow (more departures than fit) doesn't crash.

Task M3.5 — "Verify M3 deliverables"
  Owner: leader
  Dependencies: M3.1, M3.2, M3.3, M3.4
  Description: Run pytest tests/test_renderer.py -v.
    Run python -m infodisplay --render-test, inspect test_output.png.
    Git commit "M3: Rendering engine".
```

### Milestone 4: Pygame Display & Main Loop

```
Task M4.1 — "Implement display.py"
  Owner: display-agent
  Dependencies: M1.1
  Description: DepartureDisplay class with Pygame.
    __init__: pygame.init(), create window (config size), set caption "BVG Abfahrtsanzeige".
    update(pil_image): convert PIL Image → pygame surface via pygame.image.fromstring(), blit, flip.
    handle_events() → bool: return False on QUIT or ESC.
    close(): pygame.quit(). Support --fullscreen via pygame.FULLSCREEN flag.

Task M4.2 — "Implement app.py with multi-station rotation"
  Owner: display-agent
  Dependencies: M2.1, M3.1, M4.1
  Description: InfoDisplayApp orchestrator.
    Maintain list of StationContext objects (one per configured station).
    On startup, resolve station names via API for all stations.
    Main loop: handle_events, check rotation timer (switch active_station_index every
    rotation.interval_seconds, wrap around), check refresh timer per station (fetch
    independently), render active station's board, update display.
    Single station: rotation disabled. Error handling: show error overlay if first fetch fails.

Task M4.3 — "Wire up __main__.py"
  Owner: display-agent
  Dependencies: M4.2, M2.3, M3.3
  Description: Full CLI routing: --fetch-test → print table, --render-test → save PNG,
    --search → station lookup, default → InfoDisplayApp().run().
    Wrap in try/except for KeyboardInterrupt and unexpected errors.

Task M4.4 — "Add error overlay rendering"
  Owner: display-agent
  Dependencies: M3.1
  Description: In renderer.py (or display-agent coordinates with render-agent), add
    render_error(message) → PIL Image that shows centered error text on black bg.
    Messages: "Station nicht gefunden", "Keine Abfahrten", "Netzwerkfehler".

Task M4.5 — "Verify M4 deliverables"
  Owner: leader
  Dependencies: M4.1, M4.2, M4.3, M4.4
  Description: Run python -m infodisplay — verify window opens, data loads, rotates stations.
    Test ESC to quit, --fullscreen, --station-id override, network disconnect (show stale data).
    Git commit "M4: Pygame display and main loop".
```

### Milestone 5: Polish & Documentation

```
Task M5.1 — "Add logging"
  Owner: display-agent
  Dependencies: M4.5
  Description: Python logging module throughout. INFO default, --debug for DEBUG.
    Log: API fetch times, parse errors, refresh cycles, rotation switches, Pygame events.

Task M5.2 — "Handle edge cases in rendering"
  Owner: render-agent
  Dependencies: M4.5
  Description: Long destination names — truncate with ellipsis using font.getbbox().
    Long line names. Missing data fields. Text overflow into adjacent columns.

Task M5.3 — "Add --search CLI mode"
  Owner: data-agent
  Dependencies: M4.5
  Description: --search "Station Name" calls search_stations(), prints numbered list:
    "1. S+U Alexanderplatz Bhf (Berlin)  [ID: 900100003]"
    User copies ID into config.yaml.

Task M5.4 — "Write README.md"
  Owner: display-agent
  Dependencies: M4.5
  Description: Installation (venv, pip, font note), configuration guide (all config.yaml
    options with multi-station example), usage examples, architecture overview, API attribution.

Task M5.5 — "Final test pass and review"
  Owner: leader
  Dependencies: M5.1, M5.2, M5.3, M5.4
  Description: Run pytest tests/ -v, verify all pass. Read all source files.
    Run full app, verify multi-station rotation, verify --search, verify edge cases.
    Git commit "M5: Polish and documentation". Tag v0.1.0.
```

---

## Verification

1. `python -m infodisplay --help` → shows all CLI options
2. `python -m infodisplay --fetch-test` → prints live BVG departures for all configured stations
3. `python -m infodisplay --render-test` → saves PNG matching reference screenshot
4. `python -m infodisplay` → opens Pygame window with live departure board, **rotates between configured stations**
5. `python -m infodisplay --station-id 900100003` → single-station mode (no rotation)
6. `python -m infodisplay --search "Alexanderplatz"` → lists matching stations with IDs
7. `pytest tests/ -v` → all tests pass

---

## Team Leader Instructions

You are the **team leader** for building the BVG InfoDisplay application. Your job is to coordinate a team of 4 agents, manage the task list, and ensure milestones are delivered in order.

### Step 1: Create the Team

Create a team called `infodisplay` with TeamCreate.

### Step 2: Read the Plan

Read the full plan file at `/Users/ydixken/development/infodisplay/plan.md` before doing anything else.

### Step 3: Create All Tasks Upfront

Use TaskCreate to register every task from the "Task File Specification" section above. Set dependencies as specified. Leave owners unassigned initially (you'll assign them when spawning agents).

### Step 4: Spawn devops-agent First

Spawn `devops-agent` via the Task tool with `team_name: "infodisplay"` and assign it Tasks M1.1 and M1.2. Give it this context:

> You are the devops-agent for the infodisplay project. Read the plan at /Users/ydixken/development/infodisplay/plan.md. Your tasks are M1.1 (project scaffolding) and M1.2 (font download). Project root: /Users/ydixken/development/infodisplay. You own: pyproject.toml, requirements.txt, .gitignore, fonts/, config.yaml. After completing each task, mark it done via TaskUpdate and check TaskList for more work.

Wait for devops-agent to complete M1.1 before proceeding.

### Step 5: Spawn data-agent and render-agent IN PARALLEL

Once M1.1 is done (project structure exists), spawn both agents in the same message:

**data-agent context:**
> You are the data-agent for the infodisplay project. Read the plan at /Users/ydixken/development/infodisplay/plan.md. Your tasks are M1.3 (config.py), M1.4 (models.py), M1.5 (tests). Then M2.1-M2.3 (API client + tests + fetch-test CLI). Then M5.3 (station search CLI). Project root: /Users/ydixken/development/infodisplay. You own: src/infodisplay/config.py, src/infodisplay/models.py, src/infodisplay/api.py, tests/conftest.py, tests/test_config.py, tests/test_models.py, tests/test_api.py. Do NOT modify renderer.py, display.py, or app.py. Use the venv at .venv/ to run tests. After completing each task, mark it done via TaskUpdate and check TaskList for more work.

**render-agent context:**
> You are the render-agent for the infodisplay project. Read the plan at /Users/ydixken/development/infodisplay/plan.md. Your tasks are M3.1 (renderer.py), M3.2 (S-Bahn icon), M3.3 (render-test CLI), M3.4 (renderer tests). Then M5.2 (edge cases). Project root: /Users/ydixken/development/infodisplay. You own: src/infodisplay/renderer.py, assets/, tests/test_renderer.py. You need models.py for the Departure dataclass — read it from data-agent's work but don't modify it. Reference screenshot: /Users/ydixken/development/infodisplay/Screenshot 2026-02-22 at 20.49.56.png. After completing each task, mark it done via TaskUpdate and check TaskList for more work.

### Step 6: Spawn display-agent When M2+M3 Are Done

Once both data-agent and render-agent finish their milestone tasks:

**display-agent context:**
> You are the display-agent for the infodisplay project. Read the plan at /Users/ydixken/development/infodisplay/plan.md. Your tasks are M4.1 (display.py), M4.2 (app.py with multi-station rotation), M4.3 (__main__.py integration), M4.4 (error overlays). Then M5.1 (logging) and M5.4 (README.md). Project root: /Users/ydixken/development/infodisplay. You own: src/infodisplay/display.py, src/infodisplay/app.py, src/infodisplay/__main__.py, README.md. You will import from config.py, models.py, api.py, renderer.py — read them but don't modify. After completing each task, mark it done via TaskUpdate and check TaskList for more work.

### Step 7: Verify Each Milestone

After each milestone's tasks are all marked complete:

1. **M1:** Run `cd /Users/ydixken/development/infodisplay && .venv/bin/python -m pytest tests/ -v && .venv/bin/python -m infodisplay --help`
2. **M2:** Run `.venv/bin/python -m pytest tests/test_api.py -v && .venv/bin/python -m infodisplay --fetch-test`
3. **M3:** Run `.venv/bin/python -m pytest tests/test_renderer.py -v && .venv/bin/python -m infodisplay --render-test`
4. **M4:** Run `.venv/bin/python -m infodisplay` — verify window, rotation, ESC quit
5. **M5:** Run full test suite, verify all features, create final commit

If verification fails, message the responsible agent with the error output and ask them to fix it.

### Step 8: Git Commits

Create a git commit after each milestone passes verification:
- M1: `"feat: project scaffolding and data layer"`
- M2: `"feat: BVG API client with fetch-test CLI"`
- M3: `"feat: PIL rendering engine with render-test CLI"`
- M4: `"feat: Pygame display with multi-station rotation"`
- M5: `"feat: polish, logging, station search, documentation"`

### Step 9: Shutdown

After M5 verification passes, send shutdown_request to all agents and clean up the team with TeamDelete.

### Error Recovery

- If an agent's tests fail, send them a message with the test output and ask them to fix
- If the API is down during development, agents should use mock data from `tests/conftest.py`
- If font download fails, devops-agent should try alternative download URLs or create a fallback
- If agents produce incompatible interfaces, pause both and align on the shared `models.py` contract first
- If `__main__.py` has conflicts from multiple agents, resolve it yourself as the leader
