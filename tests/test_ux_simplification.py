"""V1.1 UX simplification: presentation only. Formulas and classification are covered by test_phase1_metrics.py."""
import re
from src import components, insights
from src.insights import KPI_INFO
from tests.test_phase1_metrics import page, write_telemetry, MIXED, no_gemini  # noqa: F401  (fixture reuse)


def test_drawer_leads_with_meaning_why_source_and_collapses_mechanics():
    html = components._info_html(KPI_INFO['classified_success'], 'parquet')
    head, _, details = html.partition('<details class="kpi-more">')
    assert [h in head for h in ('What it means', 'Why it matters', 'Source')] == [True] * 3
    for technical in ('FLOW-END', 'FLOW-ERROR', 'Lineage', 'does not indicate freshness', 'How it is derived', 'x 100'):
        assert technical not in head and technical in details
    assert 'Advanced metric details' in html


def test_every_kpi_has_a_why_line():
    assert all(info.get('why') for info in KPI_INFO.values())


def test_focus_bullets_only_for_triggered_findings():
    assert insights.executive_focus_bullets([]) == []
    items = [{'title': 'A'}, {'title': 'B'}]
    assert insights.executive_focus_bullets(items) == ['A', 'B']


def test_platform_health_order_and_primary_cards(no_gemini):
    write_telemetry(MIXED)
    _, text = page('Platform health')
    order = [text.index(x) for x in ('Classified-call success rate', 'Most frequent errors', 'Failed classified calls by model', 'Supporting evidence')]
    assert order == sorted(order)
    assert text.index('kpi-label">Total classified calls') < text.index('Most frequent errors')   # volume and outcome cards now precede failure analysis
    assert '50.0% of telemetry events could not be classified and are excluded from reliability calculations.' in text


def test_replacement_wording_is_not_alarmist(no_gemini):
    _, text = page('Model lifecycle')
    assert 'Replacement candidates requiring review' not in text and 'Alternative model may require additional assessment' not in text
    assert 'High-risk replacements' not in text and 'itself high risk' not in text
