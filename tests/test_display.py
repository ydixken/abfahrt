"""Tests for display module standalone renderers."""

from PIL import Image

from abfahrt.display import render_boot_screen


class TestRenderBootScreen:
    """Tests for render_boot_screen()."""

    def test_correct_dimensions(self):
        """Verify that the boot screen matches the requested pixel dimensions."""
        img = render_boot_screen("Loading...", width=1520, height=180)
        assert img.size == (1520, 180)

    def test_custom_dimensions(self):
        """Verify that non-default dimensions are respected."""
        img = render_boot_screen("Loading...", width=800, height=100)
        assert img.size == (800, 100)

    def test_returns_rgb_image(self):
        """Verify that the rendered image uses RGB mode."""
        img = render_boot_screen("Test status")
        assert img.mode == "RGB"

    def test_non_black_pixels_present(self):
        """Verify that the boot screen contains visible (non-black) pixels."""
        img = render_boot_screen("Stationen laden...")
        pixels = list(img.tobytes())
        assert any(p != 0 for p in pixels), "Boot screen should contain non-black pixels"

    def test_is_pil_image(self):
        """Verify the return type is a PIL Image."""
        img = render_boot_screen("test")
        assert isinstance(img, Image.Image)
