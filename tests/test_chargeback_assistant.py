"""Chargeback Reconciliation Assistant: evidence-first, rule-based team routing, bounded AI, advisory, graceful fallback."""
import json
import pandas as pd
import pytest
from src import chargeback_assistant as ca


def _charges():
    # Azure: billed MORE than attributed and over threshold -> MuleSoft route.
    # GCP:   billed LESS than attributed and over threshold -> Provider Billing route.
    # AWS:   within threshold -> no escalation.
    return pd.DataFrame({'provider': ['Azure', 'AWS', 'GCP'],
                         'provider_bill': [100000, 100000, 90000],
                         'platform_usage': [90000, 99000, 100000],
                         'variance': [11.11, 1.00, 10.00],
                         'status': ['Review', 'Matched', 'Review'],
                         'period': ['Oct 2026'] * 3})


def _good(owner='Interface Team'):
    return json.dumps({'observed_variance': 'Provider billing log $100,000 vs MuleSoft $90,000; difference $10,000; variance 11.11% over the 5% threshold.',
                       'what_happened': 'The provider billed $10,000 more than the platform attributed.',
                       'who_to_engage': 'Routed to the Interface team (MuleSoft API Manager layer).',
                       'recommended_actions': 'Request the MuleSoft attribution logs for the period.',
                       'owner_category': owner})


# ---- Evidence + routing -------------------------------------------------------------------------
def test_provider_log_higher_routes_to_mulesoft():
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), threshold=5)
    assert ev['Direction'].startswith('Provider billing log is higher')
    assert ev['Exceeds review threshold'] == 'Yes'
    assert ev['Routed team'] == ca.ROUTE_MULESOFT
    assert ev['Difference (provider log - MuleSoft)'] == '$10,000'


def test_provider_log_lower_routes_to_provider_billing():
    ev = ca.build_evidence(_charges(), ca.make_focus('GCP'), threshold=5)
    assert ev['Direction'].startswith('Provider billing log is lower')
    assert ev['Routed team'] == ca.ROUTE_PROVIDER
    assert ev['Difference (provider log - MuleSoft)'] == '-$10,000'


def test_within_threshold_is_matched_no_escalation():
    ev = ca.build_evidence(_charges(), ca.make_focus('AWS'), threshold=5)
    assert ev['Exceeds review threshold'] == 'No'
    assert ev['Routed team'] == ca.ROUTE_NONE


def test_portfolio_focus_summarises_and_routes_top_exception():
    ev = ca.build_evidence(_charges(), ca.make_focus(None), threshold=5)
    assert ev['Providers over threshold'] == '2'
    assert ev['Top exception provider'] == 'Azure'                                    # highest variance (11.11%)
    assert ev['Top exception routed team'] == ca.ROUTE_MULESOFT
    assert ev['Total provider billing log'] == '$290,000'


def test_make_focus_normalises_all_values():
    assert ca.make_focus('All providers') == ('all', None) == ca.make_focus(None) == ca.make_focus('All')
    assert ca.make_focus('Azure') == ('provider', 'Azure')


def test_unknown_provider_is_handled():
    ev = ca.build_evidence(_charges(), ca.make_focus('Oracle'), threshold=5)
    assert ev['Status'] == 'No chargeback record for this provider' and ev['Routed team'] == ca.ROUTE_NONE


def test_evidence_is_deterministic():
    c = _charges()
    assert ca.build_evidence(c, ca.make_focus('Azure'), 5) == ca.build_evidence(c, ca.make_focus('Azure'), 5)


# ---- Prompt ------------------------------------------------------------------------------------
def test_prompt_is_grounded_and_carries_routing_rule():
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    system, user = ca.build_prompt(ev)
    assert json.dumps(ev, ensure_ascii=False) in user
    for token in ('Routed team', 'MuleSoft', 'FinOps', 'EXACTLY'):
        assert token in system


# ---- Response validation -----------------------------------------------------------------------
def test_valid_reply_passes_validation():
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    ca.validate(ca.parse_sections(_good()), ev)                                       # does not raise


def test_off_list_owner_is_rejected():
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    with pytest.raises(ValueError):
        ca.validate(ca.parse_sections(_good(owner='Everyone')), ev)


def test_invented_large_number_is_rejected_but_small_advice_number_is_allowed():
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    good = ca.parse_sections(_good())
    good['recommended_actions'] = 'Request the MuleSoft attribution logs for the last 3 months.'   # small number ok
    ca.validate(good, ev)
    bad = ca.parse_sections(_good())
    bad['what_happened'] = 'An unexplained $77,777 gap appeared.'                      # 5-digit figure not in evidence
    with pytest.raises(ValueError):
        ca.validate(bad, ev)


def test_missing_or_extra_section_is_rejected():
    with pytest.raises(ValueError):
        ca.parse_sections(json.dumps({'observed_variance': 'x'}))                      # missing keys
    with pytest.raises(ValueError):
        ca.parse_sections(json.dumps({**json.loads(_good()), 'extra': 'y'}))           # extra key


def test_section_returned_as_list_is_flattened_to_text():
    reply = json.loads(_good())
    reply['recommended_actions'] = ['Ask MuleSoft for logs.', 'Reconcile before allocation.']
    out = ca.parse_sections(json.dumps(reply))
    assert out['recommended_actions'] == 'Ask MuleSoft for logs. Reconcile before allocation.' and '[' not in out['recommended_actions']


# ---- analyze (bounded call mocked) --------------------------------------------------------------
def test_analyze_returns_validated_sections(monkeypatch):
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    monkeypatch.setattr(ca, '_generate', lambda system, user, model, **k: _good())
    out = ca.analyze(ev, 'gemini-x')
    assert set(out) == set(ca.SECTION_KEYS) and out['owner_category'] == 'Interface Team'


def test_analyze_raises_on_unusable_reply(monkeypatch):
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    monkeypatch.setattr(ca, '_generate', lambda *a, **k: 'Sure! Here is a summary.')   # not JSON
    with pytest.raises(Exception):
        ca.analyze(ev, 'gemini-x')


def test_analyze_raises_on_off_list_owner(monkeypatch):
    ev = ca.build_evidence(_charges(), ca.make_focus('Azure'), 5)
    monkeypatch.setattr(ca, '_generate', lambda *a, **k: _good(owner='Nobody'))
    with pytest.raises(ValueError):
        ca.analyze(ev, 'gemini-x')
