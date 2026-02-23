"""Generate demo.gif with live API data, cancellation, and hurry-zone blinking."""

import time as _time_mod
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from infodisplay.api import BVGClient
from infodisplay.config import load_config
from infodisplay.models import Departure
from infodisplay.renderer import DepartureRenderer, BLINK_PERIOD
from infodisplay.weather import WeatherData

# GIF parameters
FRAME_MS = 220  # real playback speed per frame (ms)
TIME_STEP = 0.15  # simulated seconds per frame
STATION_DISPLAY_SECONDS = 6.0  # simulated seconds per station
GIF_BLINK_PERIOD = 3.0  # slower blink for GIF readability

# Load config
config = load_config(cli_args=[])

# Fetch live departures for each station
client = BVGClient(config)
station_data = []  # list of (name, walking_minutes, departures)

for station_cfg in config.stations:
    name = station_cfg.name or client.get_station_name(station_cfg.id)
    deps = client.fetch_parsed_departures(station_cfg.id)

    # Apply per-station line filters
    if station_cfg.lines:
        deps = [d for d in deps if d.line_name in station_cfg.lines]

    # Take only show_items departures
    deps = deps[: config.display.show_items]

    print(f"  {name}: {len(deps)} departures")
    for d in deps:
        print(f"    {d.line_name} → {d.direction} in {d.minutes_until}m (cancelled={d.is_cancelled})")

    station_data.append((name, station_cfg.walking_minutes, deps))

# Inject a cancelled departure into the first station that has room
if station_data:
    name, wm, deps = station_data[0]
    now = datetime.now(timezone.utc)
    cancelled_dep = Departure(
        line_name="RE1",
        line_product="regional",
        direction="Frankfurt (Oder)",
        when=(now + timedelta(minutes=15)).isoformat(),
        planned_when=(now + timedelta(minutes=15)).isoformat(),
        delay_seconds=0,
        platform="3",
        remarks=[],
        is_cancelled=True,
    )
    # Replace the last departure with the cancelled one
    if len(deps) >= config.display.show_items:
        deps[-1] = cancelled_dep
    else:
        deps.append(cancelled_dep)
    station_data[0] = (name, wm, deps)
    print(f"\n  Injected cancelled RE1 into '{name}'")

# Also ensure at least one departure is in hurry zone for station 0
# hurry zone = walking_minutes - 3 to walking_minutes
name, wm, deps = station_data[0]
hurry_low = max(0, wm - 3)
has_hurry = any(
    d.minutes_until is not None and hurry_low <= d.minutes_until <= wm and not d.is_cancelled
    for d in deps
)
if not has_hurry and deps:
    # Move the first non-cancelled departure into hurry zone
    for d in deps:
        if not d.is_cancelled:
            now = datetime.now(timezone.utc)
            target_min = wm - 1  # e.g. 4 min for walking_minutes=5
            d.when = (now + timedelta(minutes=target_min)).isoformat()
            d.planned_when = d.when
            d.delay_seconds = 0
            print(f"  Adjusted {d.line_name} to {target_min}m for hurry zone")
            break

# Mock weather
mock_weather = WeatherData(
    current_temp=4,
    daily_low=1,
    daily_high=8,
    precip_next_12h=[0.0, 0.0, 0.1, 0.3, 0.5, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
)

# Create renderer
import infodisplay.renderer as renderer_mod
original_blink = renderer_mod.BLINK_PERIOD
renderer_mod.BLINK_PERIOD = GIF_BLINK_PERIOD

renderer = DepartureRenderer(
    width=config.display.width,
    height=config.display.height,
    font_header=config.fonts.font_header,
    font_main=config.fonts.font_main,
    font_remark=config.fonts.font_remark,
    station_name_size=config.fonts.station_name_size,
    header_size=config.fonts.header_size,
    departure_size=config.fonts.departure_size,
    remark_size=config.fonts.remark_size,
    show_remarks=config.display.show_remarks,
    show_items=config.display.show_items,
)

# Generate frames
frames = []
fake_time = _time_mod.time()
original_time = _time_mod.time

# Patch time.time for blink/scroll control
_time_mod.time = lambda: fake_time

try:
    for station_idx, (name, wm, deps) in enumerate(station_data):
        # Reset scroll start for each station
        renderer._scroll_start = fake_time
        station_start = fake_time

        # Render frames for this station
        while fake_time - station_start < STATION_DISPLAY_SECONDS:
            img, _ = renderer.render(
                deps, name, wm, mock_weather, weather_page=station_idx,
            )
            frames.append(img.copy())
            fake_time += TIME_STEP
finally:
    _time_mod.time = original_time
    renderer_mod.BLINK_PERIOD = original_blink

# Convert all frames to palette mode for reliable GIF saving
# Use a shared palette from the first frame for consistency
palette_img = frames[0].quantize(colors=256, method=Image.Quantize.MEDIANCUT)
palette = palette_img.getpalette()

p_frames = []
for f in frames:
    pf = f.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    p_frames.append(pf)

# Save GIF
output_path = Path(__file__).resolve().parent / "assets" / "demo.gif"
output_path.parent.mkdir(exist_ok=True)

if len(p_frames) > 1:
    p_frames[0].save(
        str(output_path),
        save_all=True,
        append_images=p_frames[1:],
        duration=FRAME_MS,
        loop=0,
    )
else:
    p_frames[0].save(str(output_path))

print(f"\nGenerated {len(p_frames)} frames, {len(p_frames) * FRAME_MS / 1000:.1f}s total")
print(f"Saved to: {output_path}")
