import argparse
import logging
from pathlib import Path
import sys
import pandas as pd

from ml.config import DEFAULT_DATASET_CSV
from ml.datasets.build_dataset import build_ml_dataset
from ml.training.trainer import train_and_evaluate_all_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate F1 Race Intelligence ML models.")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DEFAULT_DATASET_CSV),
        help="Path to engineered ML features CSV dataset",
    )
    args = parser.parse_args()

    ds_path = Path(args.dataset)
    if not ds_path.exists():
        logger.info("Dataset file %s does not exist. Building dataset from database...", ds_path)
        df = build_ml_dataset(output_path=ds_path)
    else:
        logger.info("Loading ML dataset from %s...", ds_path)
        df = pd.read_csv(ds_path)

    if df.empty:
        logger.error("Dataset is empty. Cannot train models.")
        sys.exit(1)

    logger.info("Starting ML model training pipeline...")
    meta = train_and_evaluate_all_models(df)

    print("\n==================================================")
    print("         ML MODEL TRAINING & EVALUATION REPORT    ")
    print("==================================================")
    print(f"Total Features Used: {meta['features_count']}")
    print(f"Train Races Count:   {len(meta['split_summary']['train_races'])}")
    print(f"Val Races Count:     {len(meta['split_summary']['val_races'])}")
    print(f"Test Races Count:    {len(meta['split_summary']['test_races'])}")
    print("--------------------------------------------------")
    print("1. WIN PROBABILITY MODEL (Logistic Regression):")
    win_m = meta["metrics"]["win_probability_model"]
    print(f"   Log Loss:    {win_m['log_loss']:.4f}")
    print(f"   Brier Score: {win_m['brier_score']:.4f}")
    print(f"   ROC-AUC:     {win_m['roc_auc']:.4f}" if win_m['roc_auc'] else "   ROC-AUC:     N/A")
    print(f"   Accuracy:    {win_m['accuracy']:.4f}")

    print("\n2. FINISH POSITION MODEL (Random Forest Regressor):")
    pos_m = meta["metrics"]["finish_position_model"]
    print(f"   MAE:         {pos_m['mae']:.4f}")
    print(f"   RMSE:        {pos_m['rmse']:.4f}")

    print("\n3. PODIUM MODEL (Logistic Regression):")
    pod_m = meta["metrics"]["podium_model"]
    print(f"   Log Loss:    {pod_m['log_loss']:.4f}")
    print(f"   Brier Score: {pod_m['brier_score']:.4f}")

    print("\n4. TOP 5 MODEL (Logistic Regression):")
    top_m = meta["metrics"]["top5_model"]
    print(f"   Log Loss:    {top_m['log_loss']:.4f}")
    print(f"   Brier Score: {top_m['brier_score']:.4f}")
    print("==================================================")
    print("Model artifacts saved to ml/artifacts/models/")
    print("Metrics saved to ml/artifacts/metrics/model_metrics.json")
    print("Calibration saved to ml/artifacts/calibration/calibration_data.json")
    print("Metadata saved to ml/artifacts/metadata/model_metadata.json")


if __name__ == "__main__":
    main()
