from unittest.mock import MagicMock
import httpx
import pytest

from app.services.f1_data.jolpica_client import (
    JolpicaClient,
    JolpicaAPIError,
    JolpicaHTTPError,
    JolpicaParseError,
)


@pytest.fixture
def mock_httpx_client():
    return MagicMock(spec=httpx.Client)


def test_client_init():
    client = JolpicaClient(base_url="https://api.jolpi.ca/ergast/f1/", timeout=10.0)
    assert client.base_url == "https://api.jolpi.ca/ergast/f1"
    assert client.timeout == 10.0


def test_get_seasons_success(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "MRData": {
            "SeasonTable": {
                "Seasons": [
                    {"season": "2024", "url": "http://example.com/2024"},
                    {"season": "2025", "url": "http://example.com/2025"},
                ]
            }
        }
    }
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    seasons = client.get_seasons()

    assert len(seasons) == 2
    assert seasons[0]["season"] == "2024"
    assert seasons[1]["season"] == "2025"
    mock_httpx_client.get.assert_called_once()


def test_get_races_success(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "MRData": {
            "RaceTable": {
                "Races": [
                    {
                        "season": "2025",
                        "round": "1",
                        "raceName": "Australian Grand Prix",
                        "Circuit": {"circuitName": "Albert Park Circuit", "Location": {"country": "Australia"}},
                        "date": "2025-03-16",
                    }
                ]
            }
        }
    }
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    races = client.get_races(season=2025)

    assert len(races) == 1
    assert races[0]["raceName"] == "Australian Grand Prix"
    assert races[0]["round"] == "1"


def test_get_race_results_success(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "MRData": {
            "RaceTable": {
                "Races": [
                    {
                        "season": "2025",
                        "round": "1",
                        "Results": [
                            {
                                "position": "1",
                                "laps": "58",
                                "Driver": {"driverId": "norris", "code": "NOR"},
                                "Constructor": {"constructorId": "mclaren", "name": "McLaren"},
                            }
                        ],
                    }
                ]
            }
        }
    }
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    results = client.get_race_results(season=2025, round_num=1)

    assert len(results) == 1
    assert results[0]["Results"][0]["Driver"]["code"] == "NOR"


def test_get_drivers_success(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "MRData": {
            "DriverTable": {
                "Drivers": [
                    {
                        "driverId": "verstappen",
                        "code": "VER",
                        "givenName": "Max",
                        "familyName": "Verstappen",
                        "nationality": "Dutch",
                    }
                ]
            }
        }
    }
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    drivers = client.get_drivers(season=2025)

    assert len(drivers) == 1
    assert drivers[0]["code"] == "VER"


def test_get_constructors_success(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "MRData": {
            "ConstructorTable": {
                "Constructors": [
                    {
                        "constructorId": "ferrari",
                        "name": "Ferrari",
                        "nationality": "Italian",
                    }
                ]
            }
        }
    }
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    constructors = client.get_constructors(season=2025)

    assert len(constructors) == 1
    assert constructors[0]["name"] == "Ferrari"


def test_http_failure_raises_exception(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    with pytest.raises(JolpicaHTTPError) as exc_info:
        client.get_races(season=2099)

    assert exc_info.value.status_code == 404


def test_malformed_response_raises_exception(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"InvalidKey": {}}
    mock_httpx_client.get.return_value = mock_response

    client = JolpicaClient(httpx_client=mock_httpx_client)
    with pytest.raises(JolpicaParseError):
        client.get_seasons()


def test_network_error_raises_exception(mock_httpx_client):
    mock_httpx_client.get.side_effect = httpx.RequestError("Connection refused")

    client = JolpicaClient(httpx_client=mock_httpx_client)
    with pytest.raises(JolpicaAPIError):
        client.get_seasons()
