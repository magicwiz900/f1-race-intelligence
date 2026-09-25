from typing import Any, Dict
from ml.stages import PredictionStage

FEATURE_METADATA: Dict[str, Dict[str, Any]] = {
    # Driver Form Features (Available from PRE_FP1)
    "driver_recent_avg_finish": {
        "description": "Average finish position of the driver in their last 5 completed races.",
        "category": "driver_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "position",
    },
    "driver_recent_win_rate": {
        "description": "Ratio of wins achieved by driver in their last 5 completed races.",
        "category": "driver_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "ratio",
    },
    "driver_recent_podium_rate": {
        "description": "Ratio of podium finishes (top 3) by driver in their last 5 completed races.",
        "category": "driver_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "ratio",
    },
    "driver_season_points": {
        "description": "Cumulative championship points scored by driver in current season prior to race.",
        "category": "driver_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "points",
    },

    # Team Form Features (Available from PRE_FP1)
    "team_recent_avg_finish": {
        "description": "Average finish position of team drivers in their last 5 completed races.",
        "category": "team_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "position",
    },
    "team_recent_win_rate": {
        "description": "Ratio of wins achieved by team drivers in last 5 completed races.",
        "category": "team_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "ratio",
    },
    "team_recent_podium_rate": {
        "description": "Ratio of podium finishes achieved by team drivers in last 5 completed races.",
        "category": "team_form",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "ratio",
    },

    # Circuit History Features (Available from PRE_FP1)
    "driver_circuit_avg_finish": {
        "description": "Driver's historical average finish position at current circuit in prior seasons.",
        "category": "circuit_history",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "float",
        "unit": "position",
    },
    "driver_circuit_starts": {
        "description": "Number of previous race starts by driver at current circuit.",
        "category": "circuit_history",
        "first_available_stage": PredictionStage.PRE_FP1,
        "data_type": "int",
        "unit": "count",
    },

    # Session Pace Features: FP1 (Available from POST_FP1)
    "fp1_position": {
        "description": "Driver's finishing position in Free Practice 1.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP1,
        "data_type": "float",
        "unit": "position",
    },
    "fp1_lap_time": {
        "description": "Driver's best lap time in FP1 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP1,
        "data_type": "float",
        "unit": "seconds",
    },
    "fp1_gap_to_best": {
        "description": "Driver's gap to session-best lap time in FP1 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP1,
        "data_type": "float",
        "unit": "seconds",
    },

    # Session Pace Features: FP2 (Available from POST_FP2)
    "fp2_position": {
        "description": "Driver's finishing position in Free Practice 2.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP2,
        "data_type": "float",
        "unit": "position",
    },
    "fp2_lap_time": {
        "description": "Driver's best lap time in FP2 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP2,
        "data_type": "float",
        "unit": "seconds",
    },
    "fp2_gap_to_best": {
        "description": "Driver's gap to session-best lap time in FP2 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP2,
        "data_type": "float",
        "unit": "seconds",
    },

    # Session Pace Features: FP3 (Available from POST_FP3)
    "fp3_position": {
        "description": "Driver's finishing position in Free Practice 3.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP3,
        "data_type": "float",
        "unit": "position",
    },
    "fp3_lap_time": {
        "description": "Driver's best lap time in FP3 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP3,
        "data_type": "float",
        "unit": "seconds",
    },
    "fp3_gap_to_best": {
        "description": "Driver's gap to session-best lap time in FP3 in seconds.",
        "category": "session_pace",
        "first_available_stage": PredictionStage.POST_FP3,
        "data_type": "float",
        "unit": "seconds",
    },

    # Session Consistency Features
    "fp_avg_position": {
        "description": "Mean practice session position across completed FP sessions.",
        "category": "session_consistency",
        "first_available_stage": PredictionStage.POST_FP1,
        "data_type": "float",
        "unit": "position",
    },

    # Qualifying Features (Available from POST_QUALIFYING)
    "qualifying_position": {
        "description": "Driver's qualifying grid position.",
        "category": "qualifying",
        "first_available_stage": PredictionStage.POST_QUALIFYING,
        "data_type": "float",
        "unit": "position",
    },
    "qualifying_lap_time": {
        "description": "Driver's qualifying lap time in seconds.",
        "category": "qualifying",
        "first_available_stage": PredictionStage.POST_QUALIFYING,
        "data_type": "float",
        "unit": "seconds",
    },
    "qualifying_gap_to_pole": {
        "description": "Driver's gap to pole position lap time in seconds.",
        "category": "qualifying",
        "first_available_stage": PredictionStage.POST_QUALIFYING,
        "data_type": "float",
        "unit": "seconds",
    },
}
