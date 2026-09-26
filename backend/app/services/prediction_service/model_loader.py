from functools import lru_cache
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import joblib

logger = logging.getLogger(__name__)


def find_default_models_dir() -> Path:
    """Resolve project-relative path to ml/artifacts/models/ directory."""
    # Current file: backend/app/services/prediction_service/model_loader.py
    # Project root is 4 levels up
    project_root = Path(__file__).resolve().parents[4]
    models_dir = project_root / "ml" / "artifacts" / "models"
    return models_dir


class ModelLoader:
    """Singleton/cached loader for trained machine learning model artifacts."""

    REQUIRED_MODELS = {
        "win_probability": "win_probability_model.joblib",
        "finish_position": "finish_position_model.joblib",
        "podium": "podium_model.joblib",
        "top5": "top5_model.joblib",
    }

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir) if models_dir else find_default_models_dir()
        self._models: Dict[str, Any] = {}
        self._is_loaded = False

    def load_models(self) -> Dict[str, Any]:
        """Load all required model artifacts from disk into memory."""
        if self._is_loaded and self._models:
            return self._models

        if not self.models_dir.exists():
            raise FileNotFoundError(
                f"Model artifacts directory not found at: {self.models_dir.resolve()}. "
                "Ensure ML model training has been completed."
            )

        loaded = {}
        for key, filename in self.REQUIRED_MODELS.items():
            filepath = self.models_dir / filename
            if not filepath.exists():
                raise FileNotFoundError(
                    f"Required model artifact '{filename}' missing at: {filepath.resolve()}."
                )

            try:
                logger.info("Loading ML model artifact: %s", filepath)
                loaded[key] = joblib.load(filepath)
            except Exception as e:
                raise RuntimeError(f"Failed to load model artifact '{filename}' from {filepath}: {e}") from e

        self._models = loaded
        self._is_loaded = True
        return self._models

    def get_model(self, model_key: str) -> Any:
        """Get a specific loaded model by key."""
        if not self._is_loaded:
            self.load_models()

        if model_key not in self._models:
            raise KeyError(f"Model key '{model_key}' not found in loaded models.")

        return self._models[model_key]


@lru_cache(maxsize=1)
def get_model_loader(models_dir: Optional[str] = None) -> ModelLoader:
    """Get singleton cached ModelLoader instance."""
    path = Path(models_dir) if models_dir else None
    loader = ModelLoader(models_dir=path)
    loader.load_models()
    return loader
