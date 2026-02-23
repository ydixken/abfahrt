"""Pygame display window for the departure board."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
_FONTS_DIR = _ROOT / "fonts"

AMBER = (255, 170, 0)
BLACK = (0, 0, 0)


class DepartureDisplay:
    """Manages the Pygame window that displays the departure board."""

    def __init__(self, width: int = 1520, height: int = 180, fullscreen: bool = False) -> None:
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
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), message, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.text((x, y), message, fill=AMBER, font=font)
    return img
