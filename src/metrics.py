"""Deterministic metric helpers shared by pages, insight rules, query tools and AI evidence.

No Gemini call and no page-specific formula lives here: classification, percentages, status
normalisation, canonical use-case identity and source-mode vocabulary are defined once.
"""
from __future__ import annotations
import pandas as pd

# ---- Telemetry outcome classification -----------------------------------------------------------
SUCCESS_TRACEPOINT = 'FLOW-END'
FAILURE_TRACEPOINT = 'FLOW-ERROR'
OUTCOMES = ('Successful', 'Failed', 'Unclassified')
NO_CLASSIFIED_NOTE = 'The selected records do not contain enough outcome classification evidence.'


def classify_outcome(tracepoint) -> str:
    """Exactly one of Successful / Failed / Unclassified. A missing marker is never success."""
    if tracepoint == SUCCESS_TRACEPOINT:
        return 'Successful'
    if tracepoint == FAILURE_TRACEPOINT:
        return 'Failed'
    return 'Unclassified'


def outcome_sql(column: str) -> str:
    """SQL twin of classify_outcome for DuckDB; `column` must already be a quoted identifier."""
    return (f"CASE WHEN {column} = '{SUCCESS_TRACEPOINT}' THEN 'Successful' "
            f"WHEN {column} = '{FAILURE_TRACEPOINT}' THEN 'Failed' ELSE 'Unclassified' END")


def _count(value) -> int:
    try:
        return 0 if value is None or pd.isna(value) else max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _pct(part, whole):
    return None if not whole else 100.0 * part / whole


def outcome_summary(successful, failed, unclassified=0) -> dict:
    """Canonical counts and percentages. A percentage is None (unavailable) when its denominator is 0."""
    s, f, u = _count(successful), _count(failed), _count(unclassified)
    classified, events = s + f, s + f + u
    return {'success': s, 'failed': f, 'unclassified': u, 'classified': classified, 'events': events,
            'success_pct': _pct(s, classified), 'failure_pct': _pct(f, classified),
            'unclassified_pct': _pct(u, events)}


def health_outcomes(health) -> dict:
    """Canonical outcome summary from the daily health frame (event-weighted, not a mean of daily rates)."""
    if health is None or not len(health):
        return outcome_summary(0, 0, 0)
    if {'successful_calls', 'failed_calls'}.issubset(health.columns):
        col = lambda name: pd.to_numeric(health.get(name, 0), errors='coerce').fillna(0).sum()
        return outcome_summary(col('successful_calls'), col('failed_calls'), col('unclassified_events'))
    # Frame carries no outcome counts: every event is unclassified rather than assumed successful.
    events = pd.to_numeric(health['requests'], errors='coerce').fillna(0).sum() if 'requests' in health else 0
    return outcome_summary(0, 0, events)


def fmt_pct(value, digits: int = 2) -> str:
    return 'N/A' if value is None or pd.isna(value) else f'{value:.{digits}f}%'


# ---- Use-case identity, stage and status --------------------------------------------------------
STATUS_ALLOWLIST = {'active': 'Active', 'operational': 'Active', 'dormant': 'Dormant',
                    'new': 'New', 'onboarding': 'Onboarding'}
STAGE_ALLOWLIST = {'sandbox': 'Sandbox', 'industrialized': 'Industrialized'}
STATUS_CATEGORIES = ('Active', 'Dormant', 'New', 'Onboarding', 'Unknown')
STAGE_CATEGORIES = ('Sandbox', 'Industrialized', 'Unknown')


def _normalize(value, allowlist) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return 'Unknown'
    return allowlist.get(' '.join(str(value).split()).casefold(), 'Unknown')


def normalize_status(value) -> str:
    """Exact, allow-listed match after trimming and case-folding; 'Inactive' is Unknown, never Active."""
    return _normalize(value, STATUS_ALLOWLIST)


def normalize_stage(value) -> str:
    return _normalize(value, STAGE_ALLOWLIST)


def _clean_ids(df) -> pd.Series:
    if 'id' not in df:
        return pd.Series(pd.NA, index=df.index, dtype='string')
    ids = df['id'].astype('string').str.strip()
    return ids.mask(ids == '')


def annotate_use_cases(df) -> pd.DataFrame:
    """Copy of `df` with blank ids as missing, `status_category` and `canonical_row` (first row per id)."""
    d = df.copy()
    ids = _clean_ids(d)
    d['id'] = ids
    d['canonical_row'] = ids.notna() & ~ids.duplicated()
    d['status_category'] = d['status'].map(normalize_status) if 'status' in d else 'Unknown'
    return d


def canonical_use_cases(df):
    """Return (canonical frame, reconciliation metadata).

    Identity is the application/use-case ID; the name is a display label only. Rows sharing an ID collapse
    to the first row. Rows with no ID are preserved in the metadata count but are not distinct use cases.
    """
    d = annotate_use_cases(df)
    canon = d[d['canonical_row']].drop(columns='canonical_row')
    stage = canon['use_case_stage'].map(normalize_stage) if 'use_case_stage' in canon else pd.Series('Unknown', index=canon.index)
    status = canon['status_category']
    missing = int(d['id'].isna().sum())
    meta = {'rows': len(d), 'canonical_use_cases': len(canon), 'missing_id_rows': missing,
            'duplicate_canonical_id_count': len(d) - missing - len(canon),
            'by_stage': {k: int((stage == k).sum()) for k in STAGE_CATEGORIES},
            'by_status': {k: int((status == k).sum()) for k in STATUS_CATEGORIES}}
    meta['unknown_status_count'] = meta['by_status']['Unknown']
    meta['unknown_stage_count'] = meta['by_stage']['Unknown']
    meta['reconciles'] = sum(meta['by_stage'].values()) == len(canon) == sum(meta['by_status'].values())
    return canon, meta


# ---- Active-user terminology --------------------------------------------------------------------
ACTIVE_USERS = {
    'synthetic estimate': ('Estimated active users', 'active_users_estimated',
                           'Synthetic estimate derived from expected users; not observed identities or measured platform activity.'),
    'reported': ('Reported active users', 'active_users_reported',
                 'The source supplies the value, but the application has not independently verified its measurement period, identity definition, or deduplication rule.'),
    'observed': ('Observed active users', 'active_users_observed',
                 'Measured from an activity source with a defined timestamp, user or client identity, reporting period and deduplication rule.'),
    'not supplied': ('Reported active users', 'active_users_reported',
                     'The source does not supply an Active Users field, so no value is available.'),
}


def active_users_presentation(basis) -> tuple:
    """(label, KPI_INFO key, explanation). Unknown bases fall back to the cautious 'reported' wording."""
    return ACTIVE_USERS.get(basis, ACTIVE_USERS['reported'])


# ---- Source-mode vocabulary ---------------------------------------------------------------------
SOURCE_MODES = ('workbook', 'parquet', 'synthetic fallback', 'synthetic scenario', 'derived from workbook',
                'derived from parquet', 'locally registered', 'unclassified telemetry present')
SOURCE_BADGE_NOTE = ('The badge shows where the data came from. It does not indicate freshness, data correctness, '
                     'confidentiality approval, production status, a live integration or source certification.')


def derived_from(mode) -> str:
    m = str(mode).casefold()
    if m.startswith('workbook'):
        return 'derived from workbook'
    if m.startswith('parquet'):
        return 'derived from parquet'
    return 'derived from synthetic fallback'
