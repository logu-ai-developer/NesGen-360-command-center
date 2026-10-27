"""V1.1 Phase 3: executive experience and navigation. Presentation only; no metric, window or classification logic."""
import re
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import insights
from src.insights import (finding_target, model_review_priority, REVIEW_PRIORITY_LABELS, SEVERITY_ICONS, RISK_BADGES, FINDING_TARGETS, ATTENTION_LABELS, model_attention_rank)
from tests.test_phase1_metrics import APP, no_gemini  # noqa: F401


def text_of(at):
    return '\n'.join(m.value for m in at.markdown) + '\n' + '\n'.join(str(c.value) for c in at.caption)


def render(page=None):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state['nesgen_real_data'] = True   # exercise the real pipeline (synthetic fallback without parquet), as before the demo-only switch
    at.run()
    if page:
        at.sidebar.radio[0].set_value(page).run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return at, text_of(at)


WINDOW_LINE = r'Window: Last \d+ days · Source: \S.* · Last available: \d{4}-\d\d-\d\d'


# ---- Executive: priority findings and routing ------------------------------------------------------
def test_finding_routing_table_and_icons():
    assert FINDING_TARGETS == {'Reliability': 'Platform health', 'Operations': 'Platform health', 'Governance': 'Model lifecycle',
                               'Adoption': 'User adoption', 'Financial': 'Chargeback'}
    assert finding_target({'category': 'Governance'}) == 'Model lifecycle' and finding_target({'category': 'Other'}) == 'Executive overview'
    assert SEVERITY_ICONS['Critical'] == '🔴' and SEVERITY_ICONS['High'] == '🟠' and SEVERITY_ICONS['Medium'] == '🟡'


def test_executive_shows_only_existing_findings_as_navigation_cards(no_gemini):
    at, text = render('Executive overview')
    assert 'Priority findings' in text and 'Current focus' not in text
    labels = [b.label for b in at.button if b.key and b.key.startswith('go_')]
    assert labels and all(x.startswith('Open ') and x.endswith('→') for x in labels)
    assert 'Open Chargeback →' in labels and 'Open Platform health →' in labels
    assert '🔴' in text and '🟠' in text and 'No priority findings identified' not in text
    # Each priority finding carries a module eyebrow naming the page its evidence lives on; the alerts dataframe is gone.
    assert 'finding-module' in text and 'class="finding-module">Platform health<' in text
    assert 'Leadership action queue' not in text
    assert 'AI findings' not in text and 'Recommended actions' not in text          # the brief is shown once (Priority findings), not repeated below


def test_clicking_a_finding_opens_its_page_through_session_state(no_gemini):
    at, _ = render('Executive overview')
    next(b for b in at.button if b.label == 'Open Chargeback →').click().run()
    assert not at.exception and at.sidebar.radio[0].value == 'Chargeback'
    assert 'Provider reconciliation' in text_of(at)


def test_empty_state_when_no_findings(monkeypatch, no_gemini):
    monkeypatch.setattr(insights, 'build_decision_brief', lambda *a, **k: [])
    at, text = render('Executive overview')
    assert any(x.value == 'No priority findings identified.' and x.icon == '✅' for x in at.success)
    assert not [b for b in at.button if b.key and b.key.startswith('go_')]


def test_executive_metadata_is_compact_with_details_in_a_drawer(no_gemini):
    at, text = render('Executive overview')
    assert re.search(WINDOW_LINE, text)
    assert any('Data basis' in e.label for e in at.expander)
    assert 'Telemetry · Last 180 days' in text                                  # full lineage still available inside the drawer


# ---- Platform Health -------------------------------------------------------------------------------
def test_platform_health_sections_and_card_placement(no_gemini):
    _, text = render('Platform health')
    names = ('Volume', 'Outcomes', 'Performance', 'Failure analysis', 'Supporting evidence')
    marks = [text.index('group-title">' + x) for x in names] + [len(text)]
    assert marks == sorted(marks)
    sec = dict(zip(names, (text[marks[i]:marks[i + 1]] for i in range(5))))
    groups = {'Volume': ('Total events', 'Total classified calls'),
              'Outcomes': ('Successful classified calls', 'Failed classified calls', 'Call success rate'),
              'Performance': ('P95 response time', 'P95 latency (daily trend)', 'Peak daily P95')}
    for name, labels in groups.items():
        for label in labels:
            assert f'kpi-label">{label}<' in sec[name]
            assert sum(f'kpi-label">{label}<' in sec[o] for o in names) == 1          # each card appears once, in its own section
    assert 'P95' not in sec['Outcomes'].replace('Daily classified', '') and 'latency' not in sec['Outcomes'].lower()
    for title in ('Most frequent errors', 'Failed classified calls by model', 'Failed classified calls by provider'):
        assert title in sec['Failure analysis']
    assert 'P95 latency (true)' not in text and 'True P95' not in text and 'Supporting telemetry metrics' not in text


def test_platform_health_scope_and_scenario_labels(no_gemini):
    at, text = render('Platform health')
    assert 'not affected by the Environment filter' in text and 'fixed snapshot' in text
    assert any('Illustrative synthetic scenario' in e.label for e in at.expander)
    # On demo telemetry errors ARE linked to a provider and model, so the error views follow the focus provider (the
    # real-telemetry window-wide limitation is disclosed only when the breakdown is absent).
    assert 'errors are linked to a provider and model' in text and 'follow the focus provider' in text
    assert any(s.key == 'ph_provider_focus' for s in at.selectbox)


def test_platform_health_keeps_evidence_tables_in_an_expander(no_gemini):
    at, text = render('Platform health')
    assert any(e.label == 'View supporting evidence' for e in at.expander)
    assert not any('Evidence tables' in e.label for e in at.expander)
    assert re.search(WINDOW_LINE, text)


# ---- Model Lifecycle -------------------------------------------------------------------------------
def test_review_priority_order():
    m = pd.DataFrame({'risk': ['Low', 'High', 'High', 'Low', 'Low', 'High'],
                      'next_review_date': pd.to_datetime(['2030-01-01', '2026-01-01', '2030-01-01', '2030-01-01', '2030-01-01', '2026-01-01']),
                      'lifecycle_status': ['Current', 'Current', 'Current', 'Review due', 'Current', 'Review due'],
                      'migration_required': ['No', 'No', 'No', 'No', 'Yes', 'No']})
    assert list(model_review_priority(m, '2026-10-22')) == [5, 1, 2, 3, 4, 1]
    assert REVIEW_PRIORITY_LABELS[1] == 'High risk + overdue review' and REVIEW_PRIORITY_LABELS[5] == ''


def test_lifecycle_labels_sorting_and_risk_badges(no_gemini):
    at, text = render('Model lifecycle')
    assert 'Models in inventory' in text and 'Model inventory and decisions' in text
    assert 'Governed models' not in text and 'Governance portfolio' not in text
    table = next(df.value for df in at.dataframe if 'attention' in df.value.columns)
    ranks = [next((k for k, v in ATTENTION_LABELS.items() if v == a), 4) for a in table['attention'].fillna('')]
    assert ranks == sorted(ranks)                                                # high risk, overdue review, retirement candidate, rest
    assert {'risk', 'review_status', 'retirement_status'} <= set(table.columns)  # separate concepts, separate columns
    assert 'Model Inventory &amp; Decisions' in text and 'Recommended replacement' not in text
    assert set(table['risk']) <= set(RISK_BADGES.values())                       # badges, not coloured rows
    assert re.search(r'finding" style="border-left-color:#(df4b55|f2a93b|39b98a)"', text)   # decision record: left-border indicator


# ---- User Adoption ---------------------------------------------------------------------------------
def test_adoption_cards_are_grouped_in_order(no_gemini):
    _, text = render('User adoption')
    groups = [text.index(f'group-title">{g}') for g in ('Portfolio', 'Status', 'Usage')]
    assert groups == sorted(groups)
    portfolio, status, usage = text[groups[0]:groups[1]], text[groups[1]:groups[2]], text[groups[2]:]
    for label in ('Use cases in portfolio', 'Sandbox use cases', 'Industrialized use cases'):
        assert f'kpi-label">{label}<' in portfolio
    for label in ('Active use cases', 'New-status use cases', 'Inactive use cases', 'Onboarding-status use cases'):
        assert f'kpi-label">{label}<' in status
    assert 'kpi-label">Estimated active users<' in usage


def test_segment_chart_uses_fixed_segment_colours_not_stage_colours():
    src = Path(APP).read_text(encoding='utf-8')
    assert "color='segment'" in src and "color_discrete_map={'B2B':'#1768ff','B2C':'#f2a93b'}" in src and "color='stage'" not in src


# ---- Navigation consistency ------------------------------------------------------------------------
@pytest.mark.parametrize('page', ['Executive overview', 'Platform health', 'User adoption', 'Model lifecycle'])
def test_every_major_page_has_a_compact_window_source_date_line(page, no_gemini):
    _, text = render(page)
    assert re.search(WINDOW_LINE, text), page


def test_chargeback_states_it_is_an_unwindowed_scenario(no_gemini):
    _, text = render('Chargeback')
    assert 'Window: none (snapshot) · Source: synthetic scenario' in text


def test_approved_assistants_are_present_and_bounded():
    src = Path(APP).read_text(encoding='utf-8')
    # Phase 4B: Model Evaluation Assistant. Phase 5B V1: Error Analysis Assistant (tests/test_error_assistant.py).
    assert 'Model Evaluation Assistant' in src and 'Error Analysis Assistant' in src
    # Both run AI only on an explicit click, never automatically on render.
    assert "st.button('Analyze Model'" in src and "st.button('Analyze Failures'" in src


def test_outcomes_chart_is_a_daily_outcomes_trend(no_gemini):
    at, text = render('Platform health')
    assert 'Daily Classified Call Outcomes' in text and 'Selected time window and environment' in text
    assert 'Daily classified-call success rate (%)' not in text
    fig = next(c for c in at.get('plotly_chart') if 'Total Calls' in c.proto.spec).proto.spec
    import json
    names = [t['name'] for t in json.loads(fig)['data']]
    assert names == ['Total Calls', 'Successful Classified Calls', 'Failed Classified Calls']
    assert 'kpi-label">Call success rate<' in text


def test_adoption_charts_are_not_colour_only(no_gemini):
    # UA-16 (Phase 6A WS-3): adoption charts stay legible without relying on colour alone.
    import json
    at, _ = render('User adoption')
    specs = [c.proto.spec for c in at.get('plotly_chart')]
    seg = json.loads(next(s for s in specs if '"B2B"' in s and '"B2C"' in s))['data']     # segment chart (by its series names)
    assert any(t.get('marker', {}).get('pattern', {}).get('shape') for t in seg)          # B2B/B2C differ by texture too
    assert all(t.get('text') is not None for t in seg)                                    # value labels on bars
    reg = json.loads(next(s for s in specs if 'In portfolio' in s))['data']               # regional chart
    assert all(t.get('text') is not None for t in reg)                                    # value labels on both series
