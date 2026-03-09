"""ML configuration constants."""

import os
import torch

# Device selection
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Model artifacts directory
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")

# Training defaults
DEFAULT_EPOCHS = 50
DEFAULT_BATCH_SIZE = 64
DEFAULT_LR = 0.001
DEFAULT_WEIGHT_DECAY = 1e-5
DEFAULT_DROPOUT = 0.3
DEFAULT_PATIENCE = 8  # Early stopping patience

# Walk-forward defaults
DEFAULT_TRAIN_MONTHS = 12
DEFAULT_VAL_MONTHS = 3
DEFAULT_TEST_MONTHS = 3
DEFAULT_STEP_MONTHS = 3

# Signal scorer
SIGNAL_SCORER_HIDDEN = 128
SIGNAL_SCORER_INPUT_DIM = 55  # 45 indicators + 5 sub-scores + 3 regime + 2 price-relative

# Pattern recognizer
PATTERN_WINDOW = 60
PATTERN_CHANNELS = 6  # OHLCV + returns
NUM_PATTERNS = 11

# Price predictor
PRICE_SEQ_LEN = 60
PRICE_INPUT_DIM = 51  # 5 OHLCV + 45 indicators + 1 regime
PRICE_HIDDEN = 128
PRICE_HORIZONS = (5, 10, 20)

# Strategy selector
STRATEGY_INPUT_DIM = 30  # Aggregate market features

# Minimum data requirements
MIN_TRAINING_SAMPLES = 20
MIN_BARS_FOR_INDICATORS = 50

# Model types
MODEL_TYPES = ["signal_scorer", "pattern_recognizer", "price_predictor", "strategy_selector"]
