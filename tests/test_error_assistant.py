"""Error Analysis Assistant (P4.2): Provider -> Model -> Error code cascade. The evidence is scoped to one model's
real occurrences of one code (a model never shows a code it does not have); the model explains that code (meaning,
why, how to reduce, what the user can do), grounded in the count, with the general-guidance disclaimer."""
import json
import pandas as pd
import pytest
from src import data, error_assistant as ea
from src.timewindow import resolve_window, anchor_date
from tests.test_phase1_metrics import no_gemini  # noqa: F401
from tests.test_phase3_experience import render, text_of


def _tel():
    h = data.synthetic_health()
    window = resolve_window('6 Months', anchor_date(h.date))
    return h[window.mask(h.date)], window, data.get_telemetry(window, demo=True)


def _evidence(focus=None):
    d, window, tel = _tel()
    if focus is None:
        b = tel['error_breakdown'].iloc[0]
        focus = ea.make_focus(None, str(b.provider), str(b.model), str(b.error_code))
    return ea.build_evidence(tel, d, window, focus), tel


def _good(**over):
    base = {'observed_pattern': 'Error code 429 occurred 1 time on this model.',
            'likely_causes': 'Code 429 generally indicates provider rate limiting. ' + ea.REQUIRED_SENTENCE,
            'how_to_reduce': 'Add client-side backoff with jitter and request a higher quota.',
            'user_guidance': 'Lower the request rate and retry with backoff.',
            'owner_category': 'Provider Management'}
    base.update(over)
    return json.dumps(base)


# ---- Focus + per-model codes ----------------------------------------------------------------------
def test_make_focus_requires_provider_model_code():
    assert ea.make_focus(None, 'AWS Bedrock', 'Claude Sonnet 5.5', '429') == ('provider_model_code', 'AWS Bedrock', 'Claude Sonnet 5.5', '429')
    assert ea.make_focus(None, 'AWS Bedrock', 'Claude Sonnet 5.5') == ('provider_model', 'AWS Bedrock', 'Claude Sonnet 5.5', None)
    assert ea.make_focus() == ('overall', None, None, None)


def test_a_model_only_exposes_its_own_error_codes():
    # The core P4.2 honesty fix: not every model carries every code (so a model with no 500 never shows one).
    _, _, tel = _tel()
    bd = tel['error_breakdown']
    assert {'model', 'provider', 'error_code', 'error_message', 'error_category', 'occurrences'}.issubset(bd.columns)
    per_model = bd.groupby(['provider', 'model']).error_code.nunique()
    assert per_model.max() < bd.error_code.nunique()                                  # no model has every code
    assert int(tel['errors'].occurrences.sum()) == int(bd.occurrences.sum())          # window-wide table agrees with the breakdown


def test_code_focus_is_scoped_to_the_model_and_code():
    _, _, tel = _tel()
    b = tel['error_breakdown'].iloc[0]
    ev, _ = _evidence(ea.make_focus(None, str(b.provider), str(b.model), str(b.error_code)))
    assert ev['Provider'] == str(b.provider) and ev['Model'] == str(b.model) and ev['Error code'] == str(b.error_code)
    assert ev['Occurrences of this error on this model'] == f"{int(b.occurrences):,}"
    assert ev['Error message (as recorded)'] == str(b.error_message)
    for field in ea.UNAVAILABLE_FIELDS:
        assert ev[field] == 'Not available'


def test_overall_focus_fallback_lists_top_codes():
    ev, _ = _evidence(ea.make_focus())
    assert ev['Focus'] == 'Overall window' and 'Top error codes (window-wide)' in ev
    assert ev == _evidence(ea.make_focus())[0]                                        # deterministic


# ---- Prompt -------------------------------------------------------------------------------------
def test_prompt_allows_code_knowledge_and_is_grounded():
    ev, _ = _evidence()
    system, user = ea.build_prompt(ev)
    assert json.dumps(ev, ensure_ascii=False) in user and 'advisory' not in user
    for token in ('429', 'general knowledge', 'Ground every', 'Not available', 'Platform Support'):
        assert token in system
    assert ea.REQUIRED_SENTENCE in system


# ---- Response validation ------------------------------------------------------------------------
def test_valid_reply_passes_validation():
    ev, _ = _evidence()
    ea.validate(ea.parse_sections(_good()), ev)                                       # does not raise


def test_llm_may_explain_error_code_causes_and_remediation():
    ev, _ = _evidence()
    sections = ea.parse_sections(_good(
        likely_causes='Code 503 generally means the upstream model was unavailable, often from provider-side overload. ' + ea.REQUIRED_SENTENCE,
        how_to_reduce='Add retry with 3 attempts and a 2-second backoff, and consider failover to a backup model.'))
    ea.validate(sections, ev)                                                         # small advice numbers allowed; causes allowed


def test_parse_sections_renders_a_list_section_as_plain_text():
    reply = json.dumps({'observed_pattern': 'x', 'likely_causes': 'y ' + ea.REQUIRED_SENTENCE,
                        'how_to_reduce': ['Add backoff.', 'Request a higher quota.'],
                        'user_guidance': 'Lower the request rate.', 'owner_category': 'Platform Support'})
    sections = ea.parse_sections(reply)
    assert sections['how_to_reduce'] == 'Add backoff. Request a higher quota.' and '[' not in sections['how_to_reduce']


def test_missing_and_extra_sections_are_rejected():
    with pytest.raises(ValueError):
        ea.parse_sections(json.dumps({'observed_pattern': 'x'}))
    with pytest.raises(ValueError):
        ea.parse_sections(_good()[:-1] + ', "extra": "no"}')


def test_missing_general_guidance_disclaimer_is_rejected():
    ev, _ = _evidence()
    with pytest.raises(ValueError):
        ea.validate(ea.parse_sections(_good(likely_causes='Code 429 means rate limiting.')), ev)


def test_invented_large_count_is_rejected():
    ev, _ = _evidence()
    with pytest.raises(ValueError):
        ea.validate(ea.parse_sections(_good(observed_pattern='There were 123456789 failures recorded.')), ev)


def test_unsupported_owner_is_rejected():
    ev, _ = _evidence()
    with pytest.raises(ValueError):
        ea.validate(ea.parse_sections(_good(owner_category='Network Operations')), ev)


def test_analyze_runs_generate_then_validates(no_gemini, monkeypatch):
    ev, _ = _evidence()
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good())
    assert set(ea.analyze(ev, 'model-x')) == set(ea.SECTION_KEYS)
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good(owner_category='Nobody'))
    with pytest.raises(ValueError):
        ea.analyze(ev, 'model-x')


def test_analyze_appends_nesgen_platform_quota_guidance_for_rate_limit(no_gemini, monkeypatch):
    # For a 429 / rate-limit error, both NesGen-platform deployment-quota statements are added deterministically.
    ev = {'Error code': '429', 'Error category (as recorded)': 'Rate limit / Quota',
          'Occurrences of this error on this model': '1', 'This model failed classified calls': '1', 'This model classified calls': '1'}
    assert ea._is_capacity_error(ev)
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good())
    out = ea.analyze(ev, 'model-x')
    assert ea.PLATFORM_HOW_TO_REDUCE in out['how_to_reduce']
    assert ea.PLATFORM_USER_GUIDANCE in out['user_guidance']
    # A non-capacity error (content filter 400) does not get the quota statement.
    assert not ea._is_capacity_error({'Error code': '400', 'Error message (as recorded)': 'Content filter violation'})


# ---- Interaction and fallback -------------------------------------------------------------------
def _ph_text(at):
    return (text_of(at) + '\n' + '\n'.join(str(w.value) for w in at.warning) + '\n'
            + '\n'.join(df.value.to_string() for df in at.table))


def test_cascade_controls_and_evidence_visible_without_ai(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no call on render')))
    at, _ = render('Platform health')
    text = _ph_text(at)
    assert 'Error Analysis Assistant' in text and ea.ADVISORY in text and 'AI Interpretation' not in text
    assert [b.label for b in at.button if b.label == 'Analyze Failures'] == ['Analyze Failures']
    assert {'ea_provider', 'ea_model_focus', 'ea_code'} <= {s.key for s in at.selectbox}
    assert any('Not available' in df.value.to_string() for df in at.table)


def test_code_change_does_not_call_and_click_calls_once(no_gemini, monkeypatch):
    calls = []
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: calls.append(1) or _good())
    at, _ = render('Platform health')
    box = next(s for s in at.selectbox if s.key == 'ea_code')
    if len(box.options) > 1:
        box.set_value(box.options[1]).run()
    assert not calls and 'AI Interpretation' not in _ph_text(at)
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert len(calls) == 1 and 'AI Interpretation' in _ph_text(at) and ea.ADVISORY in _ph_text(at)


def test_code_change_clears_prior_result(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good())
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert 'AI Interpretation' in _ph_text(at)
    box = next(s for s in at.selectbox if s.key == 'ea_code')
    if len(box.options) > 1:
        box.set_value(box.options[-1]).run()
        assert 'AI Interpretation' not in _ph_text(at) and ea.ADVISORY in _ph_text(at)


def test_gemini_failure_falls_back_and_keeps_evidence(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('GEMINI_API_KEY is missing')))
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    text = _ph_text(at)
    assert not at.exception and ea.UNAVAILABLE in text and ea.ADVISORY in text and 'Not available' in text


def test_malformed_reply_is_treated_as_unavailable(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: 'Just some prose, not JSON.')
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert ea.UNAVAILABLE in _ph_text(at) and 'AI Interpretation' not in _ph_text(at)


def test_validation_rejection_is_treated_as_unavailable(no_gemini, monkeypatch):
    monkeypatch.setattr(ea, '_generate', lambda *a, **k: _good(owner_category='Nobody'))
    at, _ = render('Platform health')
    next(b for b in at.button if b.label == 'Analyze Failures').click().run()
    assert ea.UNAVAILABLE in _ph_text(at) and 'AI Interpretation' not in _ph_text(at)
