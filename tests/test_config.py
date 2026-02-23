"""Tests for abfahrt.config."""

from abfahrt.config import Config, load_config, StationConfig


class TestConfigDefaults:
    def test_default_station(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert len(config.stations) == 1
        assert config.stations[0].id == "900023201"

    def test_default_display(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.display.width == 1520
        assert config.display.height == 180
        assert config.display.fullscreen is False
        assert config.display.fps == 30
        assert config.display.background_color == [0, 0, 0]
        assert config.display.text_color == [255, 170, 0]

    def test_default_refresh(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.refresh.interval_seconds == 30
        assert config.refresh.departure_count == 20

    def test_default_filters(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.filters.suburban is True
        assert config.filters.subway is True
        assert config.filters.tram is True
        assert config.filters.bus is False
        assert config.filters.ferry is False
        assert config.filters.express is True
        assert config.filters.regional is True

    def test_default_rotation(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.rotation.interval_seconds == 10

    def test_default_fonts(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.fonts.header_size == 13
        assert config.fonts.departure_size == 18
        assert config.fonts.remark_size == 13

    def test_default_cli_flags(self):
        config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
        assert config.search is None
        assert config.fetch_test is False
        assert config.render_test is False
        assert config.debug is False


class TestYAMLOverlay:
    def test_yaml_overrides_stations(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert len(config.stations) == 2
        assert config.stations[0].id == "900100003"
        assert config.stations[0].name == "Alexanderplatz"
        assert config.stations[1].id == "900023201"

    def test_yaml_overrides_display(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.display.width == 800
        assert config.display.height == 100
        assert config.display.fullscreen is True
        assert config.display.fps == 60
        assert config.display.background_color == [10, 10, 10]
        assert config.display.text_color == [200, 150, 0]

    def test_yaml_overrides_refresh(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.refresh.interval_seconds == 60
        assert config.refresh.departure_count == 5

    def test_yaml_overrides_filters(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.filters.suburban is False
        assert config.filters.bus is True
        assert config.filters.ferry is True
        assert config.filters.express is False

    def test_yaml_overrides_rotation(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert config.rotation.interval_seconds == 15

    def test_missing_yaml_uses_defaults(self):
        config = load_config(yaml_path="/does/not/exist.yaml", cli_args=[])
        assert config.display.width == 1520


class TestCLIOverlay:
    def test_station_id_override(self, sample_config_yaml):
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--station-id", "900999999"],
        )
        assert len(config.stations) == 1
        assert config.stations[0].id == "900999999"

    def test_fullscreen_override(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--fullscreen"],
        )
        assert config.display.fullscreen is True

    def test_refresh_override(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--refresh", "10"],
        )
        assert config.refresh.interval_seconds == 10

    def test_rotation_override(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--rotation", "5"],
        )
        assert config.rotation.interval_seconds == 5

    def test_search_flag(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--search", "Alexanderplatz"],
        )
        assert config.search == "Alexanderplatz"

    def test_fetch_test_flag(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--fetch-test"],
        )
        assert config.fetch_test is True

    def test_render_test_flag(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--render-test"],
        )
        assert config.render_test is True

    def test_debug_flag(self):
        config = load_config(
            yaml_path="/nonexistent.yaml",
            cli_args=["--debug"],
        )
        assert config.debug is True

    def test_cli_overrides_yaml(self, sample_config_yaml):
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--refresh", "5", "--fullscreen"],
        )
        assert config.refresh.interval_seconds == 5
        assert config.display.fullscreen is True


class TestMultiStationConfig:
    def test_multi_station_from_yaml(self, sample_config_yaml):
        config = load_config(yaml_path=sample_config_yaml, cli_args=[])
        assert len(config.stations) == 2
        assert config.stations[0].id == "900100003"
        assert config.stations[1].id == "900023201"

    def test_station_id_cli_replaces_all(self, sample_config_yaml):
        config = load_config(
            yaml_path=sample_config_yaml,
            cli_args=["--station-id", "900111111"],
        )
        assert len(config.stations) == 1
        assert config.stations[0].id == "900111111"
