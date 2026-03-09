"""PyTorch Dataset classes for ML training."""

import numpy as np
import torch
from torch.utils.data import Dataset


class SignalDataset(Dataset):
    """Dataset for signal scorer training.

    X: (n_samples, n_features) numpy array (already scaled)
    y: (n_samples,) numpy array of class labels (0=win, 1=loss, 2=timeout)
    """

    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class OHLCVWindowDataset(Dataset):
    """Dataset for pattern recognition and price prediction.

    windows: list of dicts with 'tensor' (channels, seq_len) and labels
    """

    def __init__(self, windows: list[dict], task: str = "pattern"):
        self.windows = windows
        self.task = task

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        w = self.windows[idx]
        x = torch.tensor(w["tensor"], dtype=torch.float32)

        if self.task == "pattern":
            # Multi-label: pattern labels (11 dims, 0/1)
            labels = torch.tensor(w.get("pattern_labels", [0] * 11), dtype=torch.float32)
            return x, labels
        elif self.task == "price":
            # Multi-horizon: [dir_5, mag_5, dir_10, mag_10, dir_20, mag_20]
            fwd = w.get("forward_returns", {})
            targets = []
            for h in [5, 10, 20]:
                ret = fwd.get(h, 0)
                targets.append(1.0 if ret > 0 else 0.0)
                targets.append(abs(ret))
            return x.permute(1, 0), torch.tensor(targets, dtype=torch.float32)

        return x, torch.tensor(0)
