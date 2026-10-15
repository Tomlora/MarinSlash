from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .models import Competition

SCHEDULE_MAX_AGE = timedelta(hours=3)


def stale_competitions(connection, now: datetime) -> frozenset[Competition]:
    """A recent import must cover the entire Paris day, including early matches."""
    paris = ZoneInfo('Europe/Paris')
    day = now.astimezone(paris).date()
    start = datetime.combine(day, time.min, tzinfo=paris)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=paris)
    rows = connection.execute(text('''
        SELECT competition_code FROM fantasy.schedule_coverage
        WHERE refreshed_at >= :cutoff AND refreshed_at <= :now
          AND window_start <= :start AND window_end >= :end
    '''), {'cutoff': now - SCHEDULE_MAX_AGE, 'now': now, 'start': start, 'end': end}).all()
    return frozenset(set(Competition) - {Competition(row.competition_code) for row in rows})
