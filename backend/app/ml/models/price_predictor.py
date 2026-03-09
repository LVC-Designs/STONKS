"""Price Prediction LSTM.

Bidirectional LSTM with attention mechanism predicting multi-horizon
price movement (direction + magnitude) from OHLCV + indicator sequences.
"""

import torch
import torch.nn as nn


class PricePredictorNet(nn.Module):
    """Predict price movement over multiple horizons.

    Input: (batch, seq_len=60, features=51)
    Output: (batch, num_horizons * 2) — [direction_logit, magnitude] per horizon
    """

    def __init__(
        self,
        input_dim: int = 51,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        horizons: tuple = (5, 10, 20),
    ):
        super().__init__()
        self.horizons = horizons
        self.hidden_dim = hidden_dim

        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )

        self.attention = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim * 2, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 2),
            )
            for _ in horizons
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        lstm_out, _ = self.lstm(x)
        attn_weights = self.attention(lstm_out)
        attn_weights = torch.softmax(attn_weights, dim=1)
        context = torch.sum(lstm_out * attn_weights, dim=1)
        outputs = [head(context) for head in self.heads]
        return torch.cat(outputs, dim=1)

    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> list[dict]:
        """Inference helper returning predictions per horizon."""
        self.eval()
        out = self.forward(x)
        if out.dim() == 2:
            out = out[0]
        results = []
        for i, h in enumerate(self.horizons):
            direction_logit = out[i * 2].item()
            magnitude = abs(out[i * 2 + 1].item())
            prob_up = torch.sigmoid(torch.tensor(direction_logit)).item()
            results.append({
                "horizon_days": h,
                "direction": "up" if prob_up > 0.5 else "down",
                "probability": round(prob_up if prob_up > 0.5 else 1 - prob_up, 4),
                "magnitude_pct": round(magnitude, 4),
            })
        return results
