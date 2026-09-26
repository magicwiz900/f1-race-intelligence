import pytest
from fastapi.testclient import TestClient

from app.config import settings


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "f1-race-intelligence"


def test_get_races(client: TestClient):
    response = client.get("/api/races")
    assert response.status_code == 200
    races = response.json()
    assert len(races) >= 1
    assert races[0]["race_name"] == "Australian Grand Prix"
    assert races[0]["season"] == 2025


def test_get_races_filter_by_season(client: TestClient):
    response = client.get("/api/races?season=2025")
    assert response.status_code == 200
    races = response.json()
    assert len(races) == 1
    assert races[0]["season"] == 2025

    empty_response = client.get("/api/races?season=1950")
    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_get_race_by_id(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == race_id
    assert data["race_name"] == "Australian Grand Prix"


def test_get_nonexistent_race_404(client: TestClient):
    response = client.get("/api/races/99999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Race with ID 99999 not found"


def test_get_race_sessions(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 2
    types = [s["session_type"] for s in sessions]
    assert "FP1" in types
    assert "RACE" in types


def test_get_race_results(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/results")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["position"] == 1
    assert results[0]["driver"]["driver_code"] == "NOR"
    assert results[0]["team"]["name"] == "McLaren"


def test_get_race_results_filtered_by_session_type(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    res_fp1 = client.get(f"/api/races/{race_id}/results?session_type=FP1")
    assert res_fp1.status_code == 200
    assert res_fp1.json() == []

    res_race = client.get(f"/api/races/{race_id}/results?session_type=RACE")
    assert res_race.status_code == 200
    assert len(res_race.json()) == 1


def test_get_race_predictions_empty(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/predictions")
    assert response.status_code == 200
    data = response.json()
    assert data["race_id"] == race_id
    assert data["stage"] == "POST_QUALIFYING"
    assert isinstance(data["predictions"], list)



def test_get_drivers(client: TestClient):
    response = client.get("/api/drivers")
    assert response.status_code == 200
    drivers = response.json()
    assert len(drivers) >= 1
    assert drivers[0]["driver_code"] == "NOR"
    assert drivers[0]["team"]["name"] == "McLaren"


def test_get_driver_by_id(client: TestClient):
    drivers = client.get("/api/drivers").json()
    driver_id = drivers[0]["id"]

    response = client.get(f"/api/drivers/{driver_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == driver_id
    assert data["name"] == "Lando Norris"


def test_get_nonexistent_driver_404(client: TestClient):
    response = client.get("/api/drivers/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Driver with ID 99999 not found"


def test_get_teams(client: TestClient):
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    assert len(teams) >= 1
    assert teams[0]["name"] == "McLaren"


def test_get_team_by_id(client: TestClient):
    teams = client.get("/api/teams").json()
    team_id = teams[0]["id"]

    response = client.get(f"/api/teams/{team_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == team_id
    assert data["name"] == "McLaren"
    assert len(data["drivers"]) == 1
    assert data["drivers"][0]["driver_code"] == "NOR"


def test_get_nonexistent_team_404(client: TestClient):
    response = client.get("/api/teams/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Team with ID 99999 not found"


def test_get_session_by_id(client: TestClient):
    races = client.get("/api/races").json()
    sessions = client.get(f"/api/races/{races[0]['id']}/sessions").json()
    session_id = sessions[0]["id"]

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert "race" in data
    assert "session_results" in data


def test_get_nonexistent_session_404(client: TestClient):
    response = client.get("/api/sessions/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Session with ID 99999 not found"


def test_predictions_endpoint(client: TestClient):
    response = client.get("/api/predictions")
    assert response.status_code == 200
    assert response.json() == []

    stages = client.get("/api/predictions/stages")
    assert stages.status_code == 200
    assert "PRE_FP1" in stages.json()


def test_protected_demo_endpoint(client: TestClient, monkeypatch):
    response = client.get("/api/protected-demo")
    assert response.status_code == 200

    monkeypatch.setattr(settings, "API_KEY", "secret_test_key")
    unauth_resp = client.get("/api/protected-demo")
    assert unauth_resp.status_code == 401

    auth_resp = client.get("/api/protected-demo", headers={"X-API-Key": "secret_test_key"})
    assert auth_resp.status_code == 200
    assert auth_resp.json()["status"] == "authenticated"
