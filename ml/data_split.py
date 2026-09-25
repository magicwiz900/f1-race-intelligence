import logging
from typing import Any, Dict, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def chronological_race_split(
    df: pd.DataFrame,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Chronologically split dataset by race boundaries (season, round).
    Ensures that complete races remain together and no single race is split across datasets.
    """
    if df.empty:
        raise ValueError("Cannot split an empty DataFrame.")

    # Extract unique sorted (season, round) race boundaries
    unique_races = (
        df[["season", "round"]]
        .drop_duplicates()
        .sort_values(by=["season", "round"], ascending=True)
        .reset_index(drop=True)
    )

    total_races = len(unique_races)
    if total_races == 0:
        raise ValueError("No race boundaries found in DataFrame.")

    # Calculate race boundary cutoffs
    n_train = max(1, int(round(total_races * train_ratio)))
    n_val = int(round(total_races * val_ratio))
    
    # Ensure train + val does not exceed total_races
    if n_train + n_val >= total_races:
        n_val = max(1, total_races - n_train - 1) if total_races > 2 else 0

    train_races = unique_races.iloc[:n_train]
    val_races = unique_races.iloc[n_train : n_train + n_val]
    test_races = unique_races.iloc[n_train + n_val :]

    # Convert to set of (season, round) tuples for fast lookup
    train_set = set(zip(train_races["season"], train_races["round"]))
    val_set = set(zip(val_races["season"], val_races["round"]))
    test_set = set(zip(test_races["season"], test_races["round"]))

    # Verify zero overlap between race splits
    assert len(train_set.intersection(test_set)) == 0, "Race overlap detected between train and test sets!"
    assert len(train_set.intersection(val_set)) == 0, "Race overlap detected between train and val sets!"
    assert len(val_set.intersection(test_set)) == 0, "Race overlap detected between val and test sets!"

    def in_set(row, target_set):
        return (row["season"], row["round"]) in target_set

    train_df = df[df.apply(lambda r: in_set(r, train_set), axis=1)].copy()
    val_df = df[df.apply(lambda r: in_set(r, val_set), axis=1)].copy()
    test_df = df[df.apply(lambda r: in_set(r, test_set), axis=1)].copy()

    split_summary = {
        "total_races": total_races,
        "train_races": [f"S{s}R{r}" for s, r in train_set],
        "val_races": [f"S{s}R{r}" for s, r in val_set],
        "test_races": [f"S{s}R{r}" for s, r in test_set],
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
    }

    logger.info(
        "Chronological Split: %d train races (%d rows), %d val races (%d rows), %d test races (%d rows)",
        len(train_races),
        len(train_df),
        len(val_races),
        len(val_df),
        len(test_races),
        len(test_df),
    )

    return train_df, val_df, test_df, split_summary
