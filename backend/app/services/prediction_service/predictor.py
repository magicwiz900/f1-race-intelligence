import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session as DBSession

from app.models import Race
from app.services.prediction_service.feature_adapter import FeatureAdapter
from app.services.prediction_service.model_loader import ModelLoader, get_model_loader
from ml.stages import PredictionStage

logger = logging.getLogger(__name__)

ALLOWED_PREDICTIVE_STAGES = {
    PredictionStage.PRE_FP1.value,
    PredictionStage.POST_FP1.value,
    PredictionStage.POST_FP2.value,
    PredictionStage.POST_FP3.value,
    PredictionStage.POST_QUALIFYING.value,
}


class PredictionService:
    """Service layer orchestrating ML model inference and race-level probability normalization."""

    def __init__(self, db: DBSession, loader: Optional[ModelLoader] = None):
        self.db = db
        self.loader = loader or get_model_loader()
        self.adapter = FeatureAdapter(db)

    def predict_race_stage(
        self,
        race_id: int,
        stage: Optional[str] = None,
        stage_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate predictions for all drivers in a race at a specified stage.
        """
        # 1. Fetch Race
        race = self.db.get(Race, race_id)
        if not race:
            raise KeyError(f"Race with ID {race_id} not found.")

        # 2. Validate Stage
        target_stage_str = (stage or stage_str or PredictionStage.POST_QUALIFYING.value).upper()
        if target_stage_str not in ALLOWED_PREDICTIVE_STAGES:
            raise ValueError(
                f"Invalid prediction stage '{stage or stage_str}'. Supported stages: {sorted(list(ALLOWED_PREDICTIVE_STAGES))}"
            )

        stage_enum = PredictionStage(target_stage_str)

        # 3. Build Features via FeatureAdapter
        features_df, drivers_info, data_availability = self.adapter.build_features_for_race_stage(
            race=race,
            stage=stage_enum,
        )

        if features_df.empty or not drivers_info:
            logger.warning("No drivers or features available for race_id=%d stage=%s", race_id, target_stage_str)
            return {
                "race_id": race.id,
                "season": race.season,
                "round": race.round,
                "race_name": race.race_name,
                "stage": target_stage_str,
                "predictions": [],
                "data_availability": data_availability,
            }

        # 4. Load Models
        try:
            models = self.loader.load_models()
            win_model = models["win_probability"]
            finish_model = models["finish_position"]
            podium_model = models["podium"]
            top5_model = models["top5"]
        except FileNotFoundError as e:
            logger.error("Missing model artifact: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Prediction model artifacts are missing on server: {e}",
            )
        except Exception as e:
            logger.error("Failed to load models for inference: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model loading failure: {e}",
            )

        # 5. Model Inference
        raw_win_probs = win_model.predict_proba(features_df)[:, 1] if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1 else np.zeros(len(features_df))
        podium_probs = podium_model.predict_proba(features_df)[:, 1] if hasattr(podium_model, "predict_proba") and len(podium_model.classes_) > 1 else np.zeros(len(features_df))
        top5_probs = top5_model.predict_proba(features_df)[:, 1] if hasattr(top5_model, "predict_proba") and len(top5_model.classes_) > 1 else np.zeros(len(features_df))
        pred_positions = finish_model.predict(features_df)

        # 6. Compute Race-Level Normalized Win Probabilities (race_share_probability)
        sum_raw = float(np.sum(raw_win_probs))
        if sum_raw > 0:
            race_share_probs = raw_win_probs / sum_raw
        else:
            race_share_probs = np.full(len(raw_win_probs), 1.0 / len(raw_win_probs))

        # 7. Build Driver Prediction Items
        predictions_list = []
        for i, d_info in enumerate(drivers_info):
            raw_w = float(raw_win_probs[i])
            share_w = float(race_share_probs[i])
            podium_p = float(podium_probs[i])
            top5_p = float(top5_probs[i])
            pred_pos = float(pred_positions[i])

            predictions_list.append({
                "driver_id": d_info["driver_id"],
                "driver_code": d_info["driver_code"],
                "driver_name": d_info["driver_name"],
                "team_id": d_info["team_id"],
                "team_name": d_info["team_name"],
                "raw_win_probability": round(raw_w, 4),
                "race_share_probability": round(share_w, 4),
                "podium_probability": round(podium_p, 4),
                "top5_probability": round(top5_p, 4),
                "predicted_finish_position": round(pred_pos, 2),
            })

        # Sort predictions by race_share_probability descending
        predictions_list.sort(key=lambda x: x["race_share_probability"], reverse=True)

        return {
            "race_id": race.id,
            "season": race.season,
            "round": race.round,
            "race_name": race.race_name,
            "stage": target_stage_str,
            "predictions": predictions_list,
            "data_availability": data_availability,
        }
