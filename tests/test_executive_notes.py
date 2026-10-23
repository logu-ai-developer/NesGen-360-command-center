"""Executive KPI note wording: action-oriented primary notes, methodology in the drawer. No metric values are asserted to change."""
import re
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import components
from src.insights import KPI_INFO
from tests.test_phase1_metrics import APP, S, F, no_gemini, write_telemetry  # noqa: F401
from tests.test_phase3_experience import text_of


def note_of(text, label):
    m = re.search(r'kpi-label">' + re.escape(label) + r'</div><div class="kpi-value">[^<]*</div><div class="kpi-note">(.*?)</div>', text, re.S)
    return m.group(1) if m else None


def executive(window=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value('Executive overview').run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return text_of(at)


def fixture(undated=5):
    rows = [(S, 'INFO', '2026-07-01')] * 95 + [(F, 'ERROR', '2026-07-01')] * 5 + [(None, None, None)] * undated
    write_telemetry(rows)


def test_below_target_note_is_a_single_action_oriented_line(no_gemini):
    fixture(5)
    note = note_of(executive(), 'Classified-call success rate')
    assert note == 'Below 98% target · 5 failed calls require investigation'


def test_values_in_the_note_are_calculated_not_hardcoded(no_gemini):
    fixture(1234)
    assert '1,234 undated events excluded' in note_of(executive(), 'Unclassified events')
    fixture(0)
    assert 'undated' not in note_of(executive(), 'Unclassified events')


def test_unclassified_card_also_lists_undated_events_and_is_amber(no_gemini):
    fixture(7)
    text = executive()
    assert '7 undated events excluded' in note_of(text, 'Unclassified events')
    assert re.search(r'kpi kpi-warn"><div class="kpi-label">Unclassified events', text)


def test_meets_target_wording(no_gemini):
    write_telemetry([(S, 'INFO', '2026-07-01')] * 99 + [(F, 'ERROR', '2026-07-01')])
    note = note_of(executive(), 'Classified-call success rate')
    assert note == 'Meets 98% target · 1 failed calls in selected window'


def test_no_classified_calls_keeps_the_na_explanation(no_gemini):
    write_telemetry([(None, None, '2026-07-01')] * 3 + [(None, None, None)] * 2)
    note = note_of(executive(), 'Classified-call success rate')
    assert 'enough outcome classification evidence' in note and 'undated' not in note


def test_active_status_note_is_a_decision_figure_and_caveat_moved_to_the_drawer(no_gemini):
    text = executive()
    assert re.search(r'\d+% of use cases have Active status', note_of(text, 'Active-status use cases'))
    assert 'not measured activity' not in note_of(text, 'Active-status use cases')
    assert 'not measured activity' in KPI_INFO['active_status_use_cases']['definition']


def test_methodology_is_in_the_drawer_and_formula_in_advanced_details():
    html = components._info_html(KPI_INFO['classified_success'], 'parquet')
    head, _, advanced = html.partition('<details class="kpi-more">')
    assert 'not verified end-to-end service availability' in head and 'no timestamp' in head and 'reported separately' in head
    assert 'x 100' in advanced and 'x 100' not in head and 'FLOW-END' in advanced


def test_note_line_breaks_render_as_br(monkeypatch):
    shown = []
    monkeypatch.setattr(components.st, 'markdown', lambda body, **k: shown.append(body))
    components.kpi('L', 'V', 'line one' + chr(10) + 'line two')
    assert 'line one<br>line two' in shown[0]
