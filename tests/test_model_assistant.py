"""Phase 4B: Model Evaluation Assistant. Evidence first, explicit Analyze, advisory notice, graceful fallback."""
import json
import pandas as pd
import pytest
from src import model_assistant as ma
from src.data import enrich_models, synthetic_models
from tests.test_phase1_metrics import no_gemini  # noqa: F401
from tests.test_phase3_experience import render, text_of

GOOD = json.dumps({'current_position': 'A.', 'governance_risks': 'B.', 'evidence_gaps': 'C.', 'suggested_next_review_areas': 'D.'})
EVIDENCE_LABELS = ['Risk', 'Review Status', 'Retirement Status', 'Suggested Candidate', 'Replacement Readiness',
                   'Migration Readiness', 'Evidence Completeness', 'Retirement Urgency', 'Illustrative Decommission Readiness Score']


def _row():
    return enrich_models(synthetic_models(), today='2026-10-23').iloc[0]


def _page_text(at):
    return (text_of(at) + '\n' + '\n'.join(str(w.value) for w in at.warning) + '\n'
            + '\n'.join(str(df.value.to_string()) for df in at.table))


def test_evidence_has_every_required_item_and_is_deterministic():
    e = ma.build_evidence(_row())
    assert list(e)[1:] == EVIDENCE_LABELS
    assert e == ma.build_evidence(_row())


def test_prompt_is_grounded_and_bounded():
    e = ma.build_evidence(_row())
    system, user = ma.build_prompt(e)
    assert json.dumps(e, ensure_ascii=False) in user               # exactly the displayed evidence
    for banned in ('approve', 'invent', 'ONLY the facts'):
        assert banned in system
    for key, _ in ma.SECTIONS:
        assert key in system
    assert 'Not available' in system and 'advisory' not in user


def test_parse_requires_all_four_sections():
    assert set(ma.parse_sections(GOOD)) == {k for k, _ in ma.SECTIONS}
    with pytest.raises(ValueError):
        ma.parse_sections(json.dumps({'current_position': 'only one'}))
    with pytest.raises(ValueError):
        ma.parse_sections('not json at all')


def test_evidence_and_advisory_visible_without_ai_and_no_call_on_render(no_gemini, monkeypatch):
    def boom(*a, **k):
        raise AssertionError('analysis must not run on render')
    monkeypatch.setattr(ma, '_generate', boom)
    at, _ = render('Model lifecycle')
    text = _page_text(at)
    assert 'Model Evaluation Assistant' in text and ma.ADVISORY in text
    assert 'AI Interpretation' not in text
    assert [b.label for b in at.button if b.label == 'Analyze Model'] == ['Analyze Model']
    table = next(df.value for df in at.table if 'Evidence' in df.value.columns and 'Risk' in set(df.value['Evidence']))
    assert list(table['Evidence']) == EVIDENCE_LABELS


def test_dropdown_change_does_not_analyze(no_gemini, monkeypatch):
    calls = []
    monkeypatch.setattr(ma, '_generate', lambda *a, **k: calls.append(1) or GOOD)
    at, _ = render('Model lifecycle')
    box = next(s for s in at.selectbox if s.label == 'Model')
    box.set_value(box.options[1]).run()
    assert not calls and 'AI Interpretation' not in _page_text(at)


def test_analyze_click_runs_once_and_shows_sections_then_notice(no_gemini, monkeypatch):
    seen = []
    monkeypatch.setattr(ma, '_generate', lambda system, user, model: seen.append((system, user, model)) or GOOD)
    at, _ = render('Model lifecycle')
    next(b for b in at.button if b.label == 'Analyze Model').click().run()
    assert len(seen) == 1 and not at.exception
    text = _page_text(at)
    for _, label in ma.SECTIONS:
        assert label in text
    assert 'AI Interpretation' in text and ma.ADVISORY in text
    # changing the model afterwards hides the stale result and does not call again
    box = next(s for s in at.selectbox if s.label == 'Model')
    box.set_value(box.options[1]).run()
    assert len(seen) == 1 and 'AI Interpretation' not in _page_text(at) and ma.ADVISORY in _page_text(at)


def test_gemini_failure_falls_back_and_keeps_evidence(no_gemini, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError('GEMINI_API_KEY is missing')
    monkeypatch.setattr(ma, '_generate', fail)
    at, _ = render('Model lifecycle')
    next(b for b in at.button if b.label == 'Analyze Model').click().run()
    assert not at.exception and not at.error
    text = _page_text(at)
    assert ma.UNAVAILABLE in text and ma.ADVISORY in text
    assert all(label in text for label in EVIDENCE_LABELS)


def test_unparseable_reply_is_treated_as_unavailable(no_gemini, monkeypatch):
    monkeypatch.setattr(ma, '_generate', lambda *a, **k: 'Sure! This model is approved.')
    at, _ = render('Model lifecycle')
    next(b for b in at.button if b.label == 'Analyze Model').click().run()
    text = _page_text(at)
    assert ma.UNAVAILABLE in text and 'AI Interpretation' not in text and 'This model is approved' not in text
