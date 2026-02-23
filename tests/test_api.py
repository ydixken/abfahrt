"""Tests for abfahrt.api."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from abfahrt.api import BASE_URL, BVGClient
from abfahrt.config import load_config
from abfahrt.models import Departure


@pytest.fixture
def client():
    config = load_config(yaml_path="/nonexistent.yaml", cli_args=[])
    return BVGClient(config)


@pytest.fixture
def mock_departures_response(sample_departures_list):
    """Mock response for departures endpoint."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"departures": sample_departures_list}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestGetDepartures:
    @patch("abfahrt.api.requests.Session.get")
    def test_calls_correct_url(self, mock_get, client, mock_departures_response):
        mock_get.return_value = mock_departures_response
        client.get_departures("900023201")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "900023201" in call_args[0][0]
        assert "/departures" in call_args[0][0]

    @patch("abfahrt.api.requests.Session.get")
    def test_passes_filter_params(self, mock_get, client, mock_departures_response):
        mock_get.return_value = mock_departures_response
        client.get_departures("900023201")

        params = mock_get.call_args[1]["params"]
        assert params["suburban"] == "true"
        assert params["bus"] == "false"
        assert params["ferry"] == "false"
        assert params["duration"] == 60

    @patch("abfahrt.api.requests.Session.get")
    def test_returns_departure_list(self, mock_get, client, mock_departures_response):
        mock_get.return_value = mock_departures_response
        result = client.get_departures("900023201")
        assert isinstance(result, list)
        assert len(result) == 4

    @patch("abfahrt.api.requests.Session.get")
    def test_timeout(self, mock_get, client):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        with pytest.raises(requests.exceptions.Timeout):
            client.get_departures("900023201")

    @patch("abfahrt.api.requests.Session.get")
    def test_connection_error(self, mock_get, client):
        mock_get.side_effect = requests.exceptions.ConnectionError("No connection")
        with pytest.raises(requests.exceptions.ConnectionError):
            client.get_departures("900023201")


class TestSearchStations:
    @patch("abfahrt.api.requests.Session.get")
    def test_search_calls_locations(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "900100003", "name": "S+U Alexanderplatz", "type": "stop"},
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = client.search_stations("Alexanderplatz")
        assert len(result) == 1
        assert result[0]["name"] == "S+U Alexanderplatz"

        params = mock_get.call_args[1]["params"]
        assert params["query"] == "Alexanderplatz"
        assert params["results"] == 5


class TestGetStationName:
    @patch("abfahrt.api.requests.Session.get")
    def test_returns_name(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "900023201", "name": "S Savignyplatz"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        name = client.get_station_name("900023201")
        assert name == "S Savignyplatz"


class TestFetchParsedDepartures:
    @patch("abfahrt.api.requests.Session.get")
    def test_returns_sorted_departures(self, mock_get, client, sample_departures_list):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"departures": sample_departures_list}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = client.fetch_parsed_departures("900023201")
        assert all(isinstance(d, Departure) for d in result)

    @patch("abfahrt.api.requests.Session.get")
    def test_sorted_by_when(self, mock_get, client, sample_departures_list):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"departures": sample_departures_list}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = client.fetch_parsed_departures("900023201")
        # Check sorted order (entries with when/planned_when)
        times = [d.when or d.planned_when or "" for d in result]
        assert times == sorted(times)

    @patch("abfahrt.api.requests.Session.get")
    def test_keeps_cancelled(self, mock_get, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "departures": [
                {
                    "when": "2026-02-22T21:05:00+01:00",
                    "plannedWhen": "2026-02-22T21:05:00+01:00",
                    "delay": 0,
                    "platform": "1",
                    "direction": "Test",
                    "line": {"name": "S1", "product": "suburban"},
                    "remarks": [],
                    "cancelled": True,
                },
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = client.fetch_parsed_departures("900023201")
        assert len(result) == 1
        assert result[0].is_cancelled is True
