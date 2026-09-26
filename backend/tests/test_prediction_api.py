import pytest
from fastapi.testclient import TestClient


def test_get_race_predictions_default_stage(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/predictions")
    assert response.status_code == 200

    data = response.json()
    assert data["race_id"] == race_id
    assert data["stage"] == "POST_QUALIFYING"
    assert len(data["predictions"]) >= 1

    first_pred = data["predictions"][0]
    assert "raw_win_probability" in first_pred
    assert "race_share_probability" in first_pred
    assert "podium_probability" in first_pred
    assert "top5_probability" in first_pred
    assert "predicted_finish_position" in first_pred

    # Verify race-share normalization sums to ~1.0
    total_share = sum(p["race_share_probability"] for p in data["predictions"])
    assert pytest.approx(total_share, abs=1e-3) == 1.0


def test_get_race_predictions_with_stage_param(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/predictions?stage=POST_FP1")
    assert response.status_code == 200

    data = response.json()
    assert data["stage"] == "POST_FP1"


def test_get_race_predictions_by_stage_path(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/predictions/POST_FP3")
    assert response.status_code == 200

    data = response.json()
    assert data["stage"] == "POST_FP3"


def test_get_race_predictions_invalid_stage(client: TestClient):
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    response = client.get(f"/api/races/{race_id}/predictions/POST_RACE")
    assert response.status_code == 400
    assert "Invalid prediction stage" in response.json()["detail"]


def test_get_race_predictions_nonexistent_race(client: TestClient):
    response = client.get("/api/races/99999/predictions")
    assert response.status_code == 404
    assert response.json()["detail"] == "Race with ID 99999 not found"


def test_get_prediction_stages(client: TestClient):
    response = client.get("/api/predictions/stages")
    assert response.status_code == 200
    stages = response.json()
    assert "PRE_FP1" in stages
    assert "POST_QUALIFYING" in stages
    assert "FINAL" not in stages
