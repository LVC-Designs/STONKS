"""
Import S&P 500 tickers and fetch OHLCV data from Polygon.io.

Usage:
    cd backend
    source .venv/Scripts/activate
    PYTHONPATH=. python scripts/import_sp500.py

Rate limits (Polygon free tier): 5 requests/minute
- Ticker inserts: ~0 API calls (direct DB inserts)
- OHLCV fetches: 1 API call per ticker → ~470 tickers ≈ 94 minutes

The script is resumable — it skips tickers that already have OHLCV data.
"""

import asyncio
import logging
import sys
import time
from datetime import date, timedelta

from sqlalchemy import select, func

# Ensure app modules are importable
sys.path.insert(0, ".")

from app.database import async_session_factory, engine
from app.models.ticker import Ticker
from app.models.ohlcv import OHLCVDaily
from app.adapters.polygon_adapter import PolygonAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("import_sp500")

# ─── Complete S&P 500 Constituent List (as of March 2026) ──────────────────
# 503 ticker symbols (some companies have dual share classes: GOOGL/GOOG, BRK.B, BF.B, FOX/FOXA, NWS/NWSA)
SP500_SYMBOLS = [
    "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM", "ADP",
    "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB",
    "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT",
    "AMZN", "ANET", "AON", "AOS", "APA", "APD", "APH", "APO", "APTV", "ARE",
    "ARES", "AVGO", "AVB", "AVY", "AWK", "AXON", "AXP", "AZO",
    "BA", "BAC", "BALL", "BAX", "BBY", "BDX", "BEN", "BF.B", "BG", "BIIB",
    "BK", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BR", "BRK.B", "BRO", "BSX",
    "BX", "BXP",
    "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CCI", "CCL", "CDNS",
    "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI", "CIEN",
    "CINF", "CL", "CLX", "CMS", "CNC", "CNP", "COF", "COIN", "COO", "COP",
    "COR", "COST", "CPAY", "CPB", "CPRT", "CPT", "CRH", "CRL", "CRM", "CSCO",
    "CSGP", "CTAS", "CTRA", "CTSH", "CTVA", "CVNA",
    "CVS", "CVX",
    "D", "DAL", "DASH", "DD", "DDOG", "DE", "DECK", "DELL", "DFS", "DG",
    "DGX", "DHI", "DHR", "DIS", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE",
    "DUK", "DVA", "DVN", "DXCM",
    "EA", "EBAY", "ECL", "ED", "EFX", "EIX", "EL", "EME", "EMR", "ENPH",
    "EOG", "EPAM", "EQIX", "EQR", "EQT", "ERIE", "ES", "ESS", "ETN", "ETR",
    "EVRG", "EW", "EXC", "EXE", "EXPE", "EXPD", "EXR",
    "F", "FANG", "FAST", "FBIN", "FCX", "FDS", "FDX", "FE", "FFIV", "FICO",
    "FIS", "FISV", "FITB", "FIX", "FOXA", "FOX", "FRT", "FSLR", "FTNT", "FTV",
    "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD", "GIS", "GL", "GLW",
    "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW",
    "HAL", "HAS", "HBAN", "HCA", "HD", "HOLX", "HON", "HOOD", "HPE", "HPQ",
    "HRL", "HSIC", "HST", "HSY", "HUBB", "HUM", "HWM", "HII",
    "IBM", "ICE", "IDXX", "IEX", "IFF", "INCY", "INTC", "INTU", "INVH", "IP",
    "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ",
    "J", "JBHT", "JCI", "JBL", "JKHY", "JNJ", "JPM",
    "K", "KDP", "KEY", "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI",
    "KO", "KR",
    "L", "LDOS", "LEN", "LH", "LHX", "LII", "LIN", "LKQ", "LRCX", "LULU",
    "LUV", "LVS", "LW", "LYB", "LYV", "LNT",
    "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT",
    "MET", "META", "MGM", "MKC", "MKTX", "MLM", "MMM", "MNST", "MO", "MOH",
    "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRSH", "MS", "MSCI", "MSFT", "MSI",
    "MTB", "MTCH", "MTD", "MU",
    "NCLH", "NDAQ", "NDSN", "NEM", "NEE", "NFLX", "NI", "NKE", "NOC", "NOW",
    "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWS", "NWSA", "NXPI",
    "O", "ODFL", "OKE", "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY",
    "PANW", "PARA", "PAYC", "PAYX", "PCAR", "PCG", "PEG", "PEP", "PFE", "PFG",
    "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PLTR", "PM", "PNC", "PNR",
    "PNW", "PODD", "POOL", "PPG", "PPL", "PRU", "PSA", "PSX", "PTC", "PVH",
    "PWR",
    "Q", "QCOM", "QRVO",
    "REGN", "REG", "RF", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST",
    "RSG", "RTX", "RVTY",
    "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA", "SNDK",
    "SNPS", "SO", "SOLV", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX",
    "STZ", "SW", "SWK", "SWKS", "SYF", "SYK", "SYY",
    "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TGT", "TJX",
    "TKO", "TMO", "TMUS", "TPL", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO",
    "TSLA", "TSN", "TT", "TTD", "TTWO", "TXT", "TYL",
    "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB",
    "V", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRTX", "VST", "VTR",
    "VTRS", "VZ",
    "WAB", "WAT", "WBA", "WBD", "WDC", "WEC", "WELL", "WFC", "WM", "WMB",
    "WMT", "WRB", "WSM", "WST", "WTW", "WY", "WYNN",
    "XEL", "XOM", "XYL", "XYZ",
    "YUM",
    "ZBH", "ZBRA", "ZTS",
]


async def get_existing_symbols(db) -> set[str]:
    """Get symbols already in the database."""
    result = await db.execute(select(Ticker.symbol).where(Ticker.active == True))
    return {row[0] for row in result.all()}


async def get_tickers_with_ohlcv(db) -> set[str]:
    """Get symbols that already have OHLCV data."""
    result = await db.execute(
        select(Ticker.symbol)
        .join(OHLCVDaily, OHLCVDaily.ticker_id == Ticker.id)
        .where(Ticker.active == True)
        .group_by(Ticker.symbol)
        .having(func.count(OHLCVDaily.id) > 50)
    )
    return {row[0] for row in result.all()}


async def insert_missing_tickers(db, symbols: list[str], existing: set[str]) -> int:
    """Insert S&P 500 tickers that don't exist in DB yet. No API calls needed."""
    added = 0
    for symbol in symbols:
        if symbol in existing:
            continue

        # Check for exact duplicate (including inactive)
        result = await db.execute(
            select(Ticker).where(Ticker.symbol == symbol)
        )
        row = result.scalar_one_or_none()

        if row:
            # Reactivate if inactive
            if not row.active:
                row.active = True
                row.exchange_group = "US"
                logger.info(f"  Reactivated: {symbol}")
                added += 1
        else:
            # Determine exchange - most S&P 500 are NYSE or NASDAQ
            exchange = "NASDAQ" if symbol in NASDAQ_SYMBOLS else "NYSE"
            db.add(Ticker(
                symbol=symbol,
                name=symbol,  # Will be updated when we fetch from Polygon
                exchange=exchange,
                exchange_group="US",
                country="US",
                currency="USD",
                asset_type="stock",
                is_otc=False,
                is_neo=False,
                active=True,
                polygon_ticker=symbol,
                finnhub_ticker=symbol,
            ))
            added += 1
            logger.info(f"  Inserted: {symbol} ({exchange})")

    await db.commit()
    return added


# Known NASDAQ-listed S&P 500 companies
NASDAQ_SYMBOLS = {
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "ALGN", "AMAT",
    "AMD", "AMGN", "AMZN", "ANET", "ANSS", "APP", "ASML", "AVGO", "AZN",
    "BIIB", "BKNG", "BKR", "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA",
    "COIN", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CTAS", "CTSH", "DASH",
    "DDOG", "DLTR", "DXCM", "EA", "EBAY", "ENPH", "EXC", "FANG", "FAST",
    "FFIV", "FISV", "FTNT", "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HOOD",
    "IDXX", "ILMN", "INTC", "INTU", "ISRG", "JD", "KDP", "KHC", "KLAC",
    "LRCX", "LULU", "MAR", "MCHP", "MDLZ", "MELI", "META", "MNST", "MPWR",
    "MRNA", "MRVL", "MSFT", "MU", "NCLH", "NDAQ", "NFLX", "NTAP", "NXPI",
    "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR",
    "PYPL", "QCOM", "QRVO", "REGN", "ROST", "SBUX", "SMCI", "SNPS", "SPLK",
    "TEAM", "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WDAY",
    "XEL", "ZS",
}


async def fetch_ohlcv_for_ticker(adapter: PolygonAdapter, db, ticker: Ticker) -> int:
    """Fetch 2 years of OHLCV data for a single ticker."""
    # Check last cached date
    result = await db.execute(
        select(OHLCVDaily.trade_date)
        .where(OHLCVDaily.ticker_id == ticker.id)
        .order_by(OHLCVDaily.trade_date.desc())
        .limit(1)
    )
    last_date = result.scalar_one_or_none()

    start = last_date + timedelta(days=1) if last_date else date.today() - timedelta(days=365 * 2)
    end = date.today()

    if start > end:
        return 0

    try:
        bars = await adapter.get_ohlcv(ticker.symbol, "day", start, end)
    except Exception as e:
        logger.warning(f"  Failed to fetch OHLCV for {ticker.symbol}: {e}")
        return -1

    count = 0
    for bar in bars:
        # Skip duplicates
        existing = await db.execute(
            select(OHLCVDaily.id).where(
                OHLCVDaily.ticker_id == ticker.id,
                OHLCVDaily.trade_date == bar.date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(OHLCVDaily(
            ticker_id=ticker.id,
            trade_date=bar.date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            vwap=bar.vwap,
            source="polygon",
        ))
        count += 1

    await db.commit()
    return count


async def main():
    logger.info("=" * 60)
    logger.info("S&P 500 Ticker Import")
    logger.info("=" * 60)

    # Deduplicate the symbol list
    seen = set()
    unique_symbols = []
    for s in SP500_SYMBOLS:
        if s not in seen:
            seen.add(s)
            unique_symbols.append(s)
    logger.info(f"Unique S&P 500 symbols: {len(unique_symbols)}")

    async with async_session_factory() as db:
        # Phase 1: Insert missing tickers (no API calls)
        logger.info("\n--- Phase 1: Insert Missing Tickers ---")
        existing = await get_existing_symbols(db)
        logger.info(f"Existing tickers in DB: {len(existing)}")

        missing = [s for s in unique_symbols if s not in existing]
        logger.info(f"Missing tickers to add: {len(missing)}")

        if missing:
            added = await insert_missing_tickers(db, unique_symbols, existing)
            logger.info(f"Added {added} new tickers to DB")
        else:
            logger.info("All S&P 500 tickers already in DB!")

        # Phase 2: Fetch OHLCV data (rate-limited)
        logger.info("\n--- Phase 2: Fetch OHLCV Data ---")
        tickers_with_data = await get_tickers_with_ohlcv(db)
        logger.info(f"Tickers already having OHLCV data (>50 bars): {len(tickers_with_data)}")

        # Get all S&P 500 tickers from DB
        result = await db.execute(
            select(Ticker).where(
                Ticker.symbol.in_(unique_symbols),
                Ticker.active == True,
            ).order_by(Ticker.symbol)
        )
        all_tickers = list(result.scalars().all())

        # Filter to tickers needing OHLCV data
        tickers_needing_data = [t for t in all_tickers if t.symbol not in tickers_with_data]
        logger.info(f"Tickers needing OHLCV fetch: {len(tickers_needing_data)}")

        if not tickers_needing_data:
            logger.info("All tickers already have OHLCV data!")
            return

        # Estimate time
        est_minutes = len(tickers_needing_data) / 5
        logger.info(f"Estimated time: ~{est_minutes:.0f} minutes ({len(tickers_needing_data)} tickers at 5 req/min)")
        logger.info("Starting OHLCV fetch (Ctrl+C to stop — script is resumable)...\n")

        adapter = PolygonAdapter()
        success = 0
        failed = 0
        start_time = time.time()

        try:
            for i, ticker in enumerate(tickers_needing_data, 1):
                elapsed = time.time() - start_time
                rate = success / (elapsed / 60) if elapsed > 60 else 0
                eta = (len(tickers_needing_data) - i) / 5 if i > 1 else est_minutes
                logger.info(
                    f"[{i}/{len(tickers_needing_data)}] Fetching {ticker.symbol}... "
                    f"(elapsed: {elapsed/60:.1f}m, ETA: {eta:.0f}m, rate: {rate:.1f}/min)"
                )

                bars = await fetch_ohlcv_for_ticker(adapter, db, ticker)
                if bars >= 0:
                    success += 1
                    logger.info(f"  ✓ {ticker.symbol}: {bars} new bars cached")
                else:
                    failed += 1

                # Progress checkpoint every 25 tickers
                if i % 25 == 0:
                    total_elapsed = (time.time() - start_time) / 60
                    logger.info(f"\n--- Checkpoint: {success} success, {failed} failed, {total_elapsed:.1f}m elapsed ---\n")

        except KeyboardInterrupt:
            logger.info(f"\n\nInterrupted! Progress saved. {success} tickers fetched, {failed} failed.")
            logger.info("Re-run the script to continue from where you left off.")
        finally:
            await adapter.close()

        total_time = (time.time() - start_time) / 60
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Import complete in {total_time:.1f} minutes")
        logger.info(f"  Success: {success}")
        logger.info(f"  Failed:  {failed}")

        # Final count
        total = await db.execute(
            select(func.count(Ticker.id)).where(Ticker.active == True)
        )
        logger.info(f"  Total active tickers in DB: {total.scalar()}")

        ohlcv_count = await db.execute(select(func.count(OHLCVDaily.id)))
        logger.info(f"  Total OHLCV bars in DB: {ohlcv_count.scalar()}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
