FROM python:3.12-slim

WORKDIR /app

# Install system deps for numpy/pandas compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt asyncpg
# Install CPU-only PyTorch (much smaller than full torch with CUDA)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Download NLTK data for VADER sentiment
RUN python -c "import nltk; nltk.download('vader_lexicon', download_dir='/usr/local/nltk_data')"

# Copy backend code
COPY backend/ .

# Create model artifacts directory
RUN mkdir -p /app/models/signal_scorer /app/models/pattern_recognizer \
    /app/models/price_predictor /app/models/strategy_selector

# Alembic + app need PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
