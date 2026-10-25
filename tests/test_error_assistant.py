"""Phase 5B V1: Error Analysis Assistant. Evidence-grounded, explicit Analyze, five validated sections, safe fallback."""
import json
import pandas as pd
import pytest
from src import data, error_assistant as ea
from src.timewindow import resolve_window, anchor_date
from tests.test_phase1_metrics import no_gemini  # noqa: F401
from tests.test_phase3_experience import render, text_of


def _evidence(focus, demo=True):
    h = data.synthetic_health()
    window = resolve_window('6 Months', anchor_date(h.date))
    d = h[window.mask(h.date)]
    tel = data.get_telemetry(window, demo=demo)
    return ea.build_evidence(tel, d, window, focus), tel


def _good(**over):
    base = {'observed_pattern': 'Failures are concentrated by provider.',
            'supported_interpretation': 'Azure OpenAI ranks first by failures. ' + ea.REQUIRED_SENTENCE,
            'uncertainty_gaps': 'Environment analysis, error category, error-to-model relationship, ownership mapping and root-cause evidence are Not available; code and message pairings are inconsistent.',
            'investigation_steps': 'Review provider telemetry. Compare error concentrations.',
            'owner_category': 'Platform Support'}
    base.update(over)
    return json.dumps(base)


# ---- Evidence builder (PH-15) ---------------------------------------------------------------------
def test_focus_keys_and_unresolved_collapse_to_overall():
    assert ea.make_focus('Provider', 'AWS Bedrock', None) == ('provider', 'AWS Bedrock', None)
    assert ea.make_focus('Provider + Model', 'AWS Bedrock', 'Claude Sonnet 5.5') == ('provider_model', 'AWS Bedrock', 'Claude Sonnet 5.5')
    assert ea.make_focus('Provider', None, None) == ('overall', None, None)          # no provider chosen yet
    assert ea.make_focus('Overall window') == ('overall', None, None)


def test_overall_focus_is_deterministic_and_lists_unavailable_fields():
    ev, _ = _evidence(('overall', None, None))
    assert ev['Focus'] == 'Overall window'
    assert ev == _evidence(('overall', None, None))[0]
    for field in ea.UNAVAILABLE_FIELDS:
        assert ev[field] == 'Not available'
    assert 'Daily failed-call trend (window-wide)' in ev and 'Unclassified events excluded' in ev
    assert 'Provider' not in ev and 'Model' not in ev


def test_provider_focus_scopes_counts_to_that_provider():
    _, tel = _evidence(('overall', None, None))
    prov = tel['by_provider'].provider.astype(str).iloc[0]
    ev, _ = _evidence(('provider', prov, None))
    assert ev['Provider'] == prov and ev['Focus'] == f'Provider: {prov}'
    row = tel['by_provider'][tel['by_provider'].provider.astype(str) == prov]
    assert ev['Failed classified calls in focus'] == f"{int(row.failures.sum()):,}"


def test_provider_model_focus_scopes_counts_to_that_model():
    _, tel = _evidence(('overall', None, None))
    r = tel['by_model'].sort_values('failures', ascending=False).iloc[0]
    ev, _ = _evidence(('provider_model', str(r.provider), str(r.model)))
    assert ev['Model'] == str(r.model) and ev['Provider'] == str(r.provider)
    assert ev['Failed classified calls in focus'] == f"{int(r.failures):,}"


def test_unknown_model_share_is_reported():
    tel = {'stats': {'failed': 10, 'classified': 100, 'unclassified': 5, 'unclassified_pct': 4.5},
           'by_provider': pd.DataFrame({'provider': ['AWS Bedrock'], 'calls': [100], 'failures': [10]}),
           'by_model': pd.DataFrame({'model': ['Unknown', 'GPT-4o'], 'provider': ['AWS Bedrock', 'Azure OpenAI'], 'calls': [40, 60], 'failures': [3, 7]}),
           'errors': pd.DataFrame({'error_code': [500], 'error_message': ['Rate limit exceeded'], 'occurrences': [3]})}
    window = resolve_window('6 Months', anchor_date(data.synthetic_health().date))
    ev = ea.build_evidence(tel, data.synthetic_health(), window, ('overall', None, None))
    assert ev['Unknown-model share of failures'] == '30.00%'


def test_no_classified_calls_in_focus_is_handled():
    tel = {'stats': {'failed': 0, 'classified': 0, 'unclassified': 0, 'unclassified_pct': None},
           'by_provider': pd.DataFrame({'provider': [], 'calls': [], 'failures': []}),
           'by_model': pd.DataFrame({'model': [], 'provider': [], 'calls': [], 'failures': []}),
           'errors': pd.DataFrame({'error_code': [], 'error_message': [], 'occurrences': []})}
    window = resolve_window('6 Months', anchor_date(data.synthetic_health().date))
    ev = ea.build_evidence(tel, data.synthetic_health().iloc[0:0], window, ('overall', None, None))
    assert ev['Failure rate in focus'].startswith('N/A') and ev['Failed classified calls in focus'] == '0'
    assert ev['Daily failed-call trend (window-wide)'] == 'No daily data in window'


# ---- Prompt and grounding (PH-16) -----------------------------------------------------------------
def test_prompt_is_bounded_and_states_the_known_limits():
    ev, _ = _evidence(('overall', None, None))
    system, user = ea.build_prompt(ev)
    assert json.dumps(ev, ensure_ascii=False) in user and 'advisory' not in user
    for banned in ('outage', 'root cause', 'network', 'inconsistent', 'Not available', 'Platform Support'):
        assert banned in system
    assert ea.REQUIRED_SENTENCE in system


# ---- Response validation (PH-16/PH-17) ------------------------------------------------------------
def test_valid_reply_passes_validation():
    ev, _ = _evidence(('overall', None, None))
    sections = ea.parse_sections(_good())
    ea.validate(sections, ev)                                                        # does not raise


def test_gaps_may_list_root_cause_evidence_field_without_being_flagged():
    # Regression: the required gaps section lists "Root-cause evidence: Not available"; the label contains the
    # forbidden term "root-cause" but acknowledging the field must not be read as a causal claim.
    ev, _ = _evidence(('overall', None, None))
    sections = ea.parse_sections(_good(uncertainty_gaps='Root-cause evidence is Not available; no cause can be read from these fields.'))
    ea.validate(sections, ev)                                                        # does not raise
    # A real causal claim is still rejected even when the field label is also present.
    bad = ea.parse_sections(_good(uncertainty_gaps='Root-cause evidence is Not available, but the root cause is the provider.'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_missing_and_extra_sections_are_rejected():
    with pytest.raises(ValueError):
        ea.parse_sections(json.dumps({'observed_pattern': 'x'}))
    with pytest.raises(ValueError):
        ea.parse_sections(_good()[:-1] + ', "extra": "no"}')


def test_forbidden_causal_wording_is_rejected():
    ev, _ = _evidence(('overall', None, None))
    bad = ea.parse_sections(_good(observed_pattern='This was caused by a provider outage.'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_missing_required_no_cause_sentence_is_rejected():
    ev, _ = _evidence(('overall', None, None))
    bad = ea.parse_sections(_good(supported_interpretation='Azure OpenAI ranks first by failures.'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_invented_number_is_rejected():
    ev, _ = _evidence(('overall', None, None))
    bad = ea.parse_sections(_good(observed_pattern='There were 123456789 failures recorded.'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_unsupported_owner_is_rejected():
    ev, _ = _evidence(('overall', None, None))
    bad = ea.parse_sections(_good(owner_category='Network Operations'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_unavailable_evidence_referenced_outside_gaps_is_rejected():
    ev, _ = _evidence(('overall', None, None))
    bad = ea.parse_sections(_good(observed_pattern='The PROD environment shows the most failures.'))
    with pytest.raises(ValueError):
        ea.validate(bad, ev)


def test_analyze_runs_generate_then_validates(no_gemini, monkeypatch):
    ev, _ = _evidence(('overall', None, None))
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good())
    assert set(ea.analyze(ev, 'model-x')) == set(ea.SECTION_KEYS)
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good(owner_category='Nobody'))
    with pytest.raises(ValueError):
        ea.analyze(ev, 'model-x')


# ---- Interaction and fallback (PH-14) -------------------------------------------------------------
def _ph_text(at):
    return (text_of(at) + '\n' + '\n'.join(str(w.value) for w in at.warning) + '\n'
            + '\n'.join(df.value.to_string() for df in at.table))


def test_evidence_and_advisory_visible_without_ai_and_no_call_on_render(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no call on render')))
    at, _ = render('Platform health')
    text = _ph_text(at)
    assert 'Error Analysis Assistant' in text and ea.ADVISORY in text
    assert 'AI Interpretation' not in text
    assert [b.label for b in at.button if b.label == 'Analyze Failures'] == ['Analyze Failures']
    assert any('Not available' in df.value.to_string() for df in at.table)


def test_focus_change_does_not_call_and_click_calls_once(no_gemini, monkeypatch):
    calls = []
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: calls.append(1) or _good())
    at, _ = render('Platform health')
    next(s for s in at.selectbox if s.key == 'ea_scope').set_value('Provider').run()
    assert not calls and 'AI Interpretation' not in _ph_text(at)                      # focus change never calls AI
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert len(calls) == 1 and 'AI Interpretation' in _ph_text(at) and ea.ADVISORY in _ph_text(at)


def test_focus_change_clears_prior_result(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good())
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert 'AI Interpretation' in _ph_text(at)
    next(s for s in at.selectbox if s.key == 'ea_scope').set_value('Provider').run()
    assert 'AI Interpretation' not in _ph_text(at) and ea.ADVISORY in _ph_text(at)    # stale result hidden


def test_gemini_failure_falls_back_and_keeps_evidence(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('GEMINI_API_KEY is missing')))
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    text = _ph_text(at)
    assert not at.exception and ea.UNAVAILABLE in text and ea.ADVISORY in text
    assert 'Not available' in text                                                    # evidence stays visible


def test_malformed_reply_is_treated_as_unavailable(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: 'The provider had an outage.')
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    text = _ph_text(at)
    assert ea.UNAVAILABLE in text and 'AI Interpretation' not in text and 'outage' not in text


def test_validation_rejection_is_treated_as_unavailable(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good(investigation_steps='This happened because of a network issue.'))
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert ea.UNAVAILABLE in _ph_text(at) and 'AI Interpretation' not in _ph_text(at)
