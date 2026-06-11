"""Beijing time (UTC+8) helpers — all server-side timestamps use this."""
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """Return current datetime in Beijing time (UTC+8, China Standard Time)."""
    return datetime.now(BEIJING_TZ)


def beijing_now_naive() -> datetime:
    """Return current datetime in Beijing time without tzinfo (for DB storage)."""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)
