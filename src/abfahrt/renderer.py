"""PIL-based departure board renderer.

Renders an amber-on-black BVG Abfahrtsanzeige (departure display) as a
PIL Image. Supports dynamic scaling, hurry-zone blinking, cancelled
departure indicators, and horizontally scrolling remarks.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from abfahrt.models import Departure
from abfahrt.weather import WeatherData

# Project root (three levels up from this file)
_ROOT = Path(__file__).resolve().parent.parent.parent
_FONTS_DIR = _ROOT / "fonts"

# Amber color matching real BVG departure boards
AMBER = (255, 170, 0)
# Pure black background
BLACK = (0, 0, 0)

# Board column layout (values are percentages of display width):
#
#   | Linie | sep | Ziel (destination) | Remarks | HH:MM | Xm |
#   | 2%    |     | 16%                | 58%     | 73%   | 98%|
#
# "Linie" and "Ziel" are left-aligned. "Xm" (minutes countdown) is
# right-aligned to the display edge. A 1px vertical separator divides
# Linie from Ziel at 14% width.

# Left edge of the line name column (e.g. "S7", "M21")
COL_LINIE = 0.02
# Left edge of the destination column
COL_ZIEL = 0.16
# Left edge of the scrolling remarks column (hidden when show_remarks=False)
COL_REMARKS = 0.58
# Left edge of the "HH:MM" departure time column
COL_DEP_TIME = 0.73
# Right edge of the "Xm" minutes-until column (right-aligned)
COL_ABFAHRT_IN = 0.98

# Pixels per second for horizontal text scroll
SCROLL_SPEED = 30
# Seconds to hold at start/end of scroll cycle
SCROLL_PAUSE = 2.0

# Full blink cycle in seconds. First half = hurry-zone inverted colors
# (black on amber), second half = normal (amber on black).
BLINK_PERIOD = 2.0


class DepartureRenderer:
    """Renders a BVG departure board as a PIL Image.

    Produces an amber-on-black image mimicking a real BVG Abfahrtsanzeige
    (departure display). The board has a station name header bar at the top,
    followed by rows of departures with columns for line name, destination,
    remarks, departure time, and minutes until departure.

    All font sizes and spacing scale dynamically based on display height,
    using 128px as the base reference (the native height of an SSD1322
    OLED at 2x). This means the same code renders correctly at 64px
    (hardware), 180px (default Pygame), or any other resolution.

    Visual effects:
    - Hurry-zone blinking: departures the user might still catch blink
      their time columns with inverted amber/black colors.
    - Cancelled departures: destination alternates between the original
      text and "Fällt aus" (cancelled) every second.
    - Scrolling remarks: remarks that overflow their column scroll
      horizontally with pauses at each end.

    The renderer is stateless except for scroll timing — call render()
    each frame and it produces the correct image for the current moment.
    """

    def __init__(
        self,
        width: int = 1520,
        height: int = 180,
        font_header: str = "JetBrainsMono-Bold.ttf",
        font_main: str = "JetBrainsMono-Medium.ttf",
        font_remark: str = "JetBrainsMono-Regular.ttf",
        station_name_size: int = 20,
        header_size: int = 13,
        departure_size: int = 18,
        remark_size: int = 13,
        show_remarks: bool = True,
        show_items: int = 4,
    ) -> None:
        """Initialize the departure board renderer.

        Args:
            width: Display width in pixels. Default 1520 for Pygame preview.
            height: Display height in pixels. Default 180 for Pygame preview.
            font_header: Filename of the bold font used for headers and line
                names. Must exist in the project fonts/ directory.
            font_main: Filename of the medium-weight font used for departure
                text (destination, times, minutes).
            font_remark: Filename of the regular-weight font used for remarks.
            station_name_size: Base font size in pixels for the station name
                header. Scaled dynamically by display height.
            header_size: Base font size in pixels for column header labels
                (Linie, Ziel, Abfahrt, in Min). Scaled dynamically.
            departure_size: Base font size in pixels for departure rows.
                Overridden by dynamic sizing to fill available vertical space.
            remark_size: Base font size in pixels for remark text. Scaled
                dynamically by display height.
            show_remarks: Whether to display the scrolling remarks column.
                When False, the destination column expands to fill the space.
            show_items: Number of departure rows to display. Font size scales
                to fill the available height with this many rows.
        """
        self.width = width
        self.height = height

        # Base reference height is 128px (SSD1322 OLED native height at 2x).
        # All padding, gaps, and font sizes are multiplied by this scale
        # factor so the layout adapts to any display resolution.
        self.scale = height / 128
        station_name_size = max(6, round(station_name_size * self.scale))
        header_size = max(6, round(header_size * self.scale))
        remark_size = max(6, round(remark_size * self.scale))

        # Universal inter-element padding used for column gaps and margins.
        # Minimum 2px ensures readability even at very small scales.
        self.pad = max(2, round(8 * self.scale))

        # The station name lives in an amber bar at the top. Its height is
        # font size plus padding. first_row_y is where departure rows begin,
        # separated by a small gap below the header.
        station_name_pad = max(2, round(8 * self.scale))
        header_gap = max(1, round(2 * self.scale))
        self.station_name_height = station_name_size + station_name_pad
        self.first_row_y = self.station_name_height + header_gap

        # Departure font size is computed dynamically: divide available
        # vertical space (below header) by number of rows. This fills the
        # display evenly regardless of resolution.
        row_pad = max(2, round(4 * self.scale))
        available = height - self.first_row_y
        departure_size = max(6, int(available / show_items - row_pad))

        self.max_rows = show_items
        self.row_height = departure_size + row_pad

        # Fonts loaded from project fonts/ dir. Three weights: Bold for
        # headers/line names, Medium for departures, Regular for remarks.
        header_path = str(_FONTS_DIR / font_header)
        main_path = str(_FONTS_DIR / font_main)
        remark_path = str(_FONTS_DIR / font_remark)

        # Station name uses ExtraBold for visual hierarchy. Falls back to
        # Bold if ExtraBold variant doesn't exist.
        extrabold_path = str(
            _FONTS_DIR / font_header.replace("Bold", "ExtraBold")
        )
        try:
            self.font_station_name = ImageFont.truetype(
                extrabold_path, station_name_size
            )
        except OSError:
            self.font_station_name = ImageFont.truetype(
                header_path, station_name_size
            )
        self.font_header = ImageFont.truetype(header_path, header_size)
        # Mid-size font for clock and weather in header bar. Average of
        # header and station name sizes.
        info_size = max(6, round((header_size + station_name_size) // 2))
        self.font_info = ImageFont.truetype(header_path, info_size)
        self.font_departure = ImageFont.truetype(main_path, departure_size)
        self.font_linie = ImageFont.truetype(header_path, departure_size)
        self.font_remark = ImageFont.truetype(remark_path, remark_size)

        # Vertical layout
        self.header_y = self.first_row_y
        self.header_height = 0

        self.show_remarks = show_remarks

        # Scroll timer origin. Reset on station rotation so each station's
        # remarks start from beginning.
        self._scroll_start = time.time()

    def _truncate_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> str:
        """Truncate text with ellipsis if it exceeds max_width pixels.

        Args:
            text: The text string to potentially truncate.
            font: The PIL font used to measure text width.
            max_width: Maximum allowed width in pixels.

        Returns:
            The original text if it fits, or a truncated version with
            a ".." suffix.
        """
        if not text:
            return ""
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_width:
            return text
        # ".." (not "...") saves horizontal space on narrow displays
        ellipsis = ".."
        for end in range(len(text), 0, -1):
            candidate = text[:end] + ellipsis
            bbox = font.getbbox(candidate)
            if bbox[2] - bbox[0] <= max_width:
                return candidate
        return ellipsis

    def render(
        self,
        departures: list[Departure],
        station_name: str,
        walking_minutes: int = 5,
        weather: WeatherData | None = None,
        weather_page: int = 0,
        fetch_ok: bool = True,
    ) -> tuple[Image.Image, bool]:
        """Render a departure board image.

        Args:
            departures: List of Departure objects to display.
            station_name: Name of the station (shown at the top of the board).
            weather: Optional weather data to display on the left.

        Returns:
            Tuple of (PIL Image, scrolling_done) where scrolling_done is True
            when all remarks have completed at least one full scroll cycle.
        """
        img = Image.new("RGB", (self.width, self.height), BLACK)
        draw = ImageDraw.Draw(img)

        # Draw station name at the top
        self._draw_station_name(draw, station_name, weather, weather_page, fetch_ok)

        # Vertical 1px line between Linie and Ziel columns, matching real
        # BVG aesthetic.
        sep_x = int(self.width * 0.14)
        draw.line(
            [(sep_x, self.first_row_y), (sep_x, self.height)],
            fill=AMBER,
            width=1,
        )

        # Elapsed time since scroll started for positioning scrolling remarks.
        scroll_time = time.time() - self._scroll_start
        max_rows = self.max_rows
        # Tracks if all remarks completed one scroll cycle. Used to gate
        # station rotation.
        all_done = True
        for i, dep in enumerate(departures[:max_rows]):
            y = self.first_row_y + i * self.row_height
            row_done = self._draw_departure_row(
                img, draw, dep, y, scroll_time, walking_minutes
            )
            if not row_done:
                all_done = False

        return img, all_done

    def render_empty(
        self,
        station_name: str,
        lines: list[str],
        weather: WeatherData | None = None,
        weather_page: int = 0,
        fetch_ok: bool = True,
    ) -> Image.Image:
        """Render the station header with a 'no departures' message below."""
        img = Image.new("RGB", (self.width, self.height), BLACK)
        draw = ImageDraw.Draw(img)

        self._draw_station_name(draw, station_name, weather, weather_page, fetch_ok)

        # Center the message vertically within the departure area (below
        # the station name header bar) so it appears balanced on screen.
        area_top = self.first_row_y
        area_h = self.height - area_top
        cy = area_top + area_h // 2

        if lines:
            line_str = " / ".join(lines)
            msg = f"Keine Abfahrten: {line_str}"
        else:
            msg = "Keine Abfahrten"

        msg = self._truncate_text(
            msg, self.font_departure, self.width - self.pad * 2
        )
        bbox = self.font_departure.getbbox(msg)
        text_w = bbox[2] - bbox[0]
        draw.text(
            ((self.width - text_w) // 2, cy),
            msg,
            fill=AMBER,
            font=self.font_departure,
            anchor="lm",
        )

        return img

    def _draw_station_name(
        self,
        draw: ImageDraw.ImageDraw,
        station_name: str,
        weather: WeatherData | None = None,
        weather_page: int = 0,
        fetch_ok: bool = True,
    ) -> None:
        """Draw the station name centered on a full-width amber block, with clock on the right, weather on the left, and a connection status dot next to the clock."""
        # Full-width amber rectangle as header background, matching real
        # BVG signage.
        draw.rectangle(
            [(0, 0), (self.width, self.station_name_height)],
            fill=AMBER,
        )
        cy = self.station_name_height // 2
        margin = max(2, round(4 * self.scale))

        # Current time (left-aligned)
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        draw.text(
            (margin, cy),
            time_str,
            fill=BLACK,
            font=self.font_info,
            anchor="lm",
        )

        # Connection status dot at the far right, weather text shifted left
        # to make room. Dot is always present; when connected it's BLACK
        # (invisible against amber bar), when disconnected it blinks.
        dot_radius = max(2, round(3 * self.scale))
        dot_gap = max(2, round(4 * self.scale))
        dot_cx = self.width - margin - dot_radius
        dot_cy = cy
        if fetch_ok:
            dot_fill = BLACK
        else:
            dot_fill = BLACK if time.time() % BLINK_PERIOD < BLINK_PERIOD / 2 else AMBER
        draw.ellipse(
            [
                (dot_cx - dot_radius, dot_cy - dot_radius),
                (dot_cx + dot_radius, dot_cy + dot_radius),
            ],
            fill=dot_fill,
        )

        # Weather alternates between temperature and precipitation on each
        # station rotation. weather_page % 2 toggles views.
        # Right-aligned to the left of the status dot.
        weather_anchor_x = dot_cx - dot_radius - dot_gap
        if weather is not None:
            temp_str = (
                f"{weather.current_temp:.0f}C"
                f" {weather.daily_low:.0f}/{weather.daily_high:.0f}C"
            )
            precip_str = weather.precip_summary
            if precip_str and weather_page % 2 == 1:
                weather_str = precip_str
            else:
                weather_str = temp_str
            draw.text(
                (weather_anchor_x, cy),
                weather_str,
                fill=BLACK,
                font=self.font_info,
                anchor="rm",
            )
        # Station name (centered)
        truncate_margin = max(10, round(20 * self.scale))
        text = self._truncate_text(
            station_name,
            self.font_station_name,
            self.width - truncate_margin,
        )
        if text:
            cx = self.width // 2
            draw.text(
                (cx, cy),
                text,
                fill=BLACK,
                font=self.font_station_name,
                anchor="mm",
            )

    def _draw_header(self, draw: ImageDraw.ImageDraw) -> None:
        """Draw column header labels (Linie, Ziel, Abfahrt, in Min) below the station name bar."""
        y = self.header_y
        draw.text(
            (int(self.width * COL_LINIE), y),
            "Linie",
            fill=AMBER,
            font=self.font_header,
        )
        draw.text(
            (int(self.width * COL_ZIEL), y),
            "Ziel",
            fill=AMBER,
            font=self.font_header,
        )
        draw.text(
            (int(self.width * COL_DEP_TIME), y),
            "Abfahrt",
            fill=AMBER,
            font=self.font_header,
        )
        # "in Min " is right-aligned
        text = "in Min"
        bbox = draw.textbbox((0, 0), text, font=self.font_header)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (int(self.width * COL_ABFAHRT_IN) - text_w, y),
            text,
            fill=AMBER,
            font=self.font_header,
        )

    def _draw_scrolling_text(
        self,
        img: Image.Image,
        text: str,
        font: ImageFont.FreeTypeFont,
        x: int,
        y: int,
        max_width: int,
        scroll_time: float,
    ) -> bool:
        """Draw text, scrolling horizontally if it overflows.

        Returns True if the text fits or has completed one full scroll.
        """
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]

        if text_w <= max_width:
            draw = ImageDraw.Draw(img)
            draw.text((x, y), text, fill=AMBER, font=font)
            return True

        # Total scroll distance = text overflow beyond column.
        # Duration = distance / speed.
        scroll_distance = text_w - max_width
        scroll_duration = scroll_distance / SCROLL_SPEED
        # One scroll cycle: pause -> scroll -> pause.
        # scroll_done is True after full cycle.
        cycle = SCROLL_PAUSE + scroll_duration + SCROLL_PAUSE

        scroll_done = scroll_time >= cycle

        if scroll_time < SCROLL_PAUSE:
            offset = 0
        elif scroll_time < SCROLL_PAUSE + scroll_duration:
            offset = int((scroll_time - SCROLL_PAUSE) * SCROLL_SPEED)
        else:
            offset = scroll_distance
        offset = max(0, min(int(offset), scroll_distance))

        # Render full text onto temp strip, crop visible window. Avoids
        # clipping artifacts.
        temp = Image.new("RGB", (text_w, self.row_height), BLACK)
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.text((0, 0), text, fill=AMBER, font=font)

        visible = temp.crop((offset, 0, offset + max_width, self.row_height))
        img.paste(visible, (x, y))
        return scroll_done

    def _draw_departure_row(
        self,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        dep: Departure,
        y: int,
        scroll_time: float,
        walking_minutes: int = 5,
    ) -> bool:
        """Draw a single departure row.

        Returns True if all scrolling text in this row has completed at least one cycle.
        """
        x_linie = int(self.width * COL_LINIE)
        x_ziel = int(self.width * COL_ZIEL)
        x_time = self.width - self.pad
        pad = self.pad

        # Reserve space for widest possible minutes display '00+00m'.
        # Ensures column alignment regardless of digit count.
        _bb = self.font_departure.getbbox
        min_area_w = (
            (_bb("00")[2] - _bb("00")[0])
            + (_bb("+00")[2] - _bb("+00")[0])
            + (_bb("m")[2] - _bb("m")[0])
        )
        dep_time_w = _bb("00:00")[2] - _bb("00:00")[0]
        x_dep_time = x_time - min_area_w - pad - dep_time_w

        # Hurry zone: departures within [walking_minutes-3, walking_minutes]
        # blink. First half of BLINK_PERIOD = inverted, second = normal.
        # Cancelled departures never blink.
        minutes = dep.minutes_until
        hurry_threshold = max(0, walking_minutes - 3)
        blink_on = (
            not dep.is_cancelled
            and minutes is not None
            and hurry_threshold <= minutes <= walking_minutes
            and time.time() % BLINK_PERIOD < BLINK_PERIOD / 2
        )

        max_w_linie = x_ziel - x_linie - pad

        # Linie (bold)
        line_text = self._truncate_text(
            dep.line_name or "",
            self.font_linie,
            max_w_linie,
        )
        if line_text:
            draw.text((x_linie, y), line_text, fill=AMBER, font=self.font_linie)

        scroll_done = True
        if self.show_remarks:
            x_remarks = int(self.width * COL_REMARKS)
            max_w_ziel = x_remarks - x_ziel - pad
            max_w_remarks = (x_dep_time - x_remarks) - pad
        else:
            max_w_ziel = x_dep_time - x_ziel - pad

        # Cancelled departures alternate between original destination and
        # 'Fällt aus' every second, preserving info while signaling
        # cancellation.
        if dep.is_cancelled and time.time() % BLINK_PERIOD >= BLINK_PERIOD / 2:
            ziel_text = "Fällt aus"
        else:
            ziel_text = self._truncate_text(
                dep.direction or "",
                self.font_departure,
                max_w_ziel,
            )
        if ziel_text:
            draw.text(
                (x_ziel, y), ziel_text, fill=AMBER, font=self.font_departure
            )

        # Remarks (fixed column, scrolling if overflow)
        if self.show_remarks and dep.remarks and max_w_remarks > 20:
            remark_text = ", ".join(dep.remarks)
            scroll_done = self._draw_scrolling_text(
                img,
                remark_text,
                self.font_departure,
                x_remarks,
                y,
                max_w_remarks,
                scroll_time,
            )

        # Departure time column (actual time = planned + delay)
        dep_ts = dep.when or dep.planned_when
        if dep_ts is not None:
            dep_dt = datetime.fromisoformat(dep_ts).astimezone()
            dep_time_text = dep_dt.strftime("%H:%M")
        else:
            dep_time_text = "--:--"

        # Split into three aligned parts: number, "min", delay
        num_str = str(minutes) if minutes is not None else "--"
        min_label = "m"
        delay_text = f"+{dep.delay_minutes}" if dep.delay_minutes > 0 else ""

        # Right-aligned minutes layout, right-to-left: [number][+delay][m].
        # Number right-aligned in 2-digit slot for visual alignment.
        two_digit_bbox = self.font_departure.getbbox("00")
        two_digit_w = two_digit_bbox[2] - two_digit_bbox[0]
        label_bbox = self.font_departure.getbbox(min_label)
        label_w = label_bbox[2] - label_bbox[0]
        num_bbox = self.font_departure.getbbox(num_str)
        num_w = num_bbox[2] - num_bbox[0]
        delay_w = 0
        if delay_text:
            delay_bbox = self.font_departure.getbbox(delay_text)
            delay_w = delay_bbox[2] - delay_bbox[0]

        label_x = x_time - label_w  # "m" right-aligned to edge
        delay_x = label_x - delay_w  # "+2" left of "m"
        num_x = delay_x - num_w  # number left of delay
        num_slot_x = delay_x - two_digit_w  # 2-digit slot left edge

        # Ensure gap between dep time and minutes area
        dep_time_bbox_m = self.font_departure.getbbox("00:00")
        dep_time_end = (
            x_dep_time + (dep_time_bbox_m[2] - dep_time_bbox_m[0]) + pad
        )
        if num_slot_x < dep_time_end:
            shift = dep_time_end - num_slot_x
            num_slot_x += shift
            num_x += shift
            delay_x += shift
            label_x += shift

        # Hurry-zone blink ON: amber rectangles behind text, text in black.
        # Creates inverse-video effect alternating with normal rendering.
        if blink_on:
            blink_margin = max(1, round(2 * self.scale))
            dt_bbox = self.font_departure.getbbox(dep_time_text)
            dt_w = dt_bbox[2] - dt_bbox[0]
            draw.rectangle(
                [
                    (x_dep_time - blink_margin, y + dt_bbox[1] - blink_margin),
                    (
                        x_dep_time + dt_w + blink_margin,
                        y + dt_bbox[3] + blink_margin,
                    ),
                ],
                fill=AMBER,
            )
            draw.text(
                (x_dep_time, y),
                dep_time_text,
                fill=BLACK,
                font=self.font_departure,
            )
            # Minutes + delay text highlight
            full_min_text = num_str + delay_text + min_label
            ft_bbox = self.font_departure.getbbox(full_min_text)
            draw.rectangle(
                [
                    (num_slot_x - blink_margin, y + ft_bbox[1] - blink_margin),
                    (
                        x_time + blink_margin,
                        y + ft_bbox[3] + blink_margin,
                    ),
                ],
                fill=AMBER,
            )
            draw.text((num_x, y), num_str, fill=BLACK, font=self.font_departure)
            if delay_text:
                draw.text(
                    (delay_x, y),
                    delay_text,
                    fill=BLACK,
                    font=self.font_departure,
                )
            draw.text(
                (label_x, y), min_label, fill=BLACK, font=self.font_departure
            )
        else:
            draw.text(
                (x_dep_time, y),
                dep_time_text,
                fill=AMBER,
                font=self.font_departure,
            )
            draw.text((num_x, y), num_str, fill=AMBER, font=self.font_departure)
            if delay_text:
                draw.text(
                    (delay_x, y),
                    delay_text,
                    fill=AMBER,
                    font=self.font_departure,
                )
            draw.text(
                (label_x, y), min_label, fill=AMBER, font=self.font_departure
            )

        return scroll_done


def run_render_test(config=None) -> str:
    """Render mock departures to test_output.png and return the file path.

    Creates mock Departure objects (no API needed), renders them via
    DepartureRenderer, and saves to test_output.png in the project root.
    Uses config for display size and font settings if provided.
    """
    # Mock departures: normal (S7, S5), delayed (+2min S7), cancelled (RE1).
    # 5-min departure falls in hurry zone.
    now = datetime.now(timezone.utc)
    departures = [
        Departure(
            line_name="S7",
            line_product="suburban",
            direction="Ahrensfelde Bhf (Berlin)",
            when=(now + timedelta(minutes=5)).isoformat(),
            planned_when=(now + timedelta(minutes=5)).isoformat(),
            delay_seconds=0,
            platform="1",
            remarks=["Fahrradmitnahme möglich"],
            is_cancelled=False,
        ),
        Departure(
            line_name="S5",
            line_product="suburban",
            direction="Strausberg Bhf",
            when=(now + timedelta(minutes=8)).isoformat(),
            planned_when=(now + timedelta(minutes=8)).isoformat(),
            delay_seconds=0,
            platform="1",
            remarks=["Fahrradmitnahme möglich"],
            is_cancelled=False,
        ),
        Departure(
            line_name="S7",
            line_product="suburban",
            direction="Potsdam Hauptbahnhof",
            when=(now + timedelta(minutes=14)).isoformat(),
            planned_when=(now + timedelta(minutes=12)).isoformat(),
            delay_seconds=120,
            platform="2",
            remarks=["Fahrradmitnahme möglich"],
            is_cancelled=False,
        ),
        Departure(
            line_name="RE1",
            line_product="regional",
            direction="Frankfurt (Oder)",
            when=(now + timedelta(minutes=18)).isoformat(),
            planned_when=(now + timedelta(minutes=18)).isoformat(),
            delay_seconds=0,
            platform="3",
            remarks=[],
            is_cancelled=True,
        ),
    ]

    mock_weather = WeatherData(
        current_temp=4,
        daily_low=1,
        daily_high=8,
        precip_next_12h=[
            0.0,
            0.0,
            0.1,
            0.3,
            0.5,
            0.2,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
    )

    if config is not None:
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
    else:
        renderer = DepartureRenderer()
    station_name = "S Savignyplatz (Berlin)"
    walking_minutes = 5
    if config is not None and config.stations:
        station_name = (
            config.stations[0].name or f"Station {config.stations[0].id}"
        )
        walking_minutes = config.stations[0].walking_minutes

    # Monkey-patch time.time() to force blink ON. At t=0.0, blink condition
    # is True. Makes static test image deterministic.
    blink_on_time = 0.0
    import time as _time_mod
    _original_time = _time_mod.time
    _time_mod.time = lambda: blink_on_time
    try:
        renderer._scroll_start = blink_on_time
        img, _ = renderer.render(
            departures, station_name, walking_minutes, mock_weather,
        )
    finally:
        _time_mod.time = _original_time

    mode = config.display.mode if config is not None else "pygame"
    # RGB->grayscale->RGB round-trip simulates 4-bit SSD1322 OLED output.
    if mode == "ssd1322":
        img = img.convert("L").convert("RGB")
    assets_dir = _ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    output_path = str(assets_dir / f"test_output_{mode}.png")
    img.save(output_path)
    return output_path
