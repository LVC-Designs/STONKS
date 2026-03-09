"""Pattern Recognition CNN.

Multi-scale 1D CNN that detects chart patterns from OHLCV windows.
Uses parallel convolution branches with different kernel sizes to capture
patterns at short, medium, and long time scales.
"""

import torch
import torch.nn as nn

NUM_PATTERNS = 11
PATTERN_NAMES = [
    "bull_flag", "bear_flag", "double_bottom", "double_top",
    "head_and_shoulders", "inv_head_and_shoulders",
    "ascending_triangle", "descending_triangle",
    "cup_and_handle", "breakout", "consolidation",
]


class PatternRecognizerNet(nn.Module):
    """Detect chart patterns from OHLCV windows.

    Input: (batch, channels=6, seq_len=60)
        Channels: [open, high, low, close, volume, returns] — all normalized
    Output: (batch, 11) — logits for each pattern (multi-label, apply sigmoid)
    """

    def __init__(self, in_channels: int = 6, seq_len: int = 60):
        super().__init__()

        self.conv_short = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=5, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.conv_medium = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=11, padding=5),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=11, padding=5),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.conv_long = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=21, padding=10),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=21, padding=10),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )

        self.merge_conv = nn.Sequential(
            nn.Conv1d(192, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, NUM_PATTERNS),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        s = self.conv_short(x)
        m = self.conv_medium(x)
        lg = self.conv_long(x)
        combined = torch.cat([s, m, lg], dim=1)
        merged = self.merge_conv(combined)
        return self.classifier(merged)

    @torch.no_grad()
    def detect_patterns(self, x: torch.Tensor, threshold: float = 0.5) -> list[dict]:
        """Inference helper returning detected patterns with confidence."""
        self.eval()
        logits = self.forward(x)
        probs = torch.sigmoid(logits)
        if probs.dim() == 2:
            probs = probs[0]
        results = []
        for i, (name, prob) in enumerate(zip(PATTERN_NAMES, probs)):
            p = prob.item()
            if p >= threshold:
                results.append({"pattern": name, "confidence": round(p, 4)})
        return results
