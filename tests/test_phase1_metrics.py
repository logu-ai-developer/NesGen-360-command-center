"""V1.1 Phase 1: metric correctness and honest labelling. Offline; Parquet/workbook fixtures are synthetic."""
import inspect
import json
import math
import re
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import agent, assistant_insights as ai, components, data, insights, query_tools as qt, storage
from src import metrics
from src.insights import KPI_INFO, build_decision_brief

APP = str(Path(__file__).resolve().parents[1] / 'app.py')
S, F = metrics.SUCCESS_TRACEPOINT, metrics.FAILURE_TRACEPOINT


def run(**kwargs):
    return json.loads(qt.query_dashboard(json.dumps(kwargs)))


def write_telemetry(rows):
    """rows: (tracepoint, severity, day). Writes a NewRelic-shaped Parquet file under the (patched) data root."""
    folder = data.DATA / 'NewRelic'
    folder.mkdir(parents=True, exist_ok=True)
    n = len(rows)
    pd.DataFrame({
        'Timestamp_1': [r[2] for r in rows], 'SeverityText': [r[1] for r in rows], 'Body.Tracepoint': [r[0] for r in rows],
        'Attributes.BusinessKeys.model': ['m1'] * n, 'Attributes.BusinessKeys.provider': ['Azure'] * n,
        'Attributes.BusinessKeys.client_id': [f'c{i}' for i in range(n)], 'Attributes.BusinessKeys.responseTime': [100.0 + i for i in range(n)],
        'Attributes.BusinessKeys.total_cost': [1.0] * n, 'Error.errorCode': ['500'] * n,
        'Error.errorMessage.errorMessage': ['boom'] * n, 'Error.errorMessage.errorSource': ['gw'] * n,
    }).to_parquet(folder / 'part.parquet')
    data._telemetry.cache_clear()


MIXED = [(S, 'INFO', '2026-10-01')] * 3 + [(F, 'ERROR', '2026-10-01')] + [(None, None, '2026-10-01')] * 2 \
        + [(None, 'INFO', '2026-10-02')] * 2   # day 2: INFO severity but no marker -> must NOT count as success


# ---- Telemetry classification -------------------------------------------------------------------
@pytest.mark.parametrize('value,expected', [(S, 'Successful'), (F, 'Failed'), (None, 'Unclassified'), ('', 'Unclassified'),
                                            ('flow-end', 'Unclassified'), (float('nan'), 'Unclassified'), ('OTHER', 'Unclassified')])
def test_classify_outcome_exactly_one_class(value, expected):
    assert metrics.classify_outcome(value) == expected


@pytest.mark.parametrize('s,f,u', [(3, 1, 2), (0, 0, 0), (0, 0, 5), (4, 0, 0), (0, 4, 0), (1, 0, 0), (0, 1, 3)])
def test_outcome_summary_reconciles_and_never_nan(s, f, u):
    o = metrics.outcome_summary(s, f, u)
    assert o['events'] == s + f + u == o['classified'] + o['unclassified']
    assert o['classified'] == s + f
    for key in ('success_pct', 'failure_pct', 'unclassified_pct'):
        assert o[key] is None or (math.isfinite(o[key]) and 0 <= o[key] <= 100)
    if o['classified']:
        assert o['success_pct'] + o['failure_pct'] == pytest.approx(100)
    else:
        assert o['success_pct'] is None and o['failure_pct'] is None
    assert (o['unclassified_pct'] is None) == (o['events'] == 0)


def test_outcome_summary_formulas_and_denominators():
    o = metrics.outcome_summary(3, 1, 4)
    assert o['success_pct'] == 75.0 and o['failure_pct'] == 25.0      # denominator: classified (4)
    assert o['unclassified_pct'] == 50.0                               # denominator: total events (8)


def test_zero_classified_is_unavailable_not_zero_percent():
    o = metrics.outcome_summary(0, 0, 7)
    assert metrics.fmt_pct(o['success_pct']) == 'N/A' and metrics.fmt_pct(float('nan')) == 'N/A'
    assert metrics.fmt_pct(75.0) == '75.00%'


def test_fmt_count_millions_abbreviation():
    # Readable millions (Western) notation on dashboard KPI cards: B / M / K, one decimal, trailing zeros stripped.
    assert metrics.fmt_count(2_000_000) == '2M'
    assert metrics.fmt_count(45_400_000) == '45.4M'
    assert metrics.fmt_count(10_000_000) == '10M'
    assert metrics.fmt_count(931_000) == '931K'
    assert metrics.fmt_count(99_691) == '99.7K'           # thousands are abbreviated
    assert metrics.fmt_count(1_200_000_000) == '1.2B'     # billions
    assert metrics.fmt_count(9_961) == '10K'              # rounds to one decimal
    assert metrics.fmt_count(500) == '500'                # below 1,000: grouped digits
    assert metrics.fmt_count(7) == '7' and metrics.fmt_count(0) == '0'
    assert metrics.fmt_count(None) == 'N/A' and metrics.fmt_count(float('nan')) == 'N/A'


def test_health_outcomes_without_counts_is_all_unclassified():
    o = metrics.health_outcomes(pd.DataFrame({'requests': [10, 5], 'success_rate': [99.0, 99.0]}))
    assert (o['success'], o['failed'], o['unclassified']) == (0, 0, 15) and o['success_pct'] is None
    assert metrics.health_outcomes(None)['events'] == 0 and metrics.health_outcomes(pd.DataFrame())['events'] == 0


def test_cards_trend_query_and_telemetry_share_one_classification():
    write_telemetry(MIXED)
    stats = data.get_telemetry()['stats']
    daily = data.get_health()
    o = metrics.health_outcomes(daily)
    assert (stats['success'], stats['failed'], stats['unclassified']) == (3, 1, 4)
    assert (o['success'], o['failed'], o['unclassified']) == (3, 1, 4)           # trend == cards
    assert o['success_pct'] == stats['success_pct'] == 75.0
    assert daily.requests.sum() == stats['events'] == 8
    day2 = daily[daily.date == pd.Timestamp('2026-10-02')].iloc[0]
    assert pd.isna(day2.success_rate) and day2.unclassified_events == 2           # INFO severity is not success
    q = run(dataset='new_relic', metrics=['successful_classified_calls', 'failed_classified_calls', 'unclassified_events', 'classified_call_success_rate'])
    assert q['status'] == 'ok' and q['rows'][0] == {'successful_classified_calls': 3, 'failed_classified_calls': 1, 'unclassified_events': 4, 'classified_call_success_rate': 75.0}
    h = run(dataset='health_daily', metrics=['classified_call_success_rate', 'unclassified_events'])
    assert h['rows'][0] == {'classified_call_success_rate': 75.0, 'unclassified_events': 4}
    by_outcome = run(dataset='new_relic', dimensions=['outcome'], metrics=['events'])
    assert {r['outcome']: r['events'] for r in by_outcome['rows']} == {'Successful': 3, 'Failed': 1, 'Unclassified': 4}


def test_by_model_reconciles_to_classified_calls():
    write_telemetry(MIXED)
    t = data.get_telemetry()
    assert t['by_model'].calls.sum() == t['stats']['classified'] == 4 and t['by_model'].failures.sum() == 1


def test_only_unclassified_telemetry_has_no_rate_or_finding():
    write_telemetry([(None, None, '2026-10-01')] * 3 + [(None, 'INFO', '2026-10-01')] * 2)
    stats = data.get_telemetry()['stats']
    assert stats['success_pct'] is None and stats['failure_pct'] is None and stats['unclassified'] == 5
    assert build_decision_brief(None, None, data.get_health(), None, None) == []
    assert run(dataset='new_relic', metrics=['classified_call_success_rate'])['rows'][0]['classified_call_success_rate'] is None


def test_no_failed_and_no_successful_records():
    write_telemetry([(S, 'INFO', '2026-10-01')] * 2)
    s = data.get_telemetry()['stats']
    assert s['success_pct'] == 100.0 and s['failure_pct'] == 0.0
    write_telemetry([(F, 'ERROR', '2026-10-01')] * 2)
    s = data.get_telemetry()['stats']
    assert s['success_pct'] == 0.0 and s['failure_pct'] == 100.0 and s['classified'] == 2


def test_parquet_without_tracepoint_column_is_all_unclassified():
    folder = data.DATA / 'NewRelic'
    folder.mkdir(parents=True)
    pd.DataFrame({'Timestamp_1': ['2026-10-01'] * 3, 'SeverityText': ['INFO'] * 3, 'Attributes.BusinessKeys.responseTime': [1.0] * 3,
                  'Attributes.BusinessKeys.total_cost': [1.0] * 3}).to_parquet(folder / 'p.parquet')
    d = data.get_health()
    assert d.attrs['source_mode'] == 'parquet'
    o = metrics.health_outcomes(d)
    assert (o['success'], o['failed'], o['unclassified']) == (0, 0, 3) and o['success_pct'] is None


def test_executive_rule_uses_event_weighted_classified_rate_and_discloses_unclassified():
    health = pd.DataFrame({'success_rate': [90.0, 90.9], 'successful_calls': [90, 900], 'failed_calls': [10, 90], 'unclassified_events': [50, 0], 'requests': [150, 990]})
    items = build_decision_brief(None, None, health, None, None)
    assert len(items) == 1 and items[0]['title'] == 'Call success rate below target'
    ev = items[0]['evidence']
    assert 'Call success rate 90.83%' in ev and '50 of 1,140 events uncategorized' in ev   # 990 / (990 + 100); not the 90.45% mean of daily rates
    assert 'Not verified availability' in ev and 'Average availability' not in ev


def test_no_events_gives_no_reliability_finding():
    empty = pd.DataFrame({'success_rate': [], 'successful_calls': [], 'failed_calls': [], 'unclassified_events': [], 'requests': []})
    assert build_decision_brief(None, None, empty, None, None) == []


def test_platform_report_evidence_is_strict_json_and_labelled(monkeypatch):
    today = ai.today_utc()
    frame = pd.DataFrame({'date': [today - pd.Timedelta(days=1), today], 'requests': [10, 10], 'successful_calls': [0, 0],
                          'failed_calls': [0, 0], 'unclassified_events': [10, 10], 'success_rate': [float('nan')] * 2,
                          'p95_latency_ms': [float('nan')] * 2})
    monkeypatch.setattr(ai, 'get_health', lambda: frame)
    x = ai.get_platform_report(days=7)
    m = x['metrics']
    assert m['classified_call_success_rate_percent'] is None and m['unclassified_telemetry_present'] and m['rate_unavailable_reason'] == metrics.NO_CLASSIFIED_NOTE
    assert m['events_in_scope'] == 20 and m['unweighted_average_daily_classified_success_percent'] is None
    json.dumps(x, allow_nan=False)                                          # no NaN / Infinity reaches the model
    assert 'not verified end-to-end availability' in x['metric_note'].casefold()
    assert 'unweighted_average_daily_non_error_percent' not in m


def test_decision_brief_tool_carries_corrected_reliability_finding():
    x = ai.get_decision_brief()
    titles = [f['title'] for f in x['findings']]
    assert 'Call success rate below target' in titles and x['source_mode'] == 'synthetic scenario'
    assert 'Platform reliability below target' not in titles


def test_non_error_event_rate_is_distinct_and_excludes_missing_severity():
    desc = qt.get_metric_definition('new_relic', 'non_error_event_percent')
    assert 'Non-error event rate' in desc and 'not the classified-call success rate' in desc


def test_policy_blocks_unclassified_as_success_and_service_health():
    p = agent.POLICY
    assert 'Never count Unclassified events as successful' in p and 'no service-health inventory' in p


# ---- Adoption terminology, status and identity --------------------------------------------------
@pytest.mark.parametrize('raw,expected', [('Active', 'Active'), (' active ', 'Active'), ('ACTIVE', 'Active'), ('Operational', 'Active'),
                                          ('Inactive', 'Unknown'), ('Not Active', 'Unknown'), ('Newly onboarded', 'Unknown'),
                                          ('Dormant', 'Dormant'), ('New', 'New'), ('Onboarding', 'Onboarding'),
                                          ('Retired', 'Unknown'), (None, 'Unknown'), (float('nan'), 'Unknown'), (pd.NA, 'Unknown')])
def test_status_is_exact_allowlisted_and_unknown_preserved(raw, expected):
    assert metrics.normalize_status(raw) == expected


def apps_frame():
    return pd.DataFrame({
        'id': ['A', 'B', 'C', 'C', 'D', None, '  ', 'E'], 'name': ['Same Name'] * 8,
        'region': ['Europe', 'Europe', 'Asia', 'AMEA', 'Asia', 'Europe', 'Asia', 'Europe'],
        'status': ['Active', 'Inactive', 'Dormant', 'Active', 'New', 'Onboarding', 'Active', 'Retired'],
        'use_case_stage': ['Sandbox', 'Industrialized', 'Sandbox', 'Industrialized', 'Industrialized', 'Sandbox', 'Sandbox', 'Industrialized'],
        'segment': ['B2B', 'B2C', 'B2B', 'B2C', 'B2B', 'B2C', 'B2B', 'B2C'], 'environment': ['Production'] * 8, 'platform': ['x'] * 8,
        'recertification_status': ['Pending'] * 8, 'expected_daily_users': [10] * 8, 'business_value': [1] * 8, 'active_users': [5] * 8,
        'created_date': pd.to_datetime(['2026-10-01'] * 8), 'monthly_requests': [1] * 8, 'provider': ['Azure'] * 8,
        'Azure': [1.] * 8, 'AWS': [0.] * 8, 'GCP': [0.] * 8})


def test_canonical_identity_names_never_merge_and_duplicates_collapse():
    canon, meta = metrics.canonical_use_cases(apps_frame())
    assert meta['rows'] == 8 and meta['canonical_use_cases'] == 5 == len(canon)           # A B C D E; 8 identical names do not merge
    assert meta['duplicate_canonical_id_count'] == 1 and meta['missing_id_rows'] == 2     # second C; None and blank
    assert canon.set_index('id').loc['C', 'region'] == 'Asia'                             # first row wins
    assert meta['by_status'] == {'Active': 1, 'Dormant': 1, 'New': 1, 'Onboarding': 0, 'Unknown': 2}   # Inactive, Retired preserved as Unknown
    assert meta['by_stage'] == {'Sandbox': 2, 'Industrialized': 3, 'Unknown': 0}
    assert meta['reconciles'] and meta['unknown_status_count'] == 2


def test_missing_id_column_is_disclosed_not_invented():
    canon, meta = metrics.canonical_use_cases(pd.DataFrame({'name': ['a', 'b'], 'status': ['Active', 'Active']}))
    assert len(canon) == 0 and meta['missing_id_rows'] == 2 and meta['rows'] == 2


def test_query_tool_counts_use_canonical_ids(monkeypatch):
    monkeypatch.setattr(qt.dashboard, 'get_apps', lambda: apps_frame())
    names = ['canonical_use_cases', 'active_status_use_cases', 'dormant_status_use_cases', 'new_status_use_cases',
             'onboarding_status_use_cases', 'unknown_status_use_cases', 'sandbox_use_cases', 'industrialized_use_cases', 'missing_id_rows']
    r = run(dataset='applications', metrics=names[:6])['rows'][0]
    assert r == {'canonical_use_cases': 5, 'active_status_use_cases': 1, 'dormant_status_use_cases': 1, 'new_status_use_cases': 1,
                 'onboarding_status_use_cases': 0, 'unknown_status_use_cases': 2}
    r = run(dataset='applications', metrics=names[6:])['rows'][0]
    assert r == {'sandbox_use_cases': 2, 'industrialized_use_cases': 3, 'missing_id_rows': 2}
    by_region = run(dataset='applications', dimensions=['region'], metrics=['canonical_use_cases'])
    assert sum(x['canonical_use_cases'] for x in by_region['rows']) == 5
    by_seg = run(dataset='applications', dimensions=['segment'], metrics=['canonical_use_cases'])
    assert sum(x['canonical_use_cases'] for x in by_seg['rows']) == 5
    assert run(dataset='applications', metrics=['application_rows'])['rows'][0]['application_rows'] == 8   # rows stay labelled as rows


def test_active_users_labels_follow_the_measurement_basis():
    assert metrics.active_users_presentation('synthetic estimate')[0] == 'Estimated active users'
    assert 'derived from expected users; not observed identities or measured platform activity' in metrics.active_users_presentation('synthetic estimate')[2]
    assert metrics.active_users_presentation('reported')[0] == 'Reported active users'
    assert metrics.active_users_presentation('observed')[0] == 'Observed active users'
    assert metrics.active_users_presentation(None)[0] == 'Reported active users'                       # never silently "Observed"
    assert data.synthetic_apps().attrs['active_users_basis'] == 'synthetic estimate'


def workbook(monkeypatch, tmp_path, frame):
    hub = tmp_path / 'hub.xlsx'
    hub.touch()
    monkeypatch.setattr(data, 'HUB_XLSX', hub)
    monkeypatch.setattr(pd, 'read_excel', lambda p, **kw: frame.copy())


def hub_frame(**extra):
    base = {'Application ID': ['A', 'B', None, 'B'], 'APM Name': ['Same'] * 4, 'Region': ['Europe'] * 4,
            'Environment': ['Production'] * 4, 'LATEST STATUS OF USE CASE': ['Active', 'Inactive', 'Active', 'Dormant'],
            'Models': ['Gemini'] * 4, 'Azure': [1] * 4, 'Expected Daily Users': [10] * 4, 'Business Value': [1] * 4,
            'Approval date': ['2026-10-01'] * 4}
    return pd.DataFrame({**base, **extra})


def test_workbook_active_users_are_reported_and_missing_ids_preserved(monkeypatch, tmp_path):
    workbook(monkeypatch, tmp_path, hub_frame(**{'Active Users': [3, 4, 5, 6]}))
    a = data.get_apps()
    assert a.attrs['source_mode'] == 'workbook' and a.attrs['active_users_basis'] == 'reported'
    assert len(a) == 4 and a['id'].isna().sum() == 1                                      # row without ID kept, not dropped
    canon, meta = metrics.canonical_use_cases(a)
    assert meta['canonical_use_cases'] == 2 and meta['missing_id_rows'] == 1 and meta['duplicate_canonical_id_count'] == 1


def test_workbook_without_active_users_field_is_not_supplied(monkeypatch, tmp_path):
    workbook(monkeypatch, tmp_path, hub_frame())
    assert data.get_apps().attrs['active_users_basis'] == 'not supplied'


# ---- Source modes -------------------------------------------------------------------------------
def test_source_mode_vocabulary_and_badges():
    assert set(metrics.SOURCE_MODES) == {'workbook', 'parquet', 'synthetic fallback', 'synthetic scenario', 'derived from workbook',
                                         'derived from parquet', 'locally registered', 'unclassified telemetry present'}
    assert metrics.derived_from('workbook') == 'derived from workbook' and metrics.derived_from('parquet') == 'derived from parquet'
    for mode in metrics.SOURCE_MODES:
        badge = components.source_badge(mode)
        assert mode in badge and 'background:#65758a' not in badge                          # every vocabulary term has a colour
        text = re.sub('<[^>]+>', '', badge).casefold()
        assert not any(w in text for w in ('fresh', 'certif', 'approved', 'verified', 'live', 'production', 'correct'))


def test_info_drawer_states_what_a_badge_does_not_mean():
    drawer = components._info_html(KPI_INFO['classified_success'], 'parquet')
    assert 'does not indicate freshness' in drawer and 'source certification' in drawer


def test_synthetic_fallback_modes_and_unclassified_warning_source():
    assert data.get_apps().attrs['source_mode'] == 'synthetic fallback'
    assert data.get_health().attrs['source_mode'] == 'synthetic fallback'
    assert data.get_telemetry()['mode'] == 'synthetic fallback'
    write_telemetry(MIXED)
    assert data.get_telemetry()['mode'] == 'parquet' and data.get_health().attrs['source_mode'] == 'parquet'


def test_locally_registered_models_are_marked():
    storage.register_model('Local one', 'Azure', 'Owner', 'Sandbox validation', 70, 'Low')
    m = data.get_models()
    assert (m.record_origin == 'locally registered').sum() == 1 and (m.record_origin == 'catalog').sum() == len(m) - 1
    assert 'locally registered' in m.attrs['source_detail']


def test_chargeback_is_a_synthetic_scenario():
    assert ai.get_chargeback_report()['source_mode'] == 'synthetic scenario'
    assert 'synthetic scenario' in qt.CATALOG['charges']['mode'] and 'synthetic scenario' in qt.CATALOG['alerts']['mode']


# ---- KPI catalog ---------------------------------------------------------------------------------
def test_kpi_lineage_points_at_real_catalog_metrics():
    for key, info in KPI_INFO.items():
        if info['dataset'] in qt.CATALOG:
            assert info['metric'] in qt.CATALOG[info['dataset']]['metrics'], key


def test_services_healthy_is_removed_from_the_catalog():
    assert 'services_healthy' not in KPI_INFO
    assert not any('41 / 43' in str(v) for v in KPI_INFO.values())


# ---- Rendered pages ------------------------------------------------------------------------------
def page(name):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state['nesgen_real_data'] = True   # metric-correctness tests validate the real-data rendering pipeline
    at.run()
    at.sidebar.radio[0].set_value(name).run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return at, '\n'.join(m.value for m in at.markdown) + '\n' + '\n'.join(str(c.value) for c in at.caption)


FORBIDDEN = ['Platform availability', 'Monthly active', 'New this month', 'No use in 30 days', 'Active platform users', 'Active New Usecase',
             'Monthly active apps', 'Available Model', '41 / 43', 'Services healthy', 'Illustrative · 2 need attention']


@pytest.fixture
def no_gemini(monkeypatch):
    """Rendering any page must not reach the Gemini client."""
    def boom(*a, **k):
        raise AssertionError('Gemini must not be called while rendering a page')
    monkeypatch.setattr(agent, 'ask', boom)
    from google import genai
    monkeypatch.setattr(genai, 'Client', boom)


@pytest.mark.parametrize('name', ['Executive overview', 'Platform health', 'User adoption', 'Model lifecycle', 'Chargeback'])
def test_pages_use_honest_labels_and_drawers(name, no_gemini):
    at, text = page(name)
    assert 'kpi-info' in text, 'KPI information drawers render'
    assert 'does not indicate freshness' in text
    for bad in FORBIDDEN:
        assert bad not in text, (name, bad)
    assert not re.search(r'\bnan\b|\binf\b', text, re.I)


def test_executive_labels(no_gemini):
    _, text = page('Executive overview')
    for label in ('Call success rate', 'Models in inventory', 'Active use cases', 'Priority actions'):
        assert label in text
    assert 'Governed models' not in text and 'synthetic scenario' in text


def test_user_adoption_labels_synthetic_fallback(no_gemini):
    _, text = page('User adoption')
    for label in ('Use cases in portfolio', 'Sandbox use cases', 'Industrialized use cases', 'Estimated active users', 'Active use cases',
                  'New-status use cases', 'Inactive use cases', 'Onboarding-status use cases'):
        assert label in text, label
    assert 'Synthetic estimate derived from expected users; not observed identities or measured platform activity.' in text
    assert 'Reported active users' not in text and 'Observed active users' not in text and 'synthetic fallback' in text


def test_user_adoption_labels_workbook_reported(monkeypatch, tmp_path, no_gemini):
    workbook(monkeypatch, tmp_path, hub_frame(**{'Active Users': [3, 4, 5, 6]}))
    monkeypatch.setattr(data, 'MODEL_XLSX', tmp_path / 'missing_models.xlsx')
    _, text = page('User adoption')
    assert 'Reported active users' in text and 'Estimated active users' not in text
    assert 'has not independently verified its measurement period' in text
    assert '1 rows without an ID not counted' in text


def test_user_adoption_without_active_users_field_shows_na(monkeypatch, tmp_path, no_gemini):
    workbook(monkeypatch, tmp_path, hub_frame())
    at, text = page('User adoption')
    assert 'Reported active users' in text and 'does not supply an Active Users field' in text


def test_platform_health_with_unclassified_telemetry(no_gemini):
    write_telemetry(MIXED)
    _, text = page('Platform health')
    for label in ('Total classified calls', 'Successful classified calls', 'Failed classified calls', 'Call success rate'):
        assert label in text, label
    assert 'unclassified telemetry present' in text and '75.00%' in text and '50.00% of events' in text
    for bad in ('Total API calls', 'Successful calls<', 'Failed calls<', 'Daily success rate'):
        assert bad not in text


def test_platform_health_with_only_unclassified_telemetry_shows_na(no_gemini):
    write_telemetry([(None, None, '2026-10-01')] * 3)
    _, text = page('Platform health')
    assert 'N/A' in text and metrics.NO_CLASSIFIED_NOTE in text
    assert '>0.00%<' not in text and '>100.00%<' not in text                      # no measured-looking rate


def test_executive_page_with_only_unclassified_telemetry(no_gemini):
    write_telemetry([(None, 'INFO', '2026-10-01')] * 3)
    _, text = page('Executive overview')
    assert 'N/A' in text and metrics.NO_CLASSIFIED_NOTE in text and 'Call success rate below target' not in text


def test_sidebar_css_does_not_pin_width_or_hide_collapse_controls():
    css = inspect.getsource(components.inject_css)
    sidebar_rules = re.findall(r'\[data-testid="stSidebar"\][^{]*\{[^}]*\}', css)
    assert not any(re.search(r'(^|[;{])\s*(min-|max-)?width\s*:', r.split('{', 1)[1]) for r in sidebar_rules)
    assert 'collapsedControl' not in css and 'stSidebarCollapse' not in css
    assert "initial_sidebar_state='expanded'" in Path(APP).read_text(encoding='utf-8')
