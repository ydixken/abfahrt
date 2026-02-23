"""Shared fixtures with sample BVG API JSON responses."""

import pytest


@pytest.fixture
def sample_departure_raw():
    """A single normal departure from BVG API."""
    return {
        "tripId": "1|12345|0|86|22022026",
        "stop": {"id": "900023201", "name": "S Savignyplatz"},
        "when": "2026-02-22T21:05:00+01:00",
        "plannedWhen": "2026-02-22T21:03:00+01:00",
        "delay": 120,
        "platform": "1",
        "direction": "S Potsdam Hauptbahnhof",
        "line": {
            "id": "s7",
            "name": "S7",
            "product": "suburban",
            "mode": "train",
        },
        "remarks": [
            {"type": "hint", "code": "FK", "text": "Bicycles allowed"},
            {"type": "warning", "code": "text", "text": "Bauarbeiten"},
        ],
        "cancelled": False,
    }


@pytest.fixture
def sample_departure_cancelled():
    """A cancelled departure."""
    return {
        "when": None,
        "plannedWhen": "2026-02-22T21:10:00+01:00",
        "delay": None,
        "platform": "2",
        "direction": "S Westkreuz",
        "line": {
            "name": "S5",
            "product": "suburban",
        },
        "remarks": [],
        "cancelled": True,
    }


@pytest.fixture
def sample_departure_null_when():
    """A departure with null when (no real-time data)."""
    return {
        "when": None,
        "plannedWhen": "2026-02-22T22:00:00+01:00",
        "delay": None,
        "platform": None,
        "direction": "U Uhlandstr.",
        "line": {
            "name": "U1",
            "product": "subway",
        },
        "remarks": [],
        "cancelled": False,
    }


@pytest.fixture
def sample_departure_no_remarks():
    """A departure with empty remarks list."""
    return {
        "when": "2026-02-22T21:15:00+01:00",
        "plannedWhen": "2026-02-22T21:15:00+01:00",
        "delay": 0,
        "platform": "3",
        "direction": "S+U Alexanderplatz",
        "line": {
            "name": "RE1",
            "product": "regional",
        },
        "remarks": [],
        "cancelled": False,
    }


@pytest.fixture
def sample_departures_list(
    sample_departure_raw,
    sample_departure_cancelled,
    sample_departure_null_when,
    sample_departure_no_remarks,
):
    """List of mixed departures as raw API dicts."""
    return [
        sample_departure_raw,
        sample_departure_cancelled,
        sample_departure_null_when,
        sample_departure_no_remarks,
    ]


@pytest.fixture
def sample_api_departures_response(sample_departures_list):
    """Full API response structure for departures endpoint."""
    return {"departures": sample_departures_list}


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Create a temporary YAML config file."""
    yaml_content = """stations:
  - id: "900100003"
    name: "Alexanderplatz"
  - id: "900023201"
    name: "Savignyplatz"

rotation:
  interval_seconds: 15

display:
  width: 800
  height: 100
  fullscreen: true
  fps: 60
  background_color: [10, 10, 10]
  text_color: [200, 150, 0]

refresh:
  interval_seconds: 60
  departure_count: 5

filters:
  suburban: false
  subway: true
  tram: false
  bus: true
  express: false
  regional: false
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)
    return str(config_file)
