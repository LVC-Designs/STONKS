"""Walk-forward validation splitter for ML training."""

from datetime import date, timedelta


def _months_delta(d: date, months: int) -> date:
    return d + timedelta(days=int(months * 30.44))


def generate_walk_forward_splits(
    date_from: date,
    date_to: date,
    train_months: int = 12,
    val_months: int = 3,
    test_months: int = 3,
    step_months: int = 3,
) -> list[dict]:
    """Generate walk-forward train/val/test splits.

    Returns list of dicts with date ranges for each fold.
    """
    total_window = train_months + val_months + test_months
    folds = []
    cursor = date_from

    while True:
        train_start = cursor
        train_end = _months_delta(train_start, train_months) - timedelta(days=1)
        val_start = _months_delta(train_start, train_months)
        val_end = _months_delta(train_start, train_months + val_months) - timedelta(days=1)
        test_start = _months_delta(train_start, train_months + val_months)
        test_end = _months_delta(train_start, total_window) - timedelta(days=1)

        if test_end > date_to:
            break

        folds.append({
            "fold": len(folds),
            "train": (train_start, train_end),
            "val": (val_start, val_end),
            "test": (test_start, test_end),
        })
        cursor = _months_delta(cursor, step_months)

    return folds
