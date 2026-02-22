"""PIL-based departure board renderer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from infodisplay.models import Departure

# Project root (three levels up from this file)
_ROOT = Path(__file__).resolve().parent.parent.parent
_FONTS_DIR = _ROOT / "fonts"
_ASSETS_DIR = _ROOT / "assets"

# Amber color matching real BVG departure boards
AMBER = (255, 170, 0)
BLACK = (0, 0, 0)

# Column positions as percentage of display width
COL_LINIE = 0.02
COL_ZIEL = 0.16
COL_REMARKS = 0.35
COL_ABFAHRT_VON = 0.54
COL_ABFAHRT_IN = 0.98  # right-aligned


class DepartureRenderer:
    """Renders a departure board as a PIL Image."""

    def __init__(
        self,
        width: int = 1520,
        height: int = 180,
        header_size: int = 16,
        departure_size: int = 16,
        remark_size: int = 13,
    ) -> None:
        self.width = width
        self.height = height

        # Load fonts
        bold_path = str(_FONTS_DIR / "DotMatrix-Bold.ttf")
        regular_path = str(_FONTS_DIR / "DotMatrix-Regular.ttf")

        self.font_header = ImageFont.truetype(bold_path, header_size)
        self.font_departure = ImageFont.truetype(regular_path, departure_size)
        self.font_remark = ImageFont.truetype(regular_path, remark_size)

        # Load S-Bahn icon
        icon_path = _ASSETS_DIR / "sbahn_icon.png"
        if icon_path.exists():
            self.sbahn_icon = Image.open(icon_path).convert("RGBA")
            # Resize to match departure font height
            self.sbahn_icon = self.sbahn_icon.resize(
                (departure_size, departure_size), Image.LANCZOS
            )
        else:
            self.sbahn_icon = None

        # Row layout
        self.header_height = header_size + 6
        self.separator_y = self.header_height + 2
        self.first_row_y = self.separator_y + 4
        self.row_height = departure_size + 6

    def render(self, departures: list[Departure], station_name: str) -> Image.Image:
        """Render a departure board image.

        Args:
            departures: List of Departure objects to display.
            station_name: Name of the station (shown in "Abfahrt von" column).

        Returns:
            PIL Image with the rendered departure board.
        """
        img = Image.new("RGB", (self.width, self.height), BLACK)
        draw = ImageDraw.Draw(img)

        # Draw header row
        self._draw_header(draw)

        # Draw thin horizontal separator line
        draw.line(
            [(0, self.separator_y), (self.width, self.separator_y)],
            fill=AMBER,
            width=1,
        )

        # Draw departure rows
        max_rows = (self.height - self.first_row_y) // self.row_height
        for i, dep in enumerate(departures[:max_rows]):
            y = self.first_row_y + i * self.row_height
            self._draw_departure_row(img, draw, dep, station_name, y)

        return img

    def _draw_header(self, draw: ImageDraw.ImageDraw) -> None:
        """Draw the header row with column labels."""
        y = 4
        draw.text(
            (int(self.width * COL_LINIE), y), "Linie",
            fill=AMBER, font=self.font_header,
        )
        draw.text(
            (int(self.width * COL_ZIEL), y), "Ziel",
            fill=AMBER, font=self.font_header,
        )
        draw.text(
            (int(self.width * COL_ABFAHRT_VON), y), "Abfahrt von",
            fill=AMBER, font=self.font_header,
        )
        # "Abfahrt in" is right-aligned
        text = "Abfahrt in"
        bbox = draw.textbbox((0, 0), text, font=self.font_header)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (int(self.width * COL_ABFAHRT_IN) - text_w, y), text,
            fill=AMBER, font=self.font_header,
        )

    def _draw_departure_row(
        self,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        dep: Departure,
        station_name: str,
        y: int,
    ) -> None:
        """Draw a single departure row."""
        # Linie
        draw.text(
            (int(self.width * COL_LINIE), y), dep.line_name,
            fill=AMBER, font=self.font_departure,
        )

        # Ziel (destination)
        draw.text(
            (int(self.width * COL_ZIEL), y), dep.direction,
            fill=AMBER, font=self.font_departure,
        )

        # Remarks (smaller font, y-offset down a few pixels)
        if dep.remarks:
            remark_text = ", ".join(dep.remarks)
            remark_y_offset = (self.row_height - self.font_remark.size) // 2
            draw.text(
                (int(self.width * COL_REMARKS), y + remark_y_offset), remark_text,
                fill=AMBER, font=self.font_remark,
            )

        # Abfahrt von (station name + S-Bahn icon)
        x_von = int(self.width * COL_ABFAHRT_VON)
        draw.text((x_von, y), station_name, fill=AMBER, font=self.font_departure)

        # Add S-Bahn icon after station name if product is suburban
        if self.sbahn_icon and dep.line_product == "suburban":
            bbox = draw.textbbox((x_von, y), station_name, font=self.font_departure)
            icon_x = bbox[2] + 4
            icon_y = y + (self.row_height - self.sbahn_icon.height) // 2
            img.paste(
                self.sbahn_icon,
                (icon_x, icon_y),
                self.sbahn_icon,  # use alpha channel as mask
            )

        # Abfahrt in (right-aligned, "X min" with optional delay)
        minutes = dep.minutes_until
        if minutes is not None:
            time_text = f"{minutes} min"
        else:
            time_text = "-- min"

        if dep.delay_minutes > 0:
            time_text += f" (+{dep.delay_minutes})"

        bbox = draw.textbbox((0, 0), time_text, font=self.font_departure)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (int(self.width * COL_ABFAHRT_IN) - text_w, y), time_text,
            fill=AMBER, font=self.font_departure,
        )


def run_render_test() -> str:
    """Render mock departures to test_output.png and return the file path.

    Creates mock Departure objects (no API needed), renders them via
    DepartureRenderer, and saves to test_output.png in the project root.
    """
    now = datetime.now(timezone.utc)
    departures = [
        Departure(
            line_name="S7", line_product="suburban",
            direction="S Ahrensfelde Bhf (Berlin)",
            when=(now + timedelta(minutes=1)).isoformat(),
            planned_when=(now + timedelta(minutes=1)).isoformat(),
            delay_seconds=0, platform="1",
            remarks=["Fahrradmitnahme möglich"], is_cancelled=False,
        ),
        Departure(
            line_name="S5", line_product="suburban",
            direction="S Strausberg Bhf",
            when=(now + timedelta(minutes=2)).isoformat(),
            planned_when=(now + timedelta(minutes=2)).isoformat(),
            delay_seconds=0, platform="1",
            remarks=["Fahrradmitnahme möglich"], is_cancelled=False,
        ),
        Departure(
            line_name="S7", line_product="suburban",
            direction="S Potsdam Hauptbahnhof",
            when=(now + timedelta(minutes=5)).isoformat(),
            planned_when=(now + timedelta(minutes=3)).isoformat(),
            delay_seconds=120, platform="2",
            remarks=["Fahrradmitnahme möglich"], is_cancelled=False,
        ),
        Departure(
            line_name="S3", line_product="suburban",
            direction="S Erkner Bhf",
            when=(now + timedelta(minutes=7)).isoformat(),
            planned_when=(now + timedelta(minutes=7)).isoformat(),
            delay_seconds=0, platform="1",
            remarks=["Fahrradmitnahme möglich"], is_cancelled=False,
        ),
    ]

    renderer = DepartureRenderer()
    img = renderer.render(departures, "S Savignyplatz (Berlin)")

    output_path = str(_ROOT / "test_output.png")
    img.save(output_path)
    return output_path
