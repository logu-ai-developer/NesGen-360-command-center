"""Shared time-window framework. Every page and tool derives its period from here; no page computes its own.

1 Month = 30 days, 3 Months = 90 days, 6 Months = 180 days (fixed day counts, never calendar months).
Windows are inclusive of both ends: window_start .. window_end covers exactly window_days calendar days.
Deterministic and free of any model call.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

WINDOW_DAYS = {'1 Month': 30, '3 Months': 90, '6 Months': 180}
DEFAULT_WINDOW = '6 Months'
DAY = pd.Timedelta(days=1)


def _naive(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert('UTC').tz_localize(None)
    return ts.normalize()


def today_utc() -> pd.Timestamp:
    return _naive(pd.Timestamp.now(tz='UTC'))


@dataclass(frozen=True)
class TimeWindow:
    key: str
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    window_days: int
    window_label: str

    def mask(self, dates) -> pd.Series:
        """True for dates inside the window; missing/unparseable dates and anything after window_end are outside."""
        d = _dates(dates)
        return (d >= self.window_start) & (d < self.window_end + DAY)

    def as_dict(self) -> dict:
        return {'window': self.key, 'window_start': str(self.window_start.date()), 'window_end': str(self.window_end.date()),
                'window_days': self.window_days, 'window_label': self.window_label}


def _dates(values) -> pd.Series:
    s = pd.Series(values) if not isinstance(values, pd.Series) else values
    return pd.to_datetime(s, errors='coerce', utc=True, format='mixed').dt.tz_localize(None)


def resolve_window(key: str = DEFAULT_WINDOW, as_of=None) -> TimeWindow:
    """The window of WINDOW_DAYS[key] days ending (inclusive) on `as_of` (default: today, UTC)."""
    if key not in WINDOW_DAYS:
        raise ValueError(f'Unknown time window {key!r}; use one of {list(WINDOW_DAYS)}')
    days = WINDOW_DAYS[key]
    end = today_utc() if as_of is None else _naive(as_of)
    return TimeWindow(key, end - pd.Timedelta(days=days - 1), end, days, f'Last {days} days')


def previous_window(window: TimeWindow) -> TimeWindow:
    """The equally long window that ends the day before `window` starts."""
    end = window.window_start - DAY
    return TimeWindow(window.key, end - pd.Timedelta(days=window.window_days - 1), end, window.window_days, f'Previous {window.window_days} days')


def anchor_date(*date_series, today=None) -> pd.Timestamp:
    """Latest non-future date across the given series, else today. Keeps windows on real data even when it is not current."""
    limit = _naive(today) if today is not None else today_utc()
    latest = None
    for series in date_series:
        d = _dates(series).dropna()
        d = d[d < limit + DAY]
        if len(d) and (latest is None or d.max() > latest):
            latest = d.max()
    return latest.normalize() if latest is not None else limit


def filter_by_window(df: pd.DataFrame, date_col: str, window: TimeWindow) -> pd.DataFrame:
    return df[window.mask(df[date_col])] if date_col in df else df.iloc[0:0]


def count_in_window(df: pd.DataFrame, date_col: str, window: TimeWindow) -> int:
    return int(window.mask(df[date_col]).sum()) if date_col in df else 0


def describe_basis(window: TimeWindow, date_field: str, source_mode: str) -> str:
    """Transparency line: selected window, the date field it filters on, and the source mode."""
    return (f'{window.window_label} ({window.window_start:%Y-%m-%d} to {window.window_end:%Y-%m-%d}) · '
            f'date field: {date_field} · source: {source_mode}')


# ---- Trend helpers --------------------------------------------------------------------------------
def period_counts(dates, window: TimeWindow, bucket_days: int = 7) -> pd.DataFrame:
    """Counts per `bucket_days` bucket across the window (zero-filled). Buckets start at window_start; the last may be shorter."""
    d = _dates(dates)
    d = d[window.mask(d)]
    starts = pd.date_range(window.window_start, window.window_end, freq=f'{bucket_days}D')
    offsets = ((d - window.window_start).dt.days // bucket_days).astype(int)
    counts = offsets.value_counts().reindex(range(len(starts)), fill_value=0).sort_index()
    return pd.DataFrame({'period_start': starts, 'count': counts.to_numpy()})


def rolling_counts(counts, periods: int) -> pd.Series:
    """Rolling sum over `periods` buckets (partial at the start)."""
    return pd.Series(counts).rolling(periods, min_periods=1).sum()


def period_total(df: pd.DataFrame, value_col: str, date_col: str, window: TimeWindow) -> float:
    w = filter_by_window(df, date_col, window)
    return float(pd.to_numeric(w[value_col], errors='coerce').sum()) if len(w) else 0.0


def period_average(df: pd.DataFrame, value_col: str, date_col: str, window: TimeWindow):
    """Unweighted mean of the values in the window; None when there are none."""
    w = filter_by_window(df, date_col, window)
    values = pd.to_numeric(w[value_col], errors='coerce').dropna() if len(w) else pd.Series(dtype=float)
    return float(values.mean()) if len(values) else None


def trend_direction(current, previous, rel_tol: float = 0.05, abs_tol=None):
    """'increasing' | 'decreasing' | 'stable', or None when either value is unavailable.

    abs_tol (for percentages): stable when |current - previous| <= abs_tol. Otherwise stable when the relative
    change is within rel_tol; a rise from zero is 'increasing'.
    """
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return None
    diff = current - previous
    if abs_tol is not None:
        return 'stable' if abs(diff) <= abs_tol else ('increasing' if diff > 0 else 'decreasing')
    if previous == 0:
        return 'stable' if current == 0 else ('increasing' if current > 0 else 'decreasing')
    change = diff / abs(previous)
    return 'stable' if abs(change) <= rel_tol else ('increasing' if change > 0 else 'decreasing')


# ---- Model lifecycle dates ------------------------------------------------------------------------
LIFECYCLE_DATE_FIELDS = [('last_review_date', 'Last review'), ('review_due_date', 'Review due'), ('next_review_date', 'Next review'),
                         ('retirement_decision_date', 'Retirement decision'), ('retire_date', 'Retire date'), ('migration_date', 'Migration')]


def lifecycle_date_counts(models: pd.DataFrame, window: TimeWindow) -> dict:
    """Models with each lifecycle date inside the window. Only fields that carry at least one date are reported."""
    out = {}
    for col, label in LIFECYCLE_DATE_FIELDS:
        if col in models and _dates(models[col]).notna().any():
            out[label] = count_in_window(models, col, window)
    return out


# Only dates of things that already happened anchor the window; planning dates (next review, retire date) never do,
# so a window cannot drift with the wall clock because of a future-facing field.
LIFECYCLE_ANCHOR_FIELDS = ('last_review_date', 'review_due_date', 'retirement_decision_date', 'migration_date')


def lifecycle_anchor(models: pd.DataFrame, today=None) -> pd.Timestamp:
    return anchor_date(*[models[c] for c in LIFECYCLE_ANCHOR_FIELDS if c in models], today=today)
