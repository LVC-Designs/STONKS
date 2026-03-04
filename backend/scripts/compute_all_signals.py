"""Compute indicators and signals for ALL active tickers using existing OHLCV data.

No API calls - purely local computation. Fast.
"""

import asyncio
import logging
import sys
import time
from datetime import date
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session_factory
from app.services.ticker_service import get_all_active_tickers
from app.services.indicator_service import compute_and_store_indicators
from app.services.signal_service import compute_and_store_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    today = date.today()
    start = time.time()
    success = 0
    skipped = 0
    failed = 0

    async with async_session_factory() as db:
        tickers = await get_all_active_tickers(db)
        total = len(tickers)
        logger.info(f"Computing indicators + signals for {total} tickers...")

        for i, ticker in enumerate(tickers, 1):
            try:
                # Compute indicators from existing OHLCV data
                indicators = await compute_and_store_indicators(db, ticker.id, today)

                if indicators:
                    # Compute signal from indicators
                    await compute_and_store_signal(db, ticker.id, today)
                    success += 1
                else:
                    skipped += 1

                if i % 50 == 0 or i == total:
                    elapsed = time.time() - start
                    rate = i / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        f"[{i}/{total}] {success} scored, {skipped} skipped, "
                        f"{failed} failed ({elapsed:.0f}s, {rate:.0f}/min)"
                    )

            except Exception as e:
                failed += 1
                logger.error(f"Error on {ticker.symbol}: {e}")

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Done in {elapsed:.1f}s")
    logger.info(f"  Scored:  {success}")
    logger.info(f"  Skipped: {skipped} (insufficient OHLCV data)")
    logger.info(f"  Failed:  {failed}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
