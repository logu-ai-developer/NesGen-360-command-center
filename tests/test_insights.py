import pandas as pd
from src import data
from src.insights import KPI_INFO, build_decision_brief, executive_focus, priority_breakdown


def _brief():
    return build_decision_brief(data.synthetic_apps(), data.synthetic_models(), data.synthetic_health(),
                                data.synthetic_charges(), data.synthetic_alerts())


def test_kpi_info_complete():
    for key, info in KPI_INFO.items():
        for field in ('definition', 'formula', 'source', 'dataset', 'metric'):
            assert info[field], (key, field)


def test_brief_items_have_evidence_action_owner():
    items = _brief()
    assert items
    for i in items:
        assert all(i[k] for k in ('severity', 'category', 'title', 'evidence', 'source', 'action', 'owner'))
    order = ['Critical', 'High', 'Medium', 'Low']
    assert [order.index(i['severity']) for i in items] == sorted(order.index(i['severity']) for i in items)


def test_chargeback_variance_flags_aws_only():
    items = [i for i in _brief() if i['category'] == 'Financial']
    assert [i['title'] for i in items] == ['AWS usage variance above threshold']


def test_clean_data_gives_empty_brief():
    health = pd.DataFrame({'success_rate': [99.5, 99.0], 'successful_calls': [995, 990], 'failed_calls': [5, 10], 'unclassified_events': [0, 0]})
    charges = pd.DataFrame({'provider': ['Azure'], 'provider_bill': [1], 'platform_usage': [1], 'variance': [1.0]})
    items = build_decision_brief(None, None, health, charges, None)
    assert items == []
    assert 'No decisions' in executive_focus(items)
    assert priority_breakdown(items) == 'No open findings'


def test_get_apps_falls_back_without_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'HUB_XLSX', tmp_path / 'missing.xlsx')
    assert data.get_apps() is not None and len(data.get_apps()) > 0
    assert data.get_apps().attrs['source_mode'] == 'synthetic fallback'
