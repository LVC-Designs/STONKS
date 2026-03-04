# STONKS - North America Market Analyzer

Screen tickers across US + Canada + OTC + NEO markets, compute technical indicators, and generate ranked bullish signals with scoring.

**DISCLAIMER: This tool provides probabilistic scoring for educational and research purposes only. It does NOT constitute financial advice. No "guaranteed predictions" are made. Past performance does not guarantee future results. Do not use this tool for real money trading decisions.**

## Architecture

- **Backend**: Python / FastAPI with async SQLAlchemy
- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS)
- **Database**: PostgreSQL 16 via Docker Compose
- **Market Data**: Polygon.io (working adapter) + Yahoo/AlphaVantage (stubs)
- **News Data**: Finnhub (working adapter) + Yahoo News/NewsAPI (stubs)
- **Charting**: TradingView Lightweight Charts
- **Jobs**: APScheduler (AsyncIO scheduler)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 1. Start Database

```bash
docker compose up -d
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Download NLTK data (for sentiment analysis)
python -c "import nltk; nltk.download('vader_lexicon')"

# Copy and configure environment
cp ../.env.example .env
# Edit .env with your Polygon.io and Finnhub API keys

# Run database migrations
alembic upgrade head

# Seed default settings
python -c "
import asyncio
from app.database import async_session_factory
from app.services.settings_service import seed_default_settings
async def seed():
    async with async_session_factory() as db:
        await seed_default_settings(db)
asyncio.run(seed())
"

# Start the backend
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Access the App

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### 5. Load Data

1. Go to Settings page (http://localhost:3000/settings)
2. Enter your Polygon.io and Finnhub API keys
3. Click "Run" next to "Daily Refresh" to populate the database

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://stonks:stonks_dev@localhost:5432/stonks` |
| `POLYGON_API_KEY` | Polygon.io API key | (required) |
| `FINNHUB_API_KEY` | Finnhub API key | (required) |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |
| `SIGNAL_TARGET_PCT` | Default target % for signal success | `5.0` |
| `SIGNAL_TARGET_DAYS` | Default target days | `20` |
| `SIGNAL_MAX_DRAWDOWN_PCT` | Default max drawdown % | `-3.0` |

## Pages

- `/screener` — Filterable, sortable table of ranked bullish candidates with CSV export
- `/ticker/[symbol]` — Chart + indicator panel + signal card + reasons + news/sentiment
- `/settings` — API keys, signal thresholds, and manual job triggers

## Technical Indicators

| Category | Indicators |
|----------|-----------|
| Trend | SMA (50/100/200), EMA (9/20/50), Ichimoku (9,26,52) |
| Momentum | RSI (14), MACD (12,26,9), Stochastic (14,3,3), ROC (12), CCI (20), ADX (14) |
| Volume | OBV, Volume SMA (20), Volume Ratio, OBV Slope |
| Volatility | Bollinger Bands (20,2), ATR (14), ATR Percentile |
| Structure | Higher Highs/Lows, Breakout Detection, Fibonacci Retracement |

## Signal Scoring

Composite score (0-100) from weighted sub-scores with ADX-based regime adjustment:

| Component | Default | Ranging (ADX<20) | Strong Trend (ADX>30) |
|-----------|---------|-------------------|-----------------------|
| Trend | 30% | 10% | 40% |
| Momentum | 25% | 35% | 20% |
| Volume | 15% | 15% | 15% |
| Volatility | 10% | 15% | 5% |
| Structure | 20% | 25% | 20% |

## Scientific Validity

- **No lookahead bias**: Indicators for day T use only data through close of day T
- **No survivorship bias**: Historical ticker universe snapshots captured daily
- **Timestamped sentiment**: News filtered by publication time before signal generation
- **Walk-forward validation**: Scaffold for train/validation/out-of-sample testing (Phase 2)
- **Signal decay monitoring**: Outcome tracker evaluates pending signals

## Prediction Target

A bullish signal is considered successful if:
- Price increases >= X% within Y trading days
- AND maximum drawdown during that window <= Z%

Default: +5% within 20 trading days, max drawdown -3%. Configurable in the UI.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/screener` | Filtered, sorted, paginated screener |
| GET | `/api/screener/export` | CSV export |
| GET | `/api/tickers/{symbol}` | Ticker detail |
| GET | `/api/tickers/{symbol}/ohlcv` | OHLCV bars |
| GET | `/api/tickers/{symbol}/indicators` | Indicator values |
| GET | `/api/tickers/{symbol}/signals` | Signal history |
| GET | `/api/tickers/{symbol}/news` | News with sentiment |
| GET | `/api/settings` | All settings |
| PUT | `/api/settings/{key}` | Update setting |
| GET | `/api/jobs` | Job history |
| POST | `/api/jobs/{name}/trigger` | Trigger job |

## Phase 2 (Planned)

- Backtest runner with walk-forward validation
- Portfolio simulation (equity curve, Sharpe ratio, max drawdown)
- Signal decay monitoring dashboard
- Multi-timeframe indicators
- Bot/spam filtering for social data (Reddit/X)
- VWAP (intraday)
- Futures support
