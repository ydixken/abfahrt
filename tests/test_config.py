"""Tests for abfahrt.config."""

from abfahrt.config import Config, load_config, StationConfig


class TestConfigDefaults:
    """Tests that Config loads sensible hardcoded defaults when no YAML file or CLI args are given."""

    def test_default_station(self):
        """Verify that the default station is Savignyplatz (ID 900023201)."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert len(config.stations) == 1
        assert config.stations[0].id == "900023201"

    def test_default_display(self):
        """Verify default display dimensions (1520x180), FPS (30), and amber color."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.display.width == 1520
        assert config.display.height == 180
        assert config.display.fullscreen is False
        assert config.display.fps == 30
        assert config.display.background_color == [0, 0, 0]
        assert config.display.text_color == [255, 170, 0]

    def test_default_refresh(self):
        """Verify default refresh interval (30s) and departure count (20)."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.refresh.interval_seconds == 30
        assert config.refresh.departure_count == 20

    def test_default_filters(self):
        """Verify default filters: rail types enabled, bus disabled."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.filters.suburban is True
        assert config.filters.subway is True
        assert config.filters.tram is True
        assert config.filters.bus is False
        assert config.filters.express is True
        assert config.filters.regional is True

    def test_default_rotation(self):
        """Verify default rotation interval is 10 seconds."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.rotation.interval_seconds == 10

    def test_default_fonts(self):
        """Verify default font sizes for header (13), departure (18), and remark (13)."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.fonts.header_size == 13
        assert config.fonts.departure_size == 18
        assert config.fonts.remark_size == 13

    def test_default_cli_flags(self):
        """Verify that all CLI-only flags default to None/False."""
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.search is None
        assert config.fetch_test is False
        assert config.render_test is False
        assert config.debug is False


class TestYAMLOverlay:
    """Tests that YAML config values correctly override hardcoded defaults."""

    def test_yaml_overrides_stations(self, sample_config_yaml):
        """Verify that YAML defines two stations replacing the single default."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert len(config.stations) == 2
        assert config.stations[0].id == "900100003"
        assert config.stations[0].name == "Alexanderplatz"
        assert config.stations[1].id == "900023201"

    def test_yaml_overrides_display(self, sample_config_yaml):
        """Verify that YAML overrides all display settings (dimensions, FPS, colors)."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.display.width == 800
        assert config.display.height == 100
        assert config.display.fullscreen is True
        assert config.display.fps == 60
        assert config.display.background_color == [10, 10, 10]
        assert config.display.text_color == [200, 150, 0]

    def test_yaml_overrides_refresh(self, sample_config_yaml):
        """Verify that YAML overrides refresh interval (60s) and departure count (5)."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.refresh.interval_seconds == 60
        assert config.refresh.departure_count == 5

    def test_yaml_overrides_filters(self, sample_config_yaml):
        """Verify that YAML overrides filter booleans (suburban=false, bus=true, etc.)."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.filters.suburban is False
        assert config.filters.bus is True
        assert config.filters.express is False

    def test_yaml_overrides_rotation(self, sample_config_yaml):
        """Verify that YAML overrides rotation interval to 15 seconds."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.rotation.interval_seconds == 15

    def test_missing_yaml_uses_defaults(self):
        """Verify that a nonexistent YAML path silently falls back to defaults."""
        config = load_config(yaml_path="/does/not/exist.yaml", cli_args=[])
        assert config.display.width == 1520


class TestCLIOverlay:
    """Tests that CLI arguments take highest precedence over both defaults and YAML values."""

    def test_station_id_override(self, sample_config_yaml):
        """Verify that --station-id replaces all YAML stations with a single station."""
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--station-id", "900999999"],
        )
        assert len(config.stations) == 1
        assert config.stations[0].id == "900999999"

    def test_fullscreen_override(self):
        """Verify that --fullscreen sets display.fullscreen=True."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--fullscreen"],
        )
        assert config.display.fullscreen is True

    def test_refresh_override(self):
        """Verify that --refresh 10 overrides the refresh interval."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--refresh", "10"],
        )
        assert config.refresh.interval_seconds == 10

    def test_rotation_override(self):
        """Verify that --rotation 5 overrides the rotation interval."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--rotation", "5"],
        )
        assert config.rotation.interval_seconds == 5

    def test_search_flag(self):
        """Verify that --search stores the query string in config.search."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--search", "Alexanderplatz"],
        )
        assert config.search == "Alexanderplatz"

    def test_fetch_test_flag(self):
        """Verify that --fetch-test sets config.fetch_test=True."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--fetch-test"],
        )
        assert config.fetch_test is True

    def test_render_test_flag(self):
        """Verify that --render-test sets config.render_test=True."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--render-test"],
        )
        assert config.render_test is True

    def test_debug_flag(self):
        """Verify that --debug sets config.debug=True."""
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--debug"],
        )
        assert config.debug is True

    def test_cli_overrides_yaml(self, sample_config_yaml):
        """Verify that CLI args (--refresh, --fullscreen) override YAML values."""
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--refresh", "5", "--fullscreen"],
        )
        assert config.refresh.interval_seconds == 5
        assert config.display.fullscreen is True


class TestMultiStationConfig:
    """Tests for multi-station configuration via YAML and the --station-id CLI override."""

    def test_multi_station_from_yaml(self, sample_config_yaml):
        """Verify that YAML can define multiple stations with correct IDs."""
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert len(config.stations) == 2
        assert config.stations[0].id == "900100003"
        assert config.stations[1].id == "900023201"

    def test_station_id_cli_replaces_all(self, sample_config_yaml):
        """Verify that --station-id replaces all YAML-defined stations with one."""
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--station-id", "900111111"],
        )
        assert len(config.stations) == 1
        assert config.stations[0].id == "900111111"
