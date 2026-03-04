from datetime import date, timedelta


def is_trading_day(d: date) -> bool:
    """Check if a date is a trading day (weekday only, no holiday check)."""
    return d.weekday() < 5


def previous_trading_day(d: date) -> date:
    """Get the most recent trading day on or before date d."""
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def trading_days_back(from_date: date, n: int) -> date:
    """Go back N trading days from a given date."""
    d = from_date
    count = 0
    while count < n:
        d -= timedelta(days=1)
        if is_trading_day(d):
            count += 1
    return d
