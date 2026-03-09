"""Signal Scorer Neural Network.

Feed-forward NN with residual connections that predicts signal outcome
probability (win/loss/timeout) from indicator features + rule-based sub-scores.
"""

import torch
import torch.nn as nn


class SignalScorerNet(nn.Module):
    """Predict signal outcome from indicator features.

    Input: (batch, input_dim) — normalized indicator values + sub-scores + regime
    Output: (batch, 3) — logits for [win, loss, timeout]

    nn_score is derived as: softmax(logits)[0] * 100, bounded 0-100.
    """

    def __init__(self, input_dim: int = 55, hidden_dim: int = 128, dropout: float = 0.3):
        super().__init__()
        self.input_bn = nn.BatchNorm1d(input_dim)

        self.block1 = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.block2 = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.block3 = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
        )
        self.head = nn.Linear(hidden_dim // 2, 3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_bn(x)
        h1 = self.block1(x)
        h2 = self.block2(h1)
        h2 = h2 + h1  # Residual connection
        h3 = self.block3(h2)
        return self.head(h3)

    @torch.no_grad()
    def predict_score(self, x: torch.Tensor) -> tuple[float, float]:
        """Inference helper returning (nn_score 0-100, confidence 0-1)."""
        self.eval()
        logits = self.forward(x)
        probs = torch.softmax(logits, dim=-1)
        win_prob = probs[0, 0].item() if x.dim() == 2 else probs[0].item()
        confidence = probs.max(dim=-1).values.item()
        nn_score = round(min(max(win_prob * 100, 0), 100), 2)
        return nn_score, round(confidence, 4)
