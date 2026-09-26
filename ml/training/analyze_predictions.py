import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, mean_squared_error, roc_auc_score

from ml.config import ARTIFACTS_DIR, DEFAULT_DATASET_CSV, TARGET_FINISH_POSITION, TARGET_WIN
from ml.data_split import chronological_race_split
from ml.features.metadata import FEATURE_METADATA
from ml.stages import STAGE_ORDER, PredictionStage
from ml.validation.leakage_checks import validate_dataset_no_leakage, validate_feature_target_separation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def analyze_stage_wise_performance(
    test_df: pd.DataFrame,
    win_model: Any,
    feature_cols: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Analyze win probability prediction performance separately for each pre-race prediction stage."""
    stage_metrics = {}

    pre_race_stages = [
        PredictionStage.PRE_FP1,
        PredictionStage.POST_FP1,
        PredictionStage.POST_FP2,
        PredictionStage.POST_FP3,
        PredictionStage.POST_QUALIFYING,
    ]

    for stage in pre_race_stages:
        stage_df = test_df[test_df["prediction_stage"] == stage.value]
        if stage_df.empty:
            continue

        X_stage = stage_df[feature_cols]
        y_stage = stage_df[TARGET_WIN].astype(int).values

        if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1:
            probs = win_model.predict_proba(X_stage)[:, 1]
        else:
            probs = np.zeros(len(X_stage))

        # Evens / Winner avg prob
        winner_mask = (y_stage == 1)
        winner_probs = probs[winner_mask] if np.sum(winner_mask) > 0 else []
        avg_winner_prob = float(np.mean(winner_probs)) if len(winner_probs) > 0 else 0.0

        log_loss_val = float(log_loss(y_stage, probs)) if len(np.unique(y_stage)) > 1 else 0.0
        brier_val = float(brier_score_loss(y_stage, probs))
        roc_auc_val = float(roc_auc_score(y_stage, probs)) if len(np.unique(y_stage)) > 1 else None

        stage_metrics[stage.value] = {
            "samples": len(stage_df),
            "mean_predicted_prob": float(np.mean(probs)),
            "max_predicted_prob": float(np.max(probs)),
            "min_predicted_prob": float(np.min(probs)),
            "avg_winner_predicted_prob": avg_winner_prob,
            "log_loss": log_loss_val,
            "brier_score": brier_val,
            "roc_auc": roc_auc_val,
        }

    return stage_metrics


def analyze_race_probability_sums(
    test_df: pd.DataFrame,
    win_model: Any,
    feature_cols: List[str],
) -> Dict[str, Any]:
    """Calculate the sum of predicted win probabilities across drivers per race and stage."""
    sums = []
    race_stage_sums = []

    grouped = test_df.groupby(["season", "round", "prediction_stage"])

    for (season, r_num, stage), group in grouped:
        X_group = group[feature_cols]
        if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1:
            probs = win_model.predict_proba(X_group)[:, 1]
        else:
            probs = np.zeros(len(X_group))

        p_sum = float(np.sum(probs))
        sums.append(p_sum)
        race_stage_sums.append({
            "season": int(season),
            "round": int(r_num),
            "stage": str(stage),
            "drivers_count": len(group),
            "probability_sum": p_sum,
        })

    return {
        "mean_sum": float(np.mean(sums)) if sums else 0.0,
        "min_sum": float(np.min(sums)) if sums else 0.0,
        "max_sum": float(np.max(sums)) if sums else 0.0,
        "std_sum": float(np.std(sums)) if sums else 0.0,
        "sample_races_evaluated": len(race_stage_sums),
        "note": "Raw binary LogisticRegression win probabilities predicted independently per driver do not naturally sum to 1.0 per race.",
    }


def analyze_10bin_calibration(
    test_df: pd.DataFrame,
    win_model: Any,
    feature_cols: List[str],
) -> Dict[str, Any]:
    """Evaluate win probability calibration across 10 probability bins on the test set."""
    X_test = test_df[feature_cols]
    y_test = test_df[TARGET_WIN].astype(int).values

    if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1:
        probs = win_model.predict_proba(X_test)[:, 1]
    else:
        probs = np.zeros(len(X_test))

    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    bin_details = []

    for i in range(len(bins) - 1):
        b_low, b_high = bins[i], bins[i + 1]
        if i == len(bins) - 2:
            mask = (probs >= b_low) & (probs <= b_high)
        else:
            mask = (probs >= b_low) & (probs < b_high)

        count = int(np.sum(mask))
        if count > 0:
            mean_prob = float(np.mean(probs[mask]))
            actual_win_rate = float(np.mean(y_test[mask]))
        else:
            mean_prob = (b_low + b_high) / 2.0
            actual_win_rate = 0.0

        bin_details.append({
            "bin_range": f"{int(b_low*100)}-{int(b_high*100)}%",
            "bin_lower": b_low,
            "bin_upper": b_high,
            "count": count,
            "mean_predicted_prob": mean_prob,
            "actual_win_rate": actual_win_rate,
        })

    return {
        "bins": bin_details,
        "total_test_samples": len(y_test),
        "overall_win_rate": float(np.mean(y_test)),
        "limitation_warning": "Single 2025 season dataset contains small sample sizes in higher probability bins.",
    }


def analyze_winner_probability_trajectories(
    test_df: pd.DataFrame,
    win_model: Any,
    feature_cols: List[str],
) -> List[Dict[str, Any]]:
    """Track actual race winner's predicted win probability across pre-race prediction stages."""
    trajectories = []

    # Get races in test set
    races = test_df[["season", "round", "race_id"]].drop_duplicates().sort_values(by=["season", "round"])

    pre_race_stages = [
        PredictionStage.PRE_FP1,
        PredictionStage.POST_FP1,
        PredictionStage.POST_FP2,
        PredictionStage.POST_FP3,
        PredictionStage.POST_QUALIFYING,
    ]

    for _, r_info in races.iterrows():
        s = int(r_info["season"])
        r = int(r_info["round"])
        r_id = int(r_info["race_id"])

        race_df = test_df[(test_df["season"] == s) & (test_df["round"] == r)]

        # Find winner driver_id in this race
        winner_rows = race_df[race_df[TARGET_WIN] == 1]
        if winner_rows.empty:
            continue

        winner_driver_id = int(winner_rows.iloc[0]["driver_id"])
        winner_code = str(winner_rows.iloc[0]["driver_code"])

        stage_probs = {}
        for st in pre_race_stages:
            st_df = race_df[(race_df["driver_id"] == winner_driver_id) & (race_df["prediction_stage"] == st.value)]
            if not st_df.empty:
                X_st = st_df[feature_cols]
                if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1:
                    p = float(win_model.predict_proba(X_st)[:, 1][0])
                else:
                    p = 0.0
                stage_probs[st.value] = round(p, 4)

        trajectories.append({
            "race_identifier": f"S{s}R{r}",
            "season": s,
            "round": r,
            "race_id": r_id,
            "winner_driver_id": winner_driver_id,
            "winner_driver_code": winner_code,
            "actual_finish_position": 1,
            "stage_probabilities": stage_probs,
        })

    return trajectories


def analyze_finish_position_model(
    test_df: pd.DataFrame,
    finish_model: Any,
    feature_cols: List[str],
) -> Dict[str, Any]:
    """Perform sanity checks and error analysis on Random Forest finish position model."""
    clean_test = test_df.dropna(subset=[TARGET_FINISH_POSITION])
    X_test = clean_test[feature_cols]
    y_true = clean_test[TARGET_FINISH_POSITION].astype(float).values

    preds = finish_model.predict(X_test)
    errors = preds - y_true
    abs_errors = np.abs(errors)

    mae = float(mean_absolute_error(y_true, preds))
    rmse = float(np.sqrt(mean_squared_error(y_true, preds)))
    mean_err = float(np.mean(errors))
    median_abs_err = float(np.median(abs_errors))

    min_pred = float(np.min(preds))
    max_pred = float(np.max(preds))
    out_of_bounds = int(np.sum((preds < 1.0) | (preds > 20.0)))

    return {
        "samples_evaluated": len(y_true),
        "mae": mae,
        "rmse": rmse,
        "mean_prediction_error_bias": mean_err,
        "median_absolute_error": median_abs_err,
        "min_predicted_position": min_pred,
        "max_predicted_position": max_pred,
        "out_of_grid_bounds_count": out_of_bounds,
        "sanity_status": "VALID" if out_of_bounds == 0 and 1.0 <= min_pred <= 20.0 and 1.0 <= max_pred <= 20.0 else "WARNING_OUT_OF_BOUNDS",
    }


def run_full_prediction_analysis(
    dataset_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute complete stage-wise analysis, calibration, trajectory, and position sanity checks."""
    ds_path = dataset_path or DEFAULT_DATASET_CSV
    out_dir = output_dir or (ARTIFACTS_DIR / "metrics")
    out_dir.mkdir(parents=True, exist_ok=True)
    calib_dir = ARTIFACTS_DIR / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    if not ds_path.exists():
        raise FileNotFoundError(f"Dataset file {ds_path} not found.")

    logger.info("Loading dataset from %s for prediction analysis...", ds_path)
    df = pd.read_csv(ds_path)

    # Validate leakage & feature separation
    is_valid, leakage_violations = validate_dataset_no_leakage(df)
    if not is_valid:
        raise ValueError(f"Leakage validation failed: {leakage_violations[0]}")

    feature_cols = [c for c in df.columns if c in FEATURE_METADATA]
    validate_feature_target_separation(feature_cols)

    # Chronological Split
    train_df, val_df, test_df, split_summary = chronological_race_split(df, train_ratio=0.60, val_ratio=0.20)
    eval_df = test_df if not test_df.empty else val_df

    # Load Trained Models
    win_model_path = ARTIFACTS_DIR / "models" / "win_probability_model.joblib"
    finish_model_path = ARTIFACTS_DIR / "models" / "finish_position_model.joblib"

    if not win_model_path.exists() or not finish_model_path.exists():
        raise FileNotFoundError("Trained model joblib files not found in ml/artifacts/models/. Run ml.training.train_models first.")

    win_model = joblib.load(win_model_path)
    finish_model = joblib.load(finish_model_path)

    # 1. Stage-Wise Prediction Analysis
    logger.info("Analyzing stage-wise performance...")
    stage_metrics = analyze_stage_wise_performance(eval_df, win_model, feature_cols)

    # 2. Race Probability Sum Check
    logger.info("Checking race-level probability sums...")
    sum_analysis = analyze_race_probability_sums(eval_df, win_model, feature_cols)

    # 3. 10-Bin Calibration Analysis
    logger.info("Evaluating 10-bin calibration...")
    calib_10bin = analyze_10bin_calibration(eval_df, win_model, feature_cols)

    # 4. Winner Probability Trajectories
    logger.info("Tracking eventual winner probability trajectories...")
    winner_trajectories = analyze_winner_probability_trajectories(eval_df, win_model, feature_cols)

    # 5. Finish Position Model Sanity Check
    logger.info("Performing finish position model sanity check...")
    pos_sanity = analyze_finish_position_model(eval_df, finish_model, feature_cols)

    # 6. Save JSON Artifacts
    stage_metrics_file = out_dir / "stage_metrics.json"
    with open(stage_metrics_file, "w") as f:
        json.dump(stage_metrics, f, indent=2)

    trajectories_file = out_dir / "winner_probability_trajectories.json"
    with open(trajectories_file, "w") as f:
        json.dump(winner_trajectories, f, indent=2)

    calib_file = calib_dir / "calibration_10bin_data.json"
    with open(calib_file, "w") as f:
        json.dump(calib_10bin, f, indent=2)

    sanity_summary = {
        "split_summary": split_summary,
        "stage_metrics": stage_metrics,
        "probability_sums": sum_analysis,
        "calibration_10bin": calib_10bin,
        "winner_trajectories": winner_trajectories,
        "finish_position_sanity": pos_sanity,
    }

    sanity_file = out_dir / "prediction_sanity_report.json"
    with open(sanity_file, "w") as f:
        json.dump(sanity_summary, f, indent=2)

    logger.info("Analysis complete. Generated artifacts in %s and %s", out_dir, calib_dir)
    return sanity_summary


def main():
    parser = argparse.ArgumentParser(description="Analyze F1 model predictions across stages.")
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET_CSV), help="Dataset CSV path")
    parser.add_argument("--output-dir", type=str, default=str(ARTIFACTS_DIR / "metrics"), help="Output directory")
    args = parser.parse_args()

    ds_path = Path(args.dataset)
    out_dir = Path(args.output_dir)

    summary = run_full_prediction_analysis(dataset_path=ds_path, output_dir=out_dir)

    print("\n==================================================")
    print("      STAGE-WISE PREDICTION & SANITY REPORT      ")
    print("==================================================")
    print("1. STAGE-WISE WIN MODEL EVALUATION:")
    for st, m in summary["stage_metrics"].items():
        print(f"   Stage: {st:<16} | LogLoss: {m['log_loss']:.4f} | Brier: {m['brier_score']:.4f} | Avg Winner Prob: {m['avg_winner_predicted_prob']*100:.1f}%")

    print("\n2. RACE PROBABILITY SUM SANITY CHECK:")
    sums = summary["probability_sums"]
    print(f"   Mean Sum per Race: {sums['mean_sum']:.4f}")
    print(f"   Min Sum per Race:  {sums['min_sum']:.4f}")
    print(f"   Max Sum per Race:  {sums['max_sum']:.4f}")
    print(f"   Note: {sums['note']}")

    print("\n3. EVENTUAL WINNER PROBABILITY TRAJECTORIES:")
    for traj in summary["winner_trajectories"]:
        probs_str = " -> ".join([f"{st}: {p*100:.1f}%" for st, p in traj["stage_probabilities"].items()])
        print(f"   Race {traj['race_identifier']} (Winner: {traj['winner_driver_code']}): {probs_str}")

    print("\n4. FINISH POSITION MODEL SANITY CHECK:")
    pos = summary["finish_position_sanity"]
    print(f"   MAE:                 {pos['mae']:.4f}")
    print(f"   RMSE:                {pos['rmse']:.4f}")
    print(f"   Min Predicted Pos:   {pos['min_predicted_position']:.2f}")
    print(f"   Max Predicted Pos:   {pos['max_predicted_position']:.2f}")
    print(f"   Out-of-Bounds Count: {pos['out_of_grid_bounds_count']}")
    print(f"   Sanity Status:       {pos['sanity_status']}")
    print("==================================================")
    print(f"Stage metrics saved to: {out_dir / 'stage_metrics.json'}")
    print(f"Trajectories saved to:  {out_dir / 'winner_probability_trajectories.json'}")


if __name__ == "__main__":
    main()
