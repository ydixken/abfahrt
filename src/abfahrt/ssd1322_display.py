"""SSD1322 OLED display backend using luma.oled.

Requires the 'hardware' extra: pip install -e ".[hardware]"
"""

from __future__ import annotations

import logging

from PIL import Image

logger = logging.getLogger(__name__)


class SSD1322Display:
    """Drive an SSD1322 256x64 OLED via SPI using luma.oled."""

    def __init__(self, width: int = 256, height: int = 64) -> None:
        """Initialize the SSD1322 OLED display over SPI.

        Imports luma.core and luma.oled lazily so that machines without the
        hardware extra (luma libraries and SPI kernel modules) can still
        import the rest of the package without errors.

        Args:
            width: Display width in pixels. Default 256 for the standard
                SSD1322 OLED module.
            height: Display height in pixels. Default 64 for the standard
                SSD1322 OLED module.
        """
        from luma.core.interface.serial import spi
        from luma.oled.device import ssd1322

        # SPI bus 0, device 0 -- default GPIO SPI pins on Raspberry Pi
        # (MOSI=GPIO10, SCLK=GPIO11, CE0=GPIO8).
        serial = spi(device=0, port=0)
        self.device = ssd1322(serial, width=width, height=height)
        logger.info("SSD1322 display initialized (%dx%d)", width, height)

    def update(self, pil_image: Image.Image) -> None:
        """Display a PIL RGB image (converted to grayscale for the OLED)."""
        # Convert RGB to 8-bit grayscale. SSD1322 is 4-bit -- luma.oled
        # handles 8->4 bit reduction.
        grey = pil_image.convert("L")
        self.device.display(grey)

    def handle_events(self) -> bool:
        """No GUI events on hardware - always returns True."""
        return True

    def close(self) -> None:
        """Clean up the display device."""
        self.device.cleanup()
        logger.info("SSD1322 display closed")
