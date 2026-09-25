from enum import Enum
from typing import List


class PredictionStage(str, Enum):
    """Centralized definition of race-weekend prediction stages."""
    PRE_FP1 = "PRE_FP1"
    POST_FP1 = "POST_FP1"
    POST_FP2 = "POST_FP2"
    POST_FP3 = "POST_FP3"
    POST_QUALIFYING = "POST_QUALIFYING"
    FINAL = "FINAL"


# Chronological stage order
STAGE_ORDER: List[PredictionStage] = [
    PredictionStage.PRE_FP1,
    PredictionStage.POST_FP1,
    PredictionStage.POST_FP2,
    PredictionStage.POST_FP3,
    PredictionStage.POST_QUALIFYING,
    PredictionStage.FINAL,
]


def is_stage_at_or_after(current_stage: PredictionStage, required_stage: PredictionStage) -> bool:
    """Return True if current_stage is chronologically at or after required_stage."""
    current_idx = STAGE_ORDER.index(current_stage)
    required_idx = STAGE_ORDER.index(required_stage)
    return current_idx >= required_idx
