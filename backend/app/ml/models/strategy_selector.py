"""Strategy Selector Meta-Learner.

Feed-forward NN that predicts the optimal backtest parameter combination
given current market conditions (cross-ticker aggregate indicators).
"""

import torch
import torch.nn as nn


class StrategySelectorNet(nn.Module):
    """Predict optimal strategy config from market conditions.

    Input: (batch, 30) — aggregate market condition features
    Output: (batch, num_configs) — logits for each known strategy configuration
    """

    def __init__(
        self,
        input_dim: int = 30,
        num_configs: int = 108,
        hidden_dim: int = 128,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.num_configs = num_configs
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(hidden_dim // 2, num_configs),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    @torch.no_grad()
    def recommend(self, x: torch.Tensor, config_map: list[dict]) -> dict:
        """Inference helper returning recommended config with confidence."""
        self.eval()
        logits = self.forward(x)
        probs = torch.softmax(logits, dim=-1)
        if probs.dim() == 2:
            probs = probs[0]
        top_idx = probs.argmax().item()
        confidence = probs[top_idx].item()
        if top_idx < len(config_map):
            return {
                "recommended_config": config_map[top_idx],
                "confidence": round(confidence, 4),
                "top_3": [
                    {"config": config_map[i.item()], "probability": round(probs[i.item()].item(), 4)}
                    for i in probs.argsort(descending=True)[:3]
                    if i.item() < len(config_map)
                ],
            }
        return {"recommended_config": None, "confidence": 0}
