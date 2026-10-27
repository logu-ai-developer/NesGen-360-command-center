# Review and Validation Record

Traceability for review cycles. This file records what was decided, not how the code works. Test results are real runs only; nothing here is estimated.

## Record 1: Phase 4 review cycle, 2026-10-23

### Scope
- Executive finding narrative.
- Model Inventory & Decisions governance clarity (Phase 4A) and its follow-up decisions.
- Model Evaluation Assistant (Phase 4B), first live Gemini run.
- Review of the "Avg illustrative readiness score" wording.
- Platform Health status assessment (inspection only).

### Implemented decisions
| Decision | Result |
|---|---|
| Findings show summary, impact and recommended action | Done. Rules, thresholds, routing, drawers unchanged |
| Risk, Review and Retirement shown as separate concepts | Done (chips and columns) |
| Attention order: High risk, Overdue review, Retirement candidate, Normal | Done |
| "Suggested candidate" wording; no weak pick | Done |
| Exclusions: same, retired, scheduled, approved retirement, High-risk, incomplete evidence | Done |
| Remove "Replacement candidates requiring review" card | Done; no metric redefined |
| Remove the evaluation score below 70 exclusion | Done; no numeric threshold remains |
| Keep `model_review_priority` unchanged | Done |
| Illustrative Decommission Readiness Score with weights and limitations | Done |
| Model Evaluation Assistant: evidence first, explicit Analyze, advisory notice, fallback | Done |

### Accepted feedback
- Executives need what happened, why it matters and what to do on the card itself.
- Model risk, review obligation, retirement status and replacement suitability must not share one indicator.
- Candidate suitability must use only the approved exclusion rules.
- AI may explain displayed evidence but is never the governance authority.

### Rejected feedback and interim choices
- Counting Medium-risk candidates in the replacement card: an interim choice made during implementation, rejected. The card was removed instead.
- Evaluation score below 70 as an exclusion rule: an implementation choice that was not an approved rule; removed.
- Removing the unused `model_review_priority`: rejected; kept for future review.

### Open review items
- **Readiness wording:** "Avg illustrative readiness score" is potentially misleading for executives. It is on Model Inventory & Decisions, not on the Executive page. Recommended label "Retirement preparedness (illustrative)" with a note that higher means easier to retire; not applied. Awaiting a decision.
- **Live Gemini check:** the first attempt reported `GEMINI_API_KEY is missing` because the app process did not have the key. The user then reported the app running with the key. The outcome of that run (four sections returned, grounding, advisory notice) has not been reported, so it is **not recorded as verified**.
- **Browser review:** not performed for any Phase 4 screen.
- **Stale caption:** the inventory panel caption still describes the older ordering.

### Validation results (full suite)
- Phase 4A: 301 passed, 1 failed (defect in a new test, fixed and re-run alone); then 303 passed after the follow-up decisions.
- Phase 4B: 311 passed.
- Not tested: a live Gemini response, any browser rendering.

### Future backlog (not scheduled)
- Phase 5A Platform Health UX: scope listed in `CLAUDE.md` (Roadmap), pending approval.
- Error Analysis Assistant, remainder of the Model Review Workflow, Scenario Planning: previously listed, no approved scope.

## Record 2: Platform Health assessment, 2026-10-23 (inspection only)

No code, test or documentation was changed by the assessment itself.

- Complete: PH-01, PH-02, PH-03, PH-09, PH-11.
- Partial: PH-04, PH-05, PH-06, PH-07, PH-08, PH-10, PH-12, PH-13, PH-16.
- Missing: PH-14, PH-15, PH-17 (no Error Analysis Assistant exists). *(Superseded: PH-04 to PH-13 delivered in Phase 5A, PH-14 to PH-17 in Phase 5B V1 — see Record 3.)*
- Closed decisions respected: Services Healthy KPI stays removed; metric names and classification stay frozen; "P95 latency (true)" is a pending rename of an already approved name, not a new decision.
- Open point carried to 5A planning: a true model to provider to error drill-down may need a data-layer change, because the real-telemetry error query has no model column.

## Record 3: Phase 5A and Phase 5B V1, 2026-10-23 to 2026-10-25

### Scope
- Phase 5A Platform Health UX refinement (PH-04, 05, 06, 07, 08, 10, 12, 13), presentation only.
- Phase 5B-A scope-wording correction.
- Phase 5B V1 Error Analysis Assistant (PH-14 to PH-17).

### Implemented decisions
- Platform Health groups: Volume, Outcomes, Performance, Failure analysis, Error Analysis Assistant, Supporting evidence.
- "Event-level P95 latency" replaces "P95 latency (true)"; daily-trend and peak-daily P95 are trend context, never SLA figures.
- "View supporting evidence" replaces "Evidence tables (errors, models, providers)".
- Synthetic scenarios and illustrative alerts are labelled "Illustrative synthetic scenario"; the synthetic "Internal server error" is paired with code 500.
- Error Analysis Assistant is evidence-first, advisory, runs only on an explicit Analyze Failures click, returns exactly five validated sections (Observed Pattern, Supported Interpretation, Uncertainty and Evidence Gaps, Suggested Investigation Steps, Owner Category from a closed list), and never claims a cause. It reuses the Model Evaluation Assistant's bounded Gemini call.

### Accepted feedback
- Executives must see which controls affect which content; the real-data Environment filter does not narrow charts and the page now says so.
- Volume, outcome and performance metrics belong in distinct groups; latency never mixes into Outcomes.
- An assistant may explain observed failure patterns but must disclose its evidence limits and never diagnose a cause.

### Rejected feedback and interim choices
- A true model → provider → error drill-down: not implemented; the telemetry does not link errors to a model or provider. Documented as a limitation in the UI instead of fabricating the relationship.
- Error-code and environment focus options for the assistant: excluded, as those relationships are not in the approved evidence model.

### Defects found and fixed
- The response validator rejected the assistant's own required "Root-cause evidence" gaps field because the label contains the forbidden term "root-cause"; surfaced by two live-run log lines. Fixed by excusing the exact unavailable-field labels before the causal/out-of-gaps checks, with a regression test; a genuine causal claim is still rejected.

### Open review items
- First clean live Gemini response from the Error Analysis Assistant not yet recorded.
- Browser review not performed for any Phase 5A or 5B screen (no browser tool available to Claude).

### Validation results (full suite)
- Phase 5A: 312 passed (full run, 2026-10-23).
- Phase 5B V1: a pre-fix run gave 334; after the validator fix, 335 passed (full run, 2026-10-25). Python 3.12.10, Streamlit 1.66.0.
- Not tested: a live Gemini response, any browser rendering.

### Future backlog (not scheduled)
- Phase 5B remainder: environment analysis on real telemetry, error categories, ownership discovery, baseline comparisons, model-error relationships — each needs a data-layer or taxonomy decision first.

## Record 4: Phase 6A WS-4 — Synthetic Adoption Boundary Coverage (UA-09), 2026-10-25

### Scope
- UA-09 demo visibility only. Make the existing "Use cases without approval date" path non-zero in demo mode. No new metric, no contract change, no architecture change.

### Implemented decision
- Option C: in `_synthetic_approval_dates` (`src/data.py`), after the dates are fully generated, convert `UNDATED_K=5` rows already older than every approval window (offset >= 181) to `NaT`. Seed 364, draw sizes and shuffle unchanged; undated rows keep ID, status, stage, segment and active-user values.

### Invariants held (proof)
- `canonical_use_cases == 100` — unchanged.
- Newly approved 30/90/180-day == 26 / 31 / 80 — unchanged.
- status {Active 62, Onboarding 15, Dormant 12, New 11}, stage {Industrialized 62, Sandbox 38}, segment {B2B 54, B2C 46} — unchanged.
- `assert_frame_equal(synthetic_apps(), synthetic_apps())` — still deterministic.

### Expected, documented moves (not invariants), old -> new
- older *dated* rows (offset >= 181): 20 -> 15.
- undated rows / "Use cases without approval date" card: 0 -> 5.
- "Previous period approvals" (180-day window only): 20 -> 15 (its previous period is the out-of-window older bucket the undated rows were drawn from); 30/90-day previous periods (3, 49) unchanged.

### Tests
- Modified: `tests/test_phase2_time.py:117` (older-dated 20->15 + `isna().sum()==UNDATED_K`); the 180-day previous-period assertion (20->15, commented).
- Added: `test_v11_data.py::test_synthetic_apps_has_exactly_undated_k_rows_without_approval_date`; `test_phase2_time.py::test_demo_adoption_exposes_the_undated_use_case_path`.
- No exact-count validation removed or weakened; 26/31/80 and ==100 remain as regression guardrails.

### Validation results (full suite)
- 337 passed (full run, 2026-10-25), exit 0. Python 3.12.10, Streamlit 1.66.0. Baseline 335 + 2 new tests.
- Browser rendering not performed (no browser tool available to Claude).

## Record 5: Phase 6A WS-1 — UA-05 terminology alignment, 2026-10-25

### Scope
- Rename the canonical count label to the contract name "Use cases in portfolio" (was "Use cases onboarded"). Presentation only.

### Implemented decision
- `app.py`: KPI label, header sentence, regional-chart title and series name updated to "in portfolio" / "In portfolio". `src/insights.py`: KPI_INFO['use_cases'] definition updated. Page/nav title "User onboarding and adoption" left unchanged (names the process, not the count).

### Tests
- Updated label assertions: `test_phase1_metrics.py:359`, `test_phase3_experience.py:129`, `test_phase2_time.py` (WS-4 demo-adoption test). No new tests; no exact-count test removed or weakened.

### Validation results (full suite)
- 337 passed (full run, 2026-10-25), exit 0 — unchanged count (presentation-only change). Python 3.12.10, Streamlit 1.66.0.

## Record 6: Phase 6A WS-2 — AI-04 assistant governance parity, 2026-10-25

### Gap found
- Yes. `model_assistant.analyze` had no number-grounding check; `error_assistant.validate` did. AI-04 was unevenly enforced.

### Implemented decision
- `src/model_assistant.py`: added `validate_grounding(sections, evidence)` (every reply number must appear in the evidence JSON), called from `analyze` after `parse_sections`. Mirrors the Error Analysis Assistant. Preserved: Analyze workflow, evidence-first flow, advisory boundary, Gemini integration, quota, UNAVAILABLE fallback.

### Tests added
- `test_model_assistant.py::test_validate_grounding_rejects_invented_numbers_but_allows_evidence_numbers`
- `test_model_assistant.py::test_analyze_rejects_invented_number_and_falls_back`

### Validation results (full suite)
- 339 passed (full run, 2026-10-25), exit 0 (337 + 2 new). Python 3.12.10, Streamlit 1.66.0.

## Record 7: Phase 6A WS-3 — UA-16 accessibility beyond colour, 2026-10-25

### Scope
- Adoption charts must not rely on colour alone. No metric, data or stage-semantics change.

### Implemented decision
- Segment chart (`app.py:347`): value labels + `pattern_shape` (B2C `/`), approved colours preserved.
- Regional chart (`app.py:349`): value labels on both series; existing legend kept.

### Tests added
- `test_phase3_experience.py::test_adoption_charts_are_not_colour_only`

### Validation results (full suite)
- 340 passed (full run, 2026-10-25), exit 0 (339 + 1 new). Python 3.12.10, Streamlit 1.66.0.
- Browser rendering not performed (no browser tool); verified via the Plotly figure spec.

## Record 8: Executive overview UX cleanup, 2026-10-26

### Scope
- Presentation-only Executive page clean-up: module eyebrow on Priority findings; removed "Leadership action queue"; removed duplicate "AI findings" / "Recommended actions" panels; removed dead `finding_card` + `.finding-action` CSS.

### Decisions
- The decision brief is shown once (Priority findings cards, which already carry summary/impact/action). The bottom panels were pure duplication; "AI findings" was also a misleading label versus the closed "no LLM creates/ranks a finding" decision.
- No metric, terminology, window, classification, routing or architecture change.

### Tests
- Updated `test_phase3_experience.py::test_executive_shows_only_existing_findings_as_navigation_cards` (eyebrow present; three removed sections absent). No test asserted the removed panels/helper.

### Validation results (full suite)
- See CLAUDE.md test-count history for the recorded full-suite number (2026-10-26). Python 3.12.10, Streamlit 1.66.0.
- Browser rendering not performed (no browser tool available to Claude).

## Record 9: Error Analysis Assistant validator — causal-connective false positives, 2026-10-26

### Defect (live-surfaced, second of its kind)
- A valid reply was rejected with `forbidden causal claim: due to`. The blocklist matched bare causal connectives ("due to", "because of", "caused by", "resulted from"), which appear in safe, descriptive or cause-disclaiming sentences, so the assistant repeatedly fell back to UNAVAILABLE on otherwise-safe output.

### Fix
- `src/error_assistant.py`: removed the four bare connectives from `FORBIDDEN`; kept the named-conclusion nouns (outage, incident, degradation, infrastructure, network, capacity, quota, root cause, root-cause, provider failure, service failure). POLICY reworded to forbid asserting a named cause rather than banning connective words. No-cause rule still enforced by the conclusion nouns + the mandatory "No cause is established" sentence + restricted-outside-gaps + number-grounding.

### Tests
- `test_forbidden_causal_wording_is_rejected` broadened to three named claims (outage / root cause+network / service failure) still rejected.
- Added `test_bare_causal_connective_in_a_disclaimer_is_not_rejected` (a "due to" disclaimer passes).

### Validation results (full suite)
- 341 passed (full run, 2026-10-26), exit 0 (340 + 1 new regression test). Python 3.12.10, Streamlit 1.66.0.

## Record 10: Internal review modifications (items 1–9), 2026-10-26

### Scope
Nine review items. Presentation: (1) larger Executive module heading, (2) nav order aligned to the card flow, (3) demo banner removed from Executive, (6) Indian lakh/crore counts on headline cards, (9) Solution design / Requirements / Demo & tests hidden from navigation. Visibility: (7) the undated-events and "Scope:" disclosures gated to admins. Decision-support: (4) decommission readiness traffic-light, (5) Model Evaluation Assistant reframed, (8) Error Analysis Assistant made actionable.

### Implemented decisions
- Presentation items 1, 2, 3, 6, 9 applied as described in `docs/WORKING_LOG.md`; no metric, classification, window or routing change. Hidden pages keep their `ROUTES` entries and functions.
- Item 4: a traffic-light (green internal / amber external / red none / grey not-retiring) was added as a **separate** dimension; the Illustrative Decommission Readiness Score and its weights are unchanged.
- Item 5: the assistant now explains why a model is flagged, its position, available options and advisory actions, using evidence it already had plus Risk Reason, Retirement Timing and Replacement Availability. It remains advisory and must not approve/reject or recalculate.
- Item 8: the synthetic/demo telemetry gained a consistent error taxonomy and an error→provider/model breakdown, plus a curated remediation playbook; the assistant gives grounded, actionable guidance on that data and stays evidence-only on real telemetry.

### Accepted feedback (reversals of frozen/closed decisions — approved by the requester)
- **Item 4 — readiness colour:** the closed decision was that readiness is an illustrative score with no traffic-light. A green/amber/red status is now shown. It required a new **illustrative synthetic** `availability` (Internal/External) attribute, which does not exist in any real source; it is labelled as illustrative in the UI and is never presented as a sourced fact.
- **Item 7 — disclosure visibility:** the Telemetry Contract requires undated events be "excluded and disclosed". The two Platform Health disclosures are now shown to admins only (reusing the one existing role gate; no new role, as `src/auth.py` is architecture-locked). This narrows the disclosure for non-admin users; accepted on the requester's instruction. The data-basis expander and the Executive undated-events card note are unchanged.
- **Item 8 — Error Analysis Assistant:** the Phase 5B closed design was evidence-only with no cause and no error→model/provider relationship. The assistant may now name error categories and restate standard remediations **when the evidence provides them**. This is backed by enriching the synthetic/demo data (a real taxonomy + linkage), not by letting the model speculate: the mandatory "No cause is established from the available evidence." sentence, the closed owner list, number-grounding and the causal-term gate are all kept; the causal-term gate now excuses a term only when it is present in the evidence. Real telemetry carries no taxonomy, so there the assistant is unchanged (real-honest).

### Rejected / not done
- No new "developer" role was created for item 7 (auth is architecture-locked); the admin role was reused.
- `fmt_count` was applied to dashboard headline counts only; AI evidence number formatting was left as raw digits so the number-grounding validators keep working.

### Open review items
- Browser review of all nine items: not performed (no browser tool available to Claude).
- Live Gemini runs of both reframed assistants: not performed here; covered by unit tests and validators. First live checks remain pending (as in prior phases).

### Validation results (full suite)
- **341 passed** (full run, 2026-10-26), exit 0. Python 3.12.10, Streamlit 1.66.0. Net count unchanged: +5 new tests, +1 from splitting the demo-banner test, −6 parametrized page cases for the three hidden pages.
- New/changed tests: `test_phase1_metrics.py` (fmt_count), `test_v11_data.py` (readiness status + column set), `test_error_assistant.py` (three demo-path tests), `test_model_assistant.py` (new sections/evidence), `test_demo_mode.py` (banner split), `test_pages.py` (visible-page set).

## Record 11: Usability + scope review (P1–P8, deployment), 2026-10-26

### Scope
Readability and scope review: P1 card prominence, P2 industry-standard metric names (+ removing the Unclassified/Uncategorized events card), P7 Executive "Where you stand" summary, P8 same-family replacement only, P4.1 demo-only (toggle removed), P3 per-page time window, P4.2 Provider→Model→Error-code cascade with per-model codes, and P6 a deployment guide.

### Accepted decisions (reversals of closed decisions, approved by the requester)
- **Metric renames (P2)** including Call success rate and Inactive use cases, which trade some of the project's deliberately cautious wording for executive clarity.
- **Demo-only (P4.1)** supersedes the "Demo Scenario Data scope" closed decision; the Real/Demo toggle is removed. A hidden `nesgen_real_data` session flag keeps the real pipeline testable.
- **Per-page time window (P3)** replaces the single global sidebar window.
- **Same-family-only replacement (P8)**: the cross-family candidate fallback is removed.
- **Error cascade (P4.2)**: per-model error codes so a model never shows a code it lacks; the assistant is scoped to one Provider/Model/Error code.

### Not done / honest notes
- The unclassified-events honesty disclosure is kept (badge, Platform Health "Learn more", Data basis line); only the KPI card was removed.
- Live Gemini and browser checks not performed here (no tools available to Claude); AI surfaces are covered by unit tests and validators.

### Validation results (full suite)
- **333 passed** (full run, 2026-10-26), exit 0. Python 3.12.10, Streamlit 1.66.0. Count moved from 345 as removed Uncategorized-card and Real/Demo-toggle tests were replaced by the new per-page-window, per-model-code and cascade tests.
