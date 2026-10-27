"""V1.1 Phase 2: time-intelligence foundation. Offline; all data synthetic or generated fixtures."""
import re
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import data, metrics
from src.insights import build_decision_brief
from src.timewindow import (WINDOW_DAYS, DEFAULT_WINDOW, resolve_window, previous_window, anchor_date, filter_by_window, count_in_window,
                            describe_basis, period_counts, rolling_counts, period_total, period_average, trend_direction,
                            lifecycle_date_counts, lifecycle_anchor)
from tests.test_phase1_metrics import APP, S, F, hub_frame, no_gemini, workbook, write_telemetry  # noqa: F401  (fixture reuse)

END = data.SYNTH_END


# ---- Time windows ---------------------------------------------------------------------------------
def test_window_definitions_are_fixed_day_counts():
    assert WINDOW_DAYS == {'1 Month': 30, '3 Months': 90, '6 Months': 180} and DEFAULT_WINDOW in WINDOW_DAYS


@pytest.mark.parametrize('key,days', [('1 Month', 30), ('3 Months', 90), ('6 Months', 180)])
def test_window_boundaries_are_inclusive(key, days):
    w = resolve_window(key, '2026-10-17')
    assert (w.window_days, w.window_label) == (days, f'Last {days} days')
    assert w.window_end == pd.Timestamp('2026-10-17') and w.window_start == w.window_end - pd.Timedelta(days=days - 1)
    assert (w.window_end - w.window_start).days + 1 == days
    inside = [w.window_start, w.window_end, w.window_start + pd.Timedelta(hours=23), w.window_end + pd.Timedelta(hours=23, minutes=59)]
    outside = [w.window_start - pd.Timedelta(seconds=1), w.window_end + pd.Timedelta(days=1)]
    assert w.mask(pd.Series(inside)).all() and not w.mask(pd.Series(outside)).any()
    assert set(w.as_dict()) == {'window', 'window_start', 'window_end', 'window_days', 'window_label'}


def test_future_missing_and_unparseable_dates_are_excluded():
    w = resolve_window('1 Month', '2026-10-17')
    assert list(w.mask(pd.Series(['2026-10-18', None, 'not a date', '2026-10-17']))) == [False, False, False, True]
    df = pd.DataFrame({'d': pd.to_datetime(['2026-10-17', '2026-12-01', None])})
    assert count_in_window(df, 'd', w) == 1 and count_in_window(df, 'missing', w) == 0


def test_windows_nest_and_previous_window_is_adjacent():
    w30, w90, w180 = (resolve_window(k, '2026-10-17') for k in WINDOW_DAYS)
    assert w30.window_start > w90.window_start > w180.window_start
    p = previous_window(w30)
    assert p.window_end == w30.window_start - pd.Timedelta(days=1) and p.window_days == 30 and p.window_label == 'Previous 30 days'
    assert not (p.mask(pd.Series([w30.window_start])).any() or w30.mask(pd.Series([p.window_end])).any())


def test_timezone_aware_anchor_and_invalid_key():
    assert resolve_window('1 Month', pd.Timestamp('2026-10-17 23:00', tz='US/Pacific')).window_end == pd.Timestamp('2026-10-18')
    with pytest.raises(ValueError):
        resolve_window('2 Months')


def test_anchor_is_latest_non_future_date():
    s = pd.Series(pd.to_datetime(['2026-07-01', '2026-07-07', '2030-01-01', None]))
    assert anchor_date(s, today='2026-10-22') == pd.Timestamp('2026-07-07')
    assert anchor_date(pd.Series([], dtype='datetime64[ns]'), today='2026-10-22') == pd.Timestamp('2026-10-22')
    assert anchor_date(s, pd.Series(pd.to_datetime(['2026-09-01'])), today='2026-10-22') == pd.Timestamp('2026-09-01')


def test_basis_line_exposes_window_date_field_and_source():
    text = describe_basis(resolve_window('3 Months', '2026-10-17'), 'event timestamp', 'parquet')
    assert 'Last 90 days' in text and '2026-07-20 to 2026-10-17' in text and 'event timestamp' in text and 'parquet' in text


# ---- Trend helpers --------------------------------------------------------------------------------
def test_period_counts_zero_filled_and_complete():
    w = resolve_window('1 Month', '2026-10-30')
    dates = pd.Series(pd.to_datetime(['2026-10-01', '2026-10-01', '2026-10-08', '2026-10-30', '2026-09-01', '2026-11-05', None]))
    pc = period_counts(dates, w)
    assert len(pc) == 5 and pc['count'].sum() == 4 and list(pc['count']) == [2, 1, 0, 0, 1]
    assert pc.period_start.iloc[0] == w.window_start


def test_rolling_totals_and_averages():
    assert list(rolling_counts([1, 2, 3, 4], 2)) == [1, 3, 5, 7]
    df = pd.DataFrame({'d': pd.to_datetime(['2026-10-10', '2026-10-11', '2026-01-01']), 'v': [10, 20, 99]})
    w = resolve_window('1 Month', '2026-10-17')
    assert period_total(df, 'v', 'd', w) == 30 and period_average(df, 'v', 'd', w) == 15
    assert period_average(df, 'v', 'd', resolve_window('1 Month', '2025-01-01')) is None


@pytest.mark.parametrize('cur,prev,kw,expected', [(110, 100, {}, 'increasing'), (90, 100, {}, 'decreasing'), (102, 100, {}, 'stable'),
                                                  (5, 0, {}, 'increasing'), (0, 0, {}, 'stable'), (None, 1, {}, None), (1, float('nan'), {}, None),
                                                  (97.8, 98.0, {'abs_tol': .5}, 'stable'), (96.0, 98.0, {'abs_tol': .5}, 'decreasing')])
def test_trend_direction(cur, prev, kw, expected):
    assert trend_direction(cur, prev, **kw) == expected


# ---- Synthetic datasets ---------------------------------------------------------------------------
def test_synthetic_generation_is_deterministic():
    pd.testing.assert_frame_equal(data.synthetic_health(), data.synthetic_health())
    pd.testing.assert_frame_equal(data.synthetic_apps(), data.synthetic_apps())
    pd.testing.assert_frame_equal(data.synthetic_models(), data.synthetic_models())


def test_synthetic_health_covers_180_days_with_scenarios():
    h = data.synthetic_health()
    assert len(h) == 180 and h.date.min() == END - pd.Timedelta(days=179) and h.date.max() == END
    assert (int(h.requests.sum()), int(h.failed_calls.sum()), int(h.unclassified_events.sum())) == (33243945, 725422, 394500)
    off = (END - h.date).dt.days
    base = h[(off < 70) & (off > 40) & (h.unclassified_events == 0)].success_rate.mean()
    degraded = h[(off >= 100) & (off <= 125)].success_rate.mean()
    assert degraded < base - 3                                                    # degraded period
    assert h[(off >= 70) & (off <= 84)].success_rate.mean() > h[(off >= 85) & (off <= 99)].success_rate.mean()      # recovery
    assert h.loc[off == 4, 'success_rate'].iloc[0] < 92 and (h.success_rate[off.isin([150, 151])] < 92).all()   # error spikes
    assert h[off.isin([140, 141, 142])].p95_latency_ms.min() > h.p95_latency_ms.median() * 1.5                  # latency spike
    spikes = h[h.unclassified_events > 0]
    assert len(spikes) == 8 and set((END - spikes.date).dt.days) == {30, 31, 32, 160, 161, 162, 163, 164}      # unclassified spikes
    assert ((h.successful_calls + h.failed_calls + h.unclassified_events) == h.requests).all()


def test_synthetic_approvals_cover_window_with_spikes_gap_and_older_rows():
    a = data.synthetic_apps()
    off = (END - a.created_date).dt.days
    assert len(a) == 100 and off.min() >= 0 and a.created_date.max() <= END                 # no future approvals
    assert (off >= 181).sum() == 15                                                          # older dated approvals (20 older, UNDATED_K=5 now undated)
    assert a.created_date.isna().sum() == data.UNDATED_K == 5                                 # WS-4/UA-09: fixed undated rows, all from the out-of-window older bucket
    assert ((off >= 40) & (off <= 69)).sum() == 0                                            # zero-approval period
    assert ((off >= 100) & (off <= 106)).sum() >= 22 and ((off >= 12) & (off <= 16)).sum() >= 14   # spikes
    assert [count_in_window(a, 'created_date', resolve_window(k, END)) for k in WINDOW_DAYS] == [26, 31, 80]
    assert 'last_activity' not in ' '.join(a.columns).lower()                                 # approval dates are never converted to activity


def test_synthetic_lifecycle_dates_fall_in_the_window_and_are_stable():
    m = data.synthetic_models()
    for col in ('last_review_date', 'review_due_date', 'retirement_decision_date', 'migration_date'):
        d = m[col].dropna()
        assert len(d) and d.min() >= END - pd.Timedelta(days=179) and d.max() <= END, col
    assert lifecycle_anchor(m) == END
    counts = [lifecycle_date_counts(m, resolve_window(k, END)) for k in WINDOW_DAYS]
    assert counts[2] == {'Last review': 32, 'Review due': 3, 'Next review': 0, 'Retirement decision': 6, 'Retire date': 0, 'Migration': 6}
    for label in counts[2]:
        assert counts[0][label] <= counts[1][label] <= counts[2][label]


def test_lifecycle_review_and_retirement_filtering():
    m = data.synthetic_models()
    w = resolve_window('1 Month', END)
    review = filter_by_window(m, 'last_review_date', w)
    retired = filter_by_window(m, 'retirement_decision_date', w)
    assert review.last_review_date.between(w.window_start, w.window_end + pd.Timedelta(days=1)).all() and len(review) == 8
    assert len(retired) == 1 and retired.retirement_decision_date.notna().all()
    assert lifecycle_anchor(pd.DataFrame({'next_review_date': pd.to_datetime(['2026-01-01']), 'retire_date': pd.to_datetime(['2026-02-01'])}), today='2026-10-22') == pd.Timestamp('2026-10-22')


# ---- Executive metrics ----------------------------------------------------------------------------
def test_same_metric_changes_across_windows_without_leakage():
    h = data.synthetic_health()
    parts = {k: metrics.health_outcomes(filter_by_window(h, 'date', resolve_window(k, END))) for k in WINDOW_DAYS}
    assert [parts[k]['events'] for k in WINDOW_DAYS] == sorted(parts[k]['events'] for k in WINDOW_DAYS)
    assert len({round(parts[k]['success_pct'], 4) for k in WINDOW_DAYS}) == 3                 # different window, different result
    w30, w90 = resolve_window('1 Month', END), resolve_window('3 Months', END)
    older = filter_by_window(h, 'date', previous_window(w30))
    assert metrics.health_outcomes(older)['events'] + parts['1 Month']['events'] == metrics.health_outcomes(filter_by_window(h, 'date', resolve_window('6 Months', END)).tail(60))['events']
    assert filter_by_window(h, 'date', w90).date.min() >= w90.window_start and filter_by_window(h, 'date', w30).date.max() <= w30.window_end


def test_priority_findings_follow_the_window():
    h = data.synthetic_health()
    def titles(key):
        return [i['title'] for i in build_decision_brief(None, None, filter_by_window(h, 'date', resolve_window(key, END)), None, None)]
    assert 'Call success rate below target' in titles('6 Months')
    healthy = h[(END - h.date).dt.days.between(40, 69)]                                       # a clean stretch of the same dataset
    assert build_decision_brief(None, None, healthy, None, None) == []


def selectbox(at, key):
    # P3: the time-window control is now a per-page radio (key 'tw_<page>'), rendered in the page body.
    return next(s for s in at.radio if str(s.key).startswith('tw_'))


def render(page, window=None):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state['nesgen_real_data'] = True   # window tests validate the real-data rendering pipeline
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    if window:
        tw = [r for r in at.radio if str(r.key).startswith('tw_')]
        if tw:
            tw[0].set_value(window).run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return '\n'.join(m.value for m in at.markdown) + '\n' + '\n'.join(str(c.value) for c in at.caption)


def card(text, label):
    return re.search(r'kpi-label">' + re.escape(label) + r'</div><div class="kpi-value">([^<]*)<', text).group(1)


def test_time_window_control_defaults_to_six_months_and_lists_all_windows():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value('Platform health').run()
    box = selectbox(at, 'time_window')
    assert box.value == '6 Months' and list(box.options) == list(WINDOW_DAYS)


def test_each_page_has_its_own_independent_window():
    # P3: setting the window on one page must not change another page's window.
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value('Platform health').run()
    next(r for r in at.radio if str(r.key).startswith('tw_')).set_value('1 Month').run()
    at.sidebar.radio[0].set_value('Model lifecycle').run()
    assert next(r for r in at.radio if str(r.key).startswith('tw_')).value == '6 Months'   # lifecycle keeps its own default


def test_executive_page_responds_to_the_window(no_gemini):
    texts = {k: render('Executive overview', k) for k in WINDOW_DAYS}
    rates = [card(texts[k], 'Call success rate') for k in WINDOW_DAYS]
    assert len(set(rates)) == 3, rates
    for k, days in WINDOW_DAYS.items():
        assert f'Last {days} days' in texts[k] and 'event timestamp' in texts[k] and 'approval date' in texts[k]
    assert [card(texts[k], 'Newly approved use cases') for k in WINDOW_DAYS] == ['26', '31', '80']
    assert 'snapshots, not windowed' in texts['1 Month'] and 'Monthly active' not in texts['1 Month']


def test_demo_adoption_exposes_the_undated_use_case_path(no_gemini):
    # WS-4/UA-09: with the synthetic fallback the "Use cases without approval date" card is now non-zero and the
    # canonical total and approval-window counts are unchanged.
    for w in ('6 Months', '1 Month'):
        text = render('User adoption', w)
        assert card(text, 'Use cases without approval date') == '5'                           # non-zero, not windowed
    text6 = render('User adoption', '6 Months')
    assert card(text6, 'Use cases in portfolio') == '100' and card(text6, 'Newly approved use cases') == '80'


# ---- Platform Health ------------------------------------------------------------------------------
def write_span(days=120):
    """Daily events for `days` days ending 2026-10-17: 2 successes + 1 failure per day, plus undated unclassified rows."""
    end = pd.Timestamp('2026-10-17')
    rows = []
    for i in range(days):
        day = str((end - pd.Timedelta(days=i)).date())
        rows += [(S, 'INFO', day), (S, 'INFO', day), (F, 'ERROR', day)]
    rows += [(None, None, None)] * 5
    write_telemetry(rows)
    return end


@pytest.mark.parametrize('key,days', [('1 Month', 30), ('3 Months', 90), ('6 Months', 120)])
def test_every_telemetry_view_uses_the_same_window(key, days):
    end = write_span()
    w = resolve_window(key, end)
    t = data.get_telemetry(w)
    s = t['stats']
    daily = filter_by_window(data.get_health(), 'date', w)
    o = metrics.health_outcomes(daily)
    assert (s['success'], s['failed'], s['unclassified']) == (2 * days, days, 0) and s['undated_events'] == 5
    assert (o['success'], o['failed'], o['unclassified']) == (s['success'], s['failed'], s['unclassified'])    # trend == cards
    assert len(daily) == days and o['success_pct'] == s['success_pct']
    assert t['by_model'].calls.sum() == t['by_provider'].calls.sum() == s['classified']
    assert t['by_model'].failures.sum() == t['by_provider'].failures.sum() == s['failed'] == t['errors'].occurrences.sum()


def test_undated_events_are_outside_every_window_but_in_the_unwindowed_total():
    end = write_span(10)
    assert data.get_telemetry(resolve_window('1 Month', end))['stats']['events'] == 30
    full = data.get_telemetry()['stats']
    assert full['events'] == 35 and full['unclassified'] == 5


def test_empty_window_has_no_rate_and_no_nan():
    write_span(10)
    t = data.get_telemetry(resolve_window('1 Month', '2025-01-31'))
    s = t['stats']
    assert (s['events'], s['success_pct'], s['p95_ms']) == (0, None, None) and t['by_model'].empty and t['errors'].empty


def test_platform_health_page_shows_one_window(no_gemini):
    write_span()
    texts = {k: render('Platform health', k) for k in WINDOW_DAYS}
    assert [card(texts[k], 'Failed classified calls') for k in WINDOW_DAYS] == ['30', '90', '120']
    assert [card(texts[k], 'Successful classified calls') for k in WINDOW_DAYS] == ['60', '180', '240']
    assert [card(texts[k], 'Total classified calls') for k in WINDOW_DAYS] == ['90', '270', '360']
    for k, days in WINDOW_DAYS.items():
        assert f'Last {days} days' in texts[k] and 'every card, chart and table on this page uses this window' in texts[k]
    assert '5 events have no event timestamp' in texts['1 Month']
    assert card(texts['1 Month'], 'Call success rate') == '66.67%'


def test_platform_health_synthetic_fallback_responds_to_window(no_gemini):
    texts = {k: render('Platform health', k) for k in WINDOW_DAYS}
    assert len({card(texts[k], 'Failed classified calls') for k in WINDOW_DAYS}) == 3
    assert 'Failures by provider' in texts['1 Month'] or 'by provider' in texts['1 Month']


# ---- Adoption -------------------------------------------------------------------------------------
def test_adoption_trend_is_approval_based_and_not_activity(no_gemini):
    texts = {k: render('User adoption', k) for k in WINDOW_DAYS}
    assert [card(texts[k], 'Newly approved use cases') for k in WINDOW_DAYS] == ['26', '31', '80']   # invariant: current-window counts unchanged by WS-4
    assert [card(texts[k], 'Previous period approvals') for k in WINDOW_DAYS] == ['3', '49', '15']   # 180d previous period is the older bucket; UNDATED_K=5 of it became undated (expected WS-4 move)
    text = texts['3 Months']
    assert 'Approval-based trend' in text and 'date field: approval date' in text and 'Approval dates are not activity' in text
    assert 'Monthly active' not in text and 'No use in 30 days' not in text
    assert card(text, 'Active use cases') == card(texts['1 Month'], 'Active use cases')      # status snapshot unchanged by window


def test_adoption_with_missing_approval_dates(monkeypatch, tmp_path, no_gemini):
    workbook(monkeypatch, tmp_path, hub_frame().drop(columns=['Approval date']))
    text = render('User adoption', '1 Month')
    assert card(text, 'Newly approved use cases') == '0' and card(text, 'Use cases without approval date') == '2'


def test_adoption_workbook_counts_only_canonical_ids_inside_the_window(monkeypatch, tmp_path, no_gemini):
    frame = hub_frame()
    frame['Approval date'] = ['2026-10-01', '2026-10-01', '2026-10-01', '2026-01-01']       # row 4 repeats id B with an old date
    workbook(monkeypatch, tmp_path, frame)
    text = render('User adoption', '1 Month')
    assert card(text, 'Newly approved use cases') == '2'                                     # A and B (first row wins); id-less row not counted


# ---- Lifecycle and regression ---------------------------------------------------------------------
def test_lifecycle_page_discloses_window_and_date_basis(no_gemini):
    text = render('Model lifecycle', '3 Months')
    assert 'Last 90 days' in text and 'lifecycle dates (review, retirement, migration)' in text
    assert 'Last review 16' in text and 'Retirement decision 4' in text and 'inventory snapshot, not windowed' in text


@pytest.mark.parametrize('page', ['Executive overview', 'Model lifecycle', 'Platform health', 'User adoption', 'Chargeback'])
@pytest.mark.parametrize('window', list(WINDOW_DAYS))
def test_pages_render_under_every_window(page, window, no_gemini):
    text = render(page, window)
    assert not re.search(r'\bnan\b|\binf\b', text, re.I)


def test_phase1_definitions_are_unchanged():
    assert metrics.outcome_summary(3, 1, 4)['success_pct'] == 75.0 and metrics.normalize_status('Inactive') == 'Unknown'
    assert metrics.canonical_use_cases(data.synthetic_apps())[1]['canonical_use_cases'] == 100
