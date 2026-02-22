"""PIL-based departure board renderer."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from infodisplay.models import Departure
from infodisplay.weather import WeatherData

# Project root (three levels up from this file)
_ROOT = Path(__file__).resolve().parent.parent.parent
_FONTS_DIR = _ROOT / "fonts"

# Amber color matching real BVG departure boards
AMBER = (255, 170, 0)
BLACK = (0, 0, 0)

# Column positions as percentage of display width
COL_LINIE = 0.02
COL_ZIEL = 0.16
COL_REMARKS = 0.58
COL_DEP_TIME = 0.64
COL_ABFAHRT_IN = 0.98  # right-aligned

# Scrolling parameters
SCROLL_SPEED = 30  # pixels per second
SCROLL_PAUSE = 2.0  # seconds to pause at each end

# Blink parameters
BLINK_PERIOD = 2.0  # full blink cycle in seconds (on + off)


class DepartureRenderer:
    """Renders a departure board as a PIL Image."""

    def __init__(
        self,
        width: int = 1520,
        height: int = 180,
        station_name_size: int = 20,
        header_size: int = 13,
        departure_size: int = 18,
        remark_size: int = 13,
        show_remarks: bool = True,
    ) -> None:
        self.width = width
        self.height = height

        # Dynamic scaling: base sizes are designed for 128px height
        self.scale = height / 128
        station_name_size = max(6, round(station_name_size * self.scale))
        header_size = max(6, round(header_size * self.scale))
        departure_size = max(6, round(departure_size * self.scale))
        remark_size = max(6, round(remark_size * self.scale))

        # Scaled padding used throughout layout
        self.pad = max(2, round(8 * self.scale))

        # Load fonts (FF Transit — official BVG typeface)
        header_path = str(_FONTS_DIR / "Transit_Wide_Bold.ttf")
        main_path = str(_FONTS_DIR / "Transit_Bold.ttf")
        remark_path = str(_FONTS_DIR / "Transit_Condensed_Normal.ttf")

        self.font_station_name = ImageFont.truetype(
            header_path, station_name_size
        )
        self.font_header = ImageFont.truetype(header_path, header_size)
        self.font_departure = ImageFont.truetype(main_path, departure_size)
        self.font_linie = ImageFont.truetype(header_path, departure_size)
        self.font_remark = ImageFont.truetype(remark_path, remark_size)

        # Vertical layout (scaled)
        self.station_name_height = station_name_size + max(
            2, round(8 * self.scale)
        )
        self.header_y = self.station_name_height + max(1, round(2 * self.scale))
        self.header_height = 0
        self.first_row_y = self.header_y
        self.row_height = departure_size + max(2, round(4 * self.scale))

        self.show_remarks = show_remarks

        # Scroll start time
        self._scroll_start = time.time()

    def _truncate_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> str:
        """Truncate text with ellipsis if it exceeds max_width pixels."""
        if not text:
            return ""
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_width:
            return text
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
        self._draw_station_name(draw, station_name, weather)

        # Vertical separator between Linie and Ziel columns
        sep_x = int(self.width * 0.14)
        draw.line(
            [(sep_x, self.first_row_y), (sep_x, self.height)],
            fill=AMBER,
            width=1,
        )

        # Draw departure rows
        scroll_time = time.time() - self._scroll_start
        max_rows = (self.height - self.first_row_y) // self.row_height
        all_done = True
        for i, dep in enumerate(departures[:max_rows]):
            y = self.first_row_y + i * self.row_height
            row_done = self._draw_departure_row(
                img, draw, dep, y, scroll_time, walking_minutes
            )
            if not row_done:
                all_done = False

        return img, all_done

    def _draw_station_name(
        self,
        draw: ImageDraw.ImageDraw,
        station_name: str,
        weather: WeatherData | None = None,
    ) -> None:
        """Draw the station name centered on a full-width amber block, with clock on the right and weather on the left."""
        draw.rectangle(
            [(0, 0), (self.width, self.station_name_height)],
            fill=AMBER,
        )
        cy = self.station_name_height // 2
        margin = max(2, round(4 * self.scale))

        # Weather info (left-aligned)
        if weather is not None:
            weather_str = (
                f"{weather.current_temp:.0f}°"
                f" {weather.daily_low:.0f}/{weather.daily_high:.0f}°"
                f" {weather.precip_summary}"
            )
            draw.text(
                (margin, cy),
                weather_str,
                fill=BLACK,
                font=self.font_departure,
                anchor="lm",
            )

        # Current time (right-aligned)
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        draw.text(
            (self.width - margin, cy),
            time_str,
            fill=BLACK,
            font=self.font_departure,
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
        """Draw the column header row below the station name."""
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

        # Text overflows — scroll right once, then hold at end
        scroll_distance = text_w - max_width
        scroll_duration = scroll_distance / SCROLL_SPEED
        cycle = SCROLL_PAUSE + scroll_duration + SCROLL_PAUSE

        scroll_done = scroll_time >= cycle

        if scroll_time < SCROLL_PAUSE:
            offset = 0
        elif scroll_time < SCROLL_PAUSE + scroll_duration:
            offset = int((scroll_time - SCROLL_PAUSE) * SCROLL_SPEED)
        else:
            offset = scroll_distance
        offset = max(0, min(int(offset), scroll_distance))

        # Render full text onto a temp strip, then crop the visible window
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
        x_time = int(self.width * COL_ABFAHRT_IN)
        x_dep_time = int(self.width * COL_DEP_TIME)
        pad = self.pad

        # Blink state for hurry zone (walking_minutes - 3 to walking_minutes)
        minutes = dep.minutes_until
        hurry_threshold = max(0, walking_minutes - 3)
        blink_on = (
            minutes is not None
            and hurry_threshold <= minutes <= walking_minutes
            and dep.delay_minutes == 0
            and time.time() % BLINK_PERIOD < BLINK_PERIOD / 2
        )

        max_w_linie = x_ziel - x_linie - pad

        # Linie (bold)
        line_text = self._truncate_text(
            dep.line_name or "", self.font_linie, max_w_linie,
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

        # Ziel (destination)
        ziel_text = self._truncate_text(
            dep.direction or "", self.font_departure, max_w_ziel,
        )
        if ziel_text:
            draw.text((x_ziel, y), ziel_text, fill=AMBER, font=self.font_departure)

        # Remarks (fixed column, scrolling if overflow)
        if self.show_remarks and dep.remarks and max_w_remarks > 20:
            remark_text = ", ".join(dep.remarks)
            scroll_done = self._draw_scrolling_text(
                img, remark_text, self.font_departure,
                x_remarks, y, max_w_remarks, scroll_time,
            )

        # Departure time column (actual time = planned + delay)
        dep_ts = dep.when or dep.planned_when
        if dep_ts is not None:
            dep_dt = datetime.fromisoformat(dep_ts).astimezone()
            dep_time_text = dep_dt.strftime("%H:%M")
        else:
            dep_time_text = "--:--"

        # Minutes until departure (right-aligned)
        if minutes is not None:
            min_text = f"{minutes} min"
        else:
            min_text = "-- min"

        delay_text = f" (+{dep.delay_minutes})" if dep.delay_minutes > 0 else ""

        # Measure widths
        min_bbox = self.font_departure.getbbox(min_text)
        min_w = min_bbox[2] - min_bbox[0]
        delay_w = 0
        if delay_text:
            delay_bbox = self.font_departure.getbbox(delay_text)
            delay_w = delay_bbox[2] - delay_bbox[0]

        # Position: right-aligned to edge, but not overlapping dep time column
        dep_time_bbox_m = self.font_departure.getbbox("00:00")
        dep_time_end = x_dep_time + (dep_time_bbox_m[2] - dep_time_bbox_m[0]) + pad
        total_w = min_w + delay_w
        tx = max(dep_time_end, x_time - total_w)

        # Blink only the text of dep time + minutes (not background)
        if blink_on:
            blink_margin = max(1, round(2 * self.scale))
            # Dep time text highlight
            dt_bbox = self.font_departure.getbbox(dep_time_text)
            dt_w = dt_bbox[2] - dt_bbox[0]
            dt_h = dt_bbox[3] - dt_bbox[1]
            draw.rectangle(
                [(x_dep_time - blink_margin, y + dt_bbox[1]),
                 (x_dep_time + dt_w + blink_margin, y + dt_bbox[1] + dt_h + blink_margin)],
                fill=AMBER,
            )
            draw.text((x_dep_time, y), dep_time_text, fill=BLACK, font=self.font_departure)
            # Minutes text highlight
            full_text = min_text + delay_text
            ft_bbox = self.font_departure.getbbox(full_text)
            ft_h = ft_bbox[3] - ft_bbox[1]
            draw.rectangle(
                [(tx - blink_margin, y + ft_bbox[1]),
                 (tx + total_w + blink_margin, y + ft_bbox[1] + ft_h + blink_margin)],
                fill=AMBER,
            )
            draw.text((tx, y), min_text, fill=BLACK, font=self.font_departure)
            if delay_text:
                draw.text((tx + min_w, y), delay_text, fill=BLACK, font=self.font_departure)
        else:
            draw.text((x_dep_time, y), dep_time_text, fill=AMBER, font=self.font_departure)
            draw.text((tx, y), min_text, fill=AMBER, font=self.font_departure)
            if delay_text:
                draw.text((tx + min_w, y), delay_text, fill=AMBER, font=self.font_departure)

        return scroll_done


def run_render_test() -> str:
    """Render mock departures to test_output.png and return the file path.

    Creates mock Departure objects (no API needed), renders them via
    DepartureRenderer, and saves to test_output.png in the project root.
    """
    now = datetime.now(timezone.utc)
    departures = [
        Departure(
            line_name="S7",
            line_product="suburban",
            direction="S Ahrensfelde Bhf (Berlin)",
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
            direction="S Strausberg Bhf",
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
            direction="S Potsdam Hauptbahnhof",
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
            is_cancelled=False,
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

    renderer = DepartureRenderer()
    img, _ = renderer.render(
        departures, "S Savignyplatz (Berlin)", weather=mock_weather
    )

    output_path = str(_ROOT / "test_output.png")
    img.save(output_path)
    return output_path
