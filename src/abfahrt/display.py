"""Pygame display window for the departure board."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Project root directory (three levels up: display.py -> abfahrt -> src -> root)
_ROOT = Path(__file__).resolve().parent.parent.parent
# Font directory at project root, shared by all display backends
_FONTS_DIR = _ROOT / "fonts"

# Amber RGB matching real BVG departure board color
AMBER = (255, 170, 0)
# Pure black background
BLACK = (0, 0, 0)


class DepartureDisplay:
    """Manages the Pygame window that displays the departure board."""

    def __init__(self, width: int = 1520, height: int = 180, fullscreen: bool = False) -> None:
        """Initialize the Pygame display window.

        Args:
            width: Window width in pixels. Default 1520 matches the renderer
                default for a wide departure board preview.
            height: Window height in pixels. Default 180 matches the renderer
                default.
            fullscreen: If True, open in fullscreen mode instead of a windowed
                display. Useful for kiosk-style setups.
        """
        pygame.init()
        flags = 0
        if fullscreen:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("BVG Abfahrtsanzeige")
        self.width = width
        self.height = height
        mode = "fullscreen" if fullscreen else f"{width}x{height}"
        logger.info("Pygame display initialized (%s)", mode)

    def update(self, pil_image: Image.Image) -> None:
        """Convert a PIL Image to a Pygame surface and display it."""
        # PIL images use raw RGB bytes. Pygame ingests them directly via
        # fromstring().
        raw = pil_image.tobytes()
        surface = pygame.image.fromstring(raw, pil_image.size, pil_image.mode)
        self.screen.blit(surface, (0, 0))
        pygame.display.flip()

    def handle_events(self) -> bool:
        """Process Pygame events. Returns False if the app should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.info("Received QUIT event")
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                logger.info("Received ESC keypress")
                return False
        return True

    def close(self) -> None:
        """Shut down the Pygame display."""
        logger.info("Closing Pygame display")
        pygame.quit()


def render_error(message: str, width: int = 1520, height: int = 180) -> Image.Image:
    """Render a centered error message on a black background in amber text."""
    img = Image.new("RGB", (width, height), BLACK)
    draw = ImageDraw.Draw(img)

    font_path = str(_FONTS_DIR / "JetBrainsMono-Bold.ttf")
    try:
        font = ImageFont.truetype(font_path, 20)
    except OSError:
        # Falls back to Pillow's built-in bitmap font if .ttf missing
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), message, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.text((x, y), message, fill=AMBER, font=font)
    return img


def render_boot_screen(status: str, width: int = 1520, height: int = 180) -> Image.Image:
    """Render a boot/splash screen with the app title, loading status, and version."""
    from abfahrt import __version__

    img = Image.new("RGB", (width, height), BLACK)
    draw = ImageDraw.Draw(img)

    def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        try:
            return ImageFont.truetype(str(_FONTS_DIR / name), size)
        except OSError:
            return ImageFont.load_default()

    title_font = _load_font("JetBrainsMono-ExtraBold.ttf", int(height * 0.40))
    status_font = _load_font("JetBrainsMono-Medium.ttf", int(height * 0.15))
    small_font = _load_font("JetBrainsMono-Regular.ttf", int(height * 0.12))

    # Title "Abfahrt!" — centered, upper third
    title = "Abfahrt!"
    tb = draw.textbbox((0, 0), title, font=title_font)
    tx = (width - (tb[2] - tb[0])) // 2
    ty = int(height * 0.08)
    draw.text((tx, ty), title, fill=AMBER, font=title_font)

    # Status line — centered below title
    sb = draw.textbbox((0, 0), status, font=status_font)
    sx = (width - (sb[2] - sb[0])) // 2
    sy = ty + (tb[3] - tb[1]) + int(height * 0.08)
    draw.text((sx, sy), status, fill=AMBER, font=status_font)

    # Version — bottom-right
    version_str = f"v{__version__}"
    vb = draw.textbbox((0, 0), version_str, font=small_font)
    margin = int(height * 0.05)
    draw.text((width - (vb[2] - vb[0]) - margin, height - (vb[3] - vb[1]) - margin),
              version_str, fill=AMBER, font=small_font)

    # GitHub URL — bottom-left
    url = "github.com/ydixken/abfahrt"
    draw.text((margin, height - (vb[3] - vb[1]) - margin), url, fill=AMBER, font=small_font)

    return img
