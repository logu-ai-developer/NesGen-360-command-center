# NesGen 360 Working Log

Running record of implementation work. Newest entry last. Test counts are real runs on the date shown.

## 2026-10-23

### 1. Executive Summary: finding narrative
**Goal:** each Priority Finding says what happened, why it matters and what to do, before the user opens a page.

- `src/insights.py`: `_item` gains `summary`, `impact`, `recommended_action`; all five finding rules fill them in. Rules, thresholds, severity, owner and `evidence` are unchanged.
- `app.py`: card shows Title, Summary, Impact, Action, then a secondary line (severity · category · owner). The "Open … →" button and routing are unchanged.
- `src/components.py`: new `.finding-line` style.
- Tests: added `test_findings_carry_executive_narrative` in `tests/test_executive_notes.py`.
- Not changed: the "AI findings" and "Recommended actions" panels still use the old `evidence` and `action` fields.
- Validation: 30 targeted tests passed.

### 2. Model Lifecycle: governance clarity (Phase 4A)
**Goal:** separate risk, review, retirement and replacement concepts.

- Page title shown as **Model Inventory & Decisions**. The navigation key stays "Model lifecycle" (routing out of scope).
- Risk, Review and Retirement are separate chips and table columns, each with its own icon, label and palette.
- Ordering: High risk, Overdue review, Retirement candidate (or scheduled), Normal (`model_attention_rank`).
- **Suggested Candidate** replaces "Replacement" wording. Never the same model, retired, scheduled or approved-retirement, High-risk, or incomplete-evidence models. When none qualifies the field reads "No suitable candidate identified".
- Readiness factors added: Replacement readiness, Migration readiness, Evidence completeness, Retirement urgency.
- **Illustrative Decommission Readiness Score**: current-model quality removed. Weights 35 candidate exists, 20 candidate risk, 25 time before retirement, 20 evidence (sum 100). An expander shows factors, weights and limitations.
- Files: `src/data.py`, `src/insights.py`, `app.py`.
- Tests: four new candidate and status tests in `tests/test_v11_data.py`; lifecycle sort test updated in `tests/test_phase3_experience.py`.
- Validation: full suite 301 passed, 1 failed. The failure was a bug in my own new test, fixed afterwards and re-run alone (7 passed).

### 3. Phase 4A follow-up decisions
- Removed the "Replacement candidates requiring review" card. The KPI row now has 3 columns. No replacement metric was defined.
- Removed the unapproved evaluation-score < 70 exclusion (`MIN_CANDIDATE_SCORE` deleted). No numeric threshold remains.
- `model_review_priority` and its test left unchanged on purpose.
- Tests: `test_ux_simplification.py` now asserts the card is absent; `test_v11_data.py` covers approved-retirement and incomplete-evidence exclusions, plus a new test that a low score does not exclude a candidate.
- Validation: full suite **303 passed** (`..\.venv\Scripts\python.exe -m pytest -q`).

### 4. Phase 4B: Model Evaluation Assistant (ML-10 to ML-14)
- New `src/model_assistant.py`: deterministic `build_evidence`, grounded `build_prompt`, `parse_sections`, one tool-free Gemini call under the existing quota (`reserve`/`complete`). `src/agent.py` and its tool allow-list untouched.
- `app.py`: new "Model Evaluation Assistant" section on Model Inventory & Decisions. Order: evidence table, Analyze Model, AI Interpretation (four sections), advisory notice. Analysis runs only on the button; changing the model hides the old result and never calls Gemini.
- Failure or an unusable reply shows "AI analysis is currently unavailable."; evidence stays visible.
- Tests: new `tests/test_model_assistant.py` (8). Changed `test_no_ai_features_were_added`: it forbade the string "Evaluation Assistant", which Phase 4B now approves; the Error Analysis guard is kept.
- Validation: full suite 311 passed. Live Gemini run: key was initially missing from the app process (`GEMINI_API_KEY is missing`), later reported running; result not recorded. Not browser-checked.

## Open items
- Panel caption above the inventory table still describes the old ordering ("high risk + overdue review, high risk, review due, migration required"). Not changed: outside the brief.
- Browser validation: not performed for any of the above.
- Live Gemini check of the Model Evaluation Assistant: key issue resolved by the user; outcome not reported, so not recorded as verified.
- Readiness card wording flagged as potentially misleading; proposed change not applied.
- Current status, roadmap and test-count history: see "Current Approved State", "Phase History" and "Roadmap" in CLAUDE.md. Review decisions: `docs/VALIDATION_RECORD.md`.

## V1.2 checklist mapping (as of 2026-10-23)

Source: the V1.2 checklist screenshots (F-01..F-13, EX-01..EX-14, ML-01..ML-14). "Verified" means covered by code and automated tests; none of it has had browser review.

### ML items delivered
| ID | Item | Where it landed | Evidence |
|---|---|---|---|
| ML-01 | Rename Governance portfolio | Page title "Model Inventory & Decisions"; panel "Model inventory and decisions"; nav key "Model lifecycle" unchanged | `test_lifecycle_labels_sorting_and_risk_badges` |
| ML-02 | Highlight risk records | Risk chip with icon and text, left-border accent follows risk only | same test |
| ML-03 | Separate risk from lifecycle | Separate Risk, Review and Retirement chips and columns, each with its own palette | same test |
| ML-04 | Prioritize attention records | `model_attention_rank`: High risk, Overdue review, Retirement candidate, Normal | `test_status_concepts_are_independent_and_ranked` |
| ML-05 | Strengthen replacement rules | Same, retired, scheduled, approved-retirement, High-risk and incomplete-evidence models excluded; no score threshold | `test_candidates_exclude_invalid_models`, `test_low_evaluation_score_is_not_an_exclusion_rule` |
| ML-06 | Safe replacement wording | "Suggested candidate", "not an approval" | UI text |
| ML-07 | Handle no replacement | "No suitable candidate identified"; no weak pick | `test_no_suitable_candidate_is_none_not_weak_pick` |
| ML-08 | Revisit decommission readiness | Four separate factors; current-model quality removed from the score | `enrich_models` |
| ML-09 | Disclose combined scoring | "Illustrative Decommission Readiness Score" with weights and limitations expander | UI expander |

ML-10 to ML-14 (Model Evaluation Assistant, Phase 4B): implemented in entry 4 below; first live Gemini result not yet recorded (see `docs/VALIDATION_RECORD.md`).

### Items to review against the checklist
- **ML-01 wording:** the checklist says "Model inventory and decisions"; the page title uses "Model Inventory & Decisions" (title case, ampersand), as requested in the brief. Confirm that is acceptable.
- **F-12 and F-13 (accessibility, responsive layout) stay Partial.** The new chips add icons and text, but nothing was checked at narrow width or with the keyboard.
- **F-02 stays Partial.** No layout work was done against the screenshot style.
- **EX items:** the finding narrative (entry 1) adds to EX-07, EX-08 and EX-14. I did not change any EX status; the checklist already shows them Complete.


## 2026-10-23 documentation update
- `CLAUDE.md`: added "Current Approved State", updated Phase History with Phase 4, 4A and 4B and the test-count history, added missing Closed Decisions, rewrote the Roadmap (Phase 5A added as planned and pending approval; earlier items moved to "Previously listed, not scheduled").
- New `docs/VALIDATION_RECORD.md`: implemented, accepted, rejected, open and backlog items.
- Superseded notes added to `docs/TEST_REPORT.md`, `docs/VALIDATION.md` and `docs/V1_1_CHANGES.md`. No application code, test or metric was touched.


## 2026-10-25 Phase 5B V1: Error Analysis Assistant (PH-14 to PH-17) + 5B-A scope wording

Design review (previous turn) confirmed the available evidence. This entry is the implementation.

**5B-A scope wording.** The Platform Health scope caption and two P95 card notes previously said charts "follow the Environment filter". That is true only for synthetic/demo telemetry, which carries a per-environment breakdown; the real telemetry aggregates and the real daily health frame do not, so on real data the Environment filter does not change the page. Caption and notes corrected. No metric, calculation or filter logic changed.

**Error Analysis Assistant** (`src/error_assistant.py`, new; wired into `health()` in `app.py` as section 5, between Failure analysis and Supporting evidence). Reuses the Model Evaluation Assistant pattern (`src/model_assistant._generate`: one bounded Gemini call, no tools, no web, under the existing quota and input budget).

- **PH-14:** optional section, evidence shown first, Focus selector + Analyze Failures button. AI runs only on click; changing focus never calls and hides any stale result (result is keyed to the focus it ran for). Focus options: Overall window / Provider / Provider + Model only. Error code and environment focuses are deliberately not offered (relationships not in the approved evidence model).
- **PH-15:** `build_evidence` returns a deterministic ordered dict (time window, focus, failed count, failure rate and classified calls in focus, provider/model when chosen, top 3 window-wide error code/message pairs, window-wide daily failed-call trend summary, Unknown-model share of failures, unclassified-events excluded). It always includes five "Not available" rows (environment analysis, error category, error-to-model relationship, ownership mapping, root-cause evidence). The same dict is displayed and passed to Gemini.
- **PH-16:** dedicated evidence JSON only. The prompt states the code/message pairings are inconsistent, that causes cannot be established, and that unavailable evidence must be acknowledged. `validate()` rejects forbidden causal terms (outage, incident, degradation, infrastructure, network, capacity, quota, root cause, provider/service failure, "caused by"/"because of"/"due to"), a missing required "No cause is established…" sentence, owner values outside the closed list, unavailable-evidence terms used outside the gaps section, invented numbers (any number not present in the evidence), and missing/extra sections. Any failure shows "AI analysis is currently unavailable." with the evidence still visible.
- **PH-17:** exactly five sections — Observed Pattern, Supported Interpretation (must carry the no-cause sentence), Uncertainty and Evidence Gaps (required, lists the unavailable fields), Suggested Investigation Steps (≤3, framed as checks), Owner Category (closed list: Platform Support, Provider Management, Model Enablement, FinOps; default Platform Support).
- **Advisory** "AI guidance is advisory only. Root causes are not established by this evidence." always shown, with or without AI output.
- **Failure handling** reuses the Model Evaluation Assistant path (missing key, disabled AI, quota, timeout, malformed reply, validation failure → fallback; key redacted in logs).

**Tests.** New `tests/test_error_assistant.py` (21): evidence builder for the three focuses plus Unknown-model and no-classified-call cases; prompt grounding; validation for missing/extra section, forbidden causal wording, missing no-cause sentence, invented number, unsupported owner, unavailable-evidence-outside-gaps; interaction (no call on render, no call on focus change, one call per click, focus change clears the result); fallbacks (Gemini unavailable, malformed JSON, validation rejection). `tests/test_phase3_experience.py`: the stale `test_no_ai_features_were_added` (which blocked "Error Analysis") replaced with `test_approved_assistants_are_present_and_bounded`. All other Platform Health and metric tests preserved.

Out of scope and untouched: root-cause analysis, environment analysis on real telemetry, error taxonomy, ownership discovery, baseline comparisons, new telemetry relationships, provider blame, incident detection.
