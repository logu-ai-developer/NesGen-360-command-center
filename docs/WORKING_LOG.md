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


## 2026-10-23 Phase 5A: Platform Health UX refinement (PH-04, 05, 06, 07, 08, 10, 12, 13)

Presentation only. No metric, KPI contract, telemetry classification, window logic, synthetic-generation logic, AI, routing or architecture change.

- **PH-04 scope consistency.** Added a scope caption and per-group/per-card notes: KPI cards are telemetry-wide for the time window and not affected by the Environment filter; charts follow the time window; correlated alerts are a fixed snapshot. (Corrected in 5B-A: the Environment filter narrows charts only on synthetic/demo data, not real data.)
- **PH-05 Volume group.** New section grouping Total events (elevated to its own card), Total classified calls (with "% of events classified") and Unclassified events.
- **PH-06 Outcomes group.** Successful / Failed classified calls and Classified-call success rate together; no latency in this section. The daily success-rate chart was later replaced by the three-line Daily Classified Call Outcomes chart (Total / Successful / Failed), same window and filtering, KPIs unchanged.
- **PH-07 Performance group.** "Event-level P95 latency" (renamed from "P95 latency (true)"), daily-trend P95 and a new Peak daily P95 card. Explainer says to use the event-level P95 for SLA statements, never the daily values. KPI_INFO entries added for `total_events` and `peak_daily_p95`; `p95_true` caveat reworded. No formula change.
- **PH-08 Failure analysis.** Renamed from "Investigation areas"; added a Focus-provider selector that filters failed-calls-by-model (model rows carry their provider). A caption documents the limitation: errors are not linked to a model or provider in the telemetry, so a true model → provider → error drill-down is not available.
- **PH-10 Illustrative labels.** Correlated alerts expander and the demo banner labelled "Illustrative synthetic scenario".
- **PH-12 Supporting evidence.** Expander renamed "Evidence tables (errors, models, providers)" → "View supporting evidence"; contents unchanged.
- **PH-13 Scenario clarity.** Synthetic error "Internal server error" re-paired from code 403 to 500 in `src/data.py`; no other scenario-generation change.

Section order on the page: Volume, Outcomes, Performance, Failure analysis, Supporting evidence.

Tests: updated `tests/test_phase3_experience.py`, `tests/test_ux_simplification.py`, `tests/test_demo_mode.py` for the new section names, the "Event-level P95 latency" label and the "View supporting evidence" title; added checks for group membership, section order, scope/scenario labels and the Daily Classified Call Outcomes chart. Metric-correctness tests preserved. Full suite: 312 passed (full run, 2026-10-23).


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

## 2026-10-25 WS-4: Synthetic Adoption Boundary Coverage (UA-09 demo visibility)

Resolved the one residual gap from the Phase 6A audit: the "Use cases without approval date" path (logic, windowing, reconciliation and fixture tests already existed) was never exercised by demo-visible synthetic data, so the card always read 0.

**Approach: Option C (approved).** In `_synthetic_approval_dates` (`src/data.py`), after the dates are fully generated, convert `UNDATED_K=5` of the rows already older than every approval window (offset ≥ 181) to `NaT`. The RNG stream, draw sizes (older=20, spike_a=22, spike_b=14, rest=44) and the shuffle are untouched, so no window count or distribution moves; only out-of-window older-dated rows lose their date. The undated rows keep their ID, status, stage, segment and active-user values, so they remain canonical use cases.

**Invariants verified unchanged:** canonical use cases == 100; Newly approved 30/90/180-day == 26/31/80; status/stage/segment distributions; `synthetic_apps()` determinism (`assert_frame_equal(apps(),apps())`).

**Expected, documented moves (not invariants):**
- older *dated* rows (offset ≥ 181): 20 → 15.
- undated rows: 0 → 5; "Use cases without approval date" card 0 → 5 in demo (now amber via the existing `tone='warn'`).
- "Previous period approvals" for the 180-day window: 20 → 15 (its previous period *is* the older bucket the undated rows were drawn from). The 30/90-day previous periods (3, 49) are unchanged.

**Tests.** Modified `tests/test_phase2_time.py:117` (older-dated 20→15, plus an explicit `isna().sum()==UNDATED_K`) and the 180-day previous-period assertion (20→15, with a comment). Added `tests/test_v11_data.py::test_synthetic_apps_has_exactly_undated_k_rows_without_approval_date` and `tests/test_phase2_time.py::test_demo_adoption_exposes_the_undated_use_case_path`. No existing exact-count validation was removed or weakened; the 26/31/80 and ==100 assertions still run and pass as the regression guardrails.

## 2026-10-25 Phase 6A WS-1: UA-05 terminology alignment

Closed the pending-alignment item: the canonical count label now matches the Metric Contract name "Use cases in portfolio" (was "Use cases onboarded"). Presentation only — no metric, logic, calculation or time-window change.

Changed (`app.py`): KPI label "Use cases onboarded" → "Use cases in portfolio"; header sentence "how many use cases are onboarded" → "in the portfolio"; regional chart title "Regional use cases: onboarded vs Active-status" → "in portfolio vs Active-status" and its series name "Onboarded" → "In portfolio". `src/insights.py`: KPI_INFO['use_cases'] definition "Canonical use cases onboarded to the platform." → "Canonical use cases in the platform portfolio.". The page/nav title "User onboarding and adoption" is unchanged (it names the onboarding process, not the count).

Tests updated (intended label change): `test_phase1_metrics.py:359`, `test_phase3_experience.py:129`, and the WS-4 demo-adoption test in `test_phase2_time.py` (asserts the card by its new name). No new tests. Full suite: 337 passed (full run, 2026-10-25), unchanged count.

## 2026-10-25 Phase 6A WS-2: AI-04 assistant governance parity

Gap found: `model_assistant.analyze` validated only the reply shape (`parse_sections`), with no post-hoc number check, while `error_assistant.validate` already rejects invented numbers. So AI-04 ("no invented numbers/counts/scores") was enforced for the Error Analysis Assistant but only prompt-requested for the Model Evaluation Assistant.

Smallest parity change (`src/model_assistant.py`): added `import re`, a `_numbers` helper and `validate_grounding(sections, evidence)` that rejects any number in the reply not present in the evidence JSON; `analyze` now calls it after `parse_sections`. Mirrors the Error Analysis Assistant pattern. Non-numeric claims stay governed by the existing POLICY. Unchanged: Analyze-button workflow, evidence-first flow, advisory boundary, Gemini integration, quota controls, and the UNAVAILABLE fallback (a rejection raises ValueError, which the existing app.py try/except turns into the fallback).

Not ported (domain-specific to error analysis, not AI-04): the causal-term blocklist, the restricted-outside-gaps rule and the closed owner list.

Tests added (`tests/test_model_assistant.py`): `test_validate_grounding_rejects_invented_numbers_but_allows_evidence_numbers` (unit: no-number passes, evidence number passes, invented number rejected) and `test_analyze_rejects_invented_number_and_falls_back` (invented number → UNAVAILABLE, evidence still visible). Full suite: 339 passed (337 + 2).

## 2026-10-25 Phase 6A WS-3: UA-16 accessibility beyond colour

Made the two adoption charts legible without relying on colour alone. No metric, data or stage-semantics change.

- Segment chart "Segment: B2B vs B2C by stage" (`app.py:347`): added on-bar value labels (`text='use_cases'`, `textposition='outside'`) and `pattern_shape='segment'` with `pattern_shape_map={'B2B':'','B2C':'/'}`, so B2B/B2C differ by texture as well as the approved colours (B2B `#1768ff`, B2C `#f2a93b`). Colour map and the B2B-blue/B2C-orange mapping preserved; stage stays the axis, never a colour.
- Regional chart "Regional use cases: in portfolio vs Active-status" (`app.py:349`): added on-bar value labels to both series (`text=`, `textposition='outside'`). It already had a legend distinguishing the two series.

Chart structure, colours and metrics are otherwise unchanged. Test added: `tests/test_phase3_experience.py::test_adoption_charts_are_not_colour_only` (segment chart carries a pattern shape and value labels; regional chart carries value labels). Full suite: 340 passed (339 + 1).

Browser rendering not performed (no browser tool available to Claude); verification is via the Plotly figure spec.

## 2026-10-26 Executive overview UX cleanup (Priority-finding module headings, de-duplication)

Presentation only; no metric, terminology, window, classification, routing or architecture change. `build_decision_brief` and all finding rules are untouched.

- Priority findings now carry a module eyebrow (`.finding-module`) naming the page their evidence lives on (Platform health / Model lifecycle / User adoption / Chargeback), matching the "Open <page> →" button. `app.py` (finding card) + new CSS in `src/components.py`.
- Removed the "Leadership action queue" panel (a fixed synthetic-alerts dump) from the Executive page.
- De-duplication: removed the "AI findings" and "Recommended actions" panels, which re-rendered the same brief already shown as Priority findings cards (which carry summary/impact/action since Phase 4). This also retires the misleading "AI findings" label (the project's closed decision is that no LLM creates or ranks a finding). The Executive spine is now Priority findings → Key metrics → Usage/reliability trend + Provider consumption.
- Removed the now-dead `finding_card` helper (its only callers were the two removed panels) and its unused `.finding-action` CSS. `SEVERITY_COLORS`/`SEVERITY_ICONS` and the other `.finding-*` styles stay (used by the Priority cards).

Tests: added assertions to `test_phase3_experience.py::test_executive_shows_only_existing_findings_as_navigation_cards` (module eyebrow present; "Leadership action queue", "AI findings", "Recommended actions" absent). No test referenced the removed panels or `finding_card`. Full suite: see Validation record.

## 2026-10-26 Fix: Error Analysis Assistant validator false-positives on causal connectives

Second live-surfaced false rejection (after the "Root-cause evidence" label fix): a valid reply was rejected with `forbidden causal claim: due to`. The hard blocklist matched bare causal connectives ("due to", "because of", "caused by", "resulted from"), which models use in safe, descriptive or cause-*disclaiming* sentences ("this is not due to any confirmed outage"), so the assistant kept falling back to "AI analysis is currently unavailable." on otherwise-safe output.

Fix (`src/error_assistant.py`): removed the four bare connectives from `FORBIDDEN`; kept the named-conclusion nouns (outage, incident, degradation, infrastructure, network, capacity, quota, root cause, root-cause, provider failure, service failure). Aligned the POLICY wording to forbid *asserting* a named cause rather than banning the word "because"/"due to". The no-cause rule is still enforced by: the conclusion nouns, the mandatory "No cause is established from the available evidence." sentence, the restricted-outside-gaps rule, and number-grounding.

Tests (`tests/test_error_assistant.py`): `test_forbidden_causal_wording_is_rejected` now checks three named claims (outage / root cause + network / service failure) still fail; added `test_bare_causal_connective_in_a_disclaimer_is_not_rejected` (a "due to" disclaimer passes). Full suite: see validation record.

## 2026-10-26 Internal review modifications (items 1–9)

A nine-item internal review. Items 1–3, 6, 9 are presentation; 7 gates disclosures; 4, 5, 8 are approved changes to frozen/closed decisions (recorded as accepted reversals — see `docs/VALIDATION_RECORD.md` Record 10). Decisions were confirmed with the requester before implementation.

1. **Larger module heading on Executive finding cards.** `.finding-module` font-size `.7rem → .85rem` (`src/components.py`). The destination-page eyebrow now reads as a heading above the finding title.
2. **Navigation order aligned with the card flow.** `PAGES` reordered to `Executive overview, Platform health, Model lifecycle, User adoption, Chargeback, AI assistant, Administration` (`app.py`). Cards stay severity-sorted; routing, labels and `FINDING_TARGETS` unchanged.
3. **Demo banner removed from the Executive page.** The `demo_banner()` call is dropped from `executive()`; it still marks Platform Health (`app.py`). `test_demo_mode.py` now asserts the banner on Platform Health only and absent on Executive.
4. **Decommission readiness traffic-light.** New illustrative synthetic `availability` (Internal/External) on models (`synthetic_models`); `enrich_models` derives `replacement_availability` (the suggested candidate's availability) and `decommission_readiness_status`: green = retiring + internally available replacement, amber = retiring + external only, red = retiring + none, grey = not retiring. The 0–100 illustrative score is unchanged (status is a separate dimension). Display: readiness bar recoloured by status with a legend, a "Decommission" chip in the decision record, new inventory columns, and a note in the scoring expander (`app.py`, `src/insights.py`: `READINESS_STATUS_COLORS/BADGES`).
5. **Model Evaluation Assistant reframed.** Sections now Why Flagged / Current Position / Available Options / Recommended Actions. Evidence gains Risk Reason, Retirement Timing and Replacement Availability (`src/model_assistant.py`). Stays advisory (still must not approve/reject or recalculate); number-grounding unchanged.
6. **Readable Indian-notation counts.** New `fmt_count` in `src/metrics.py` (`2,000,000 → 20L`, `10,000,000 → 1Cr`; grouped digits below one lakh). Applied to the headline count cards on Executive (Unclassified events) and Platform Health (Total events, Total classified calls, Unclassified events, Successful/Failed classified calls). Latency, percentages and currency unchanged. AI evidence numbers are deliberately left as raw digits so number-grounding validators are unaffected.
7. **Disclosures gated to admins.** The undated-events caption and the long "Scope:" caption on Platform Health render only when `role=='admin'` (`app.py`). No new role (auth is architecture-locked); tests run as admin. Recorded as an accepted narrowing of the Telemetry Contract disclosure for non-admins.
8. **Error Analysis Assistant made actionable (demo-rich, real-honest).** Synthetic/demo telemetry now carries a consistent error taxonomy (`ERROR_CATALOG`: code → message → category → source) and an `error_breakdown` (category × provider × model) in `src/data.py`; `get_telemetry` returns `error_breakdown` (None on real parquet). The assistant (`src/error_assistant.py`) surfaces top error categories in focus, where the leading one concentrates, and standard remediations to check from a curated `PLAYBOOK` (owner from the closed list). POLICY updated to allow naming evidence-provided categories and restating playbook actions; the mandatory "No cause is established from the available evidence." sentence is kept, and the FORBIDDEN causal-term gate now excuses a term only when it appears in the evidence (same principle as number-grounding). `investigation_steps` relabelled "Recommended Actions". On real telemetry (no breakdown) the assistant stays evidence-only with categories "Not available".

**Tests.** Added `test_fmt_count_indian_abbreviation` (`test_phase1_metrics.py`), `test_decommission_readiness_status_green_amber_red_grey` (`test_v11_data.py`), and three demo-path error-assistant tests (`test_error_assistant.py`); updated `test_demo_mode.py`, `test_pages.py`, `test_model_assistant.py`, `test_v11_data.py` for the intended changes. Full suite: **341 passed** (full run, 2026-10-26), exit 0. Python 3.12.10, Streamlit 1.66.0. Browser rendering and live Gemini not performed (no browser tool available to Claude); the assistants are covered by unit tests, validators and figure/evidence specs.

### Live-review follow-ups (same day)

After a live walkthrough (screenshots on Real Data):
1. **Module heading more prominent** (item 1): `.finding-module` enlarged to 1rem with an underline accent so it clearly reads as the heading (`src/components.py`).
2. **Disclosures relocated** (item 2/7): the undated-events and "Scope:" captions moved inside the collapsed "Data basis" expander on Platform Health and the admin-only gate removed, so the main view is uncluttered and the disclosure stays visible to everyone (`app.py`).
3. **Rendering bug fixed** (item 3): both assistants' `parse_sections` now coerce a section returned as a JSON array into plain text, so "Recommended Actions" no longer renders as `['...', '...']`. Added a regression test. The actionable error categories/playbook remain demo-only by design (real telemetry error code/message fields are inconsistent, so categorising real data would mislabel — demo-rich, real-honest stands).
4. **Model differentiators added** (item 4/5): `enrich_models` now captures the candidate's `replacement_score`; the Model Evaluation Assistant evidence gains Evaluation Score, Unique API Clients and the candidate's score/risk, and the POLICY asks it to name the concrete differentiator. These fields exist on real workbook data, so they show without Demo mode.

Targeted tests: 154 passed, exit 0. Full suite after this set: 342 passed, exit 0.

### AI value re-scope + model data fixes (same day)

The reviewer observed that both assistants were only re-skinning the pre-computed evidence ("words apart slightly"). Agreed: with everything pre-computed and a strict "restate only" policy, the LLM had nothing to add.

- **Both assistants re-scoped from restate → reason & prioritise** (approved). POLICY rewritten in `src/model_assistant.py` and `src/error_assistant.py`: the Error Analysis Assistant must prioritise error categories by share × concentration × trend, say which to tackle first and put the overall rate/trend in context; the Model Evaluation Assistant must weigh the candidate-vs-current trade-off (score gain vs cross-provider migration, risk, internal/external, time before retirement, adoption as blast radius) and say what to do first. Guardrails unchanged: every number must come from the evidence (number-grounding), no invented facts, the Error Assistant still keeps the mandatory "No cause is established…" sentence, the causal-term gate and closed owner list, and neither assistant approves/rejects or establishes a cause — the human still decides. Section keys and the test token contracts are unchanged.
- **Availability now works on the real model inventory.** `enrich_models` derives an illustrative, deterministic `availability` (Internal/External, stable per model name) when the column is absent, so workbook-loaded models get a value instead of N/A. This makes the green/amber/red decommission readiness traffic-light and the assistant's "Replacement Availability" meaningful on real data. Still labelled illustrative synthetic — never a sourced fact. (Reason it was blank before: the Demo toggle only swaps Executive + Platform Health, never Model Lifecycle, which always reads the real model workbook.)
- **Retired-vs-Scheduled fixed.** `retirement_status` now treats a model with a FUTURE retire date as Scheduled, never Retired, even if its lifecycle_status label says "Retired" — removing the "Retired but retires in 53 days" contradiction.

Tests added: `test_future_retire_date_is_scheduled_not_retired`, `test_availability_is_derived_for_models_without_the_field` (`test_v11_data.py`). Targeted: 83 passed, exit 0. Full suite: 344 passed, exit 0.

### Cross-domain synthesis (option C) — the real AI value-add

The reviewer showed that even the "reason & prioritise" output was still a restatement, because the deterministic evidence already contains the ranked categories, the "leading" concentration, the recommended actions and the owner — the table does the AI's job. Agreed. The fix is structural: give the two bounded assistants FACTS from OTHER domains that no single page pre-joins, and let the LLM do the join + prioritisation. Approved scope: provider-level (reliable) + best-effort model-level (disclosed when names don't align); the Dashboard Agent already synthesises across domains via its tools and is left unchanged (architecture-locked).

- **New `src/cross_domain.py`** (grounded facts only, never a verdict): `normalize_provider` (telemetry 'Azure OpenAI' → 'Azure'), `provider_context` (a provider's chargeback variance + high-risk/review-due governance counts), `model_governance_match` (a telemetry model's governance standing, or None), `model_telemetry_footprint` (a governance model's telemetry failure load, or None), and the two assistant-facing builders `error_context` / `model_context`.
- **Error Analysis Assistant** evidence now adds, for the leading failing provider/model: the provider's cost + governance context, the leading model's governance match (or "not matched to the governance inventory"), and its adoption (unique clients). POLICY tells it to judge whether the priority is primarily a reliability, cost or governance concern and how wide the impact is.
- **Model Evaluation Assistant** evidence now adds the model's operational footprint from telemetry (failure load, or "No telemetry match for this model name") and its provider's cost + governance context. POLICY tells it to weigh keep-vs-retire against real-world impact. These work on the real model workbook (model names often align with telemetry there).
- Guardrails unchanged: every new field is a real number from a real adapter; the LLM only joins and weighs; number-grounding, no-cause, closed owner list and the advisory boundary all stand. The honest ceiling: provider joins always work; model-to-model is disclosed as "not matched" when telemetry and governance names differ (common in demo, where governance uses synthetic workbook names).

Tests added: `tests/test_cross_domain.py` (5) and a demo cross-domain assertion in `test_error_assistant.py`; `test_model_assistant.py` evidence labels extended. Targeted: 76 passed, exit 0. Full suite: 349 passed, exit 0.

### Error Analysis Assistant rebuilt: analyse the error codes (major reversal, approved)

After several rounds, the reviewer's point stood: on a complete, pre-computed dashboard, an LLM forbidden from using any knowledge can only paraphrase the evidence table — every fact it could cite is already a row. The only way to get real "why does this error happen / how do we reduce it / what can the user do" analysis is to let the model use its **general knowledge of standard error codes**. Approved (reverses the Phase 5B evidence-only / no-cause stance for this assistant only).

- **`src/error_assistant.py` rebuilt.** New sections: Observed Pattern / **Likely Causes** / **How to Reduce** / **What You Can Do** / Owner Category. New POLICY: the model MAY explain what each observed standard error code (429, 503, 500, 400/422, 401/403, 408/504, …) generally means, why it typically happens, and standard mitigations — anchored on the error CODE (messages are known-inconsistent), framed as general guidance to verify, not a confirmed root cause for this system.
- **Guardrails kept, re-aimed:** number-grounding still rejects fabricated DATA figures (now only 4+ significant-digit numbers, so counts/percentages stay honest while small advice numbers like "retry 3 times / 2-second backoff" are allowed); the closed owner list stays; a required verbatim disclaimer sentence ("These are general explanations … not a confirmed root cause for this environment.") must appear in Likely Causes; "Not available" fields (environment, ownership) must still be acknowledged. The old causal-term blocklist, the no-cause sentence and the restricted-outside-gaps rule were removed (they were exactly what blocked the analysis). `ADVISORY` now reads "AI guidance uses general knowledge of standard error codes and is advisory; verify against your system."
- Works on **real** telemetry (it analyses whatever error codes are actually present; no synthetic taxonomy needed). The demo taxonomy/playbook/cross-domain context remain as extra grounding.
- The Model Evaluation Assistant was left unchanged this round (the reviewer scoped the change to the Error assistant).

Tests: `tests/test_error_assistant.py` rewritten for the new design (code-explanation allowed, disclaimer required, large-count grounding, owner list, parse/interaction/fallbacks preserved). Targeted: 131 passed, exit 0. Full suite: see validation record.

## 2026-10-26 Usability + scope review (P1–P8, deployment)

A review focused on readability, scope and the error flow. Decisions confirmed up front.

- **P1 Card prominence.** `.kpi-label` enlarged (1.06rem, weight 700, dark) and `.kpi-value` eased to 2.0rem so the card topic reads as prominently as the number (`src/components.py`).
- **P7 Executive summary.** A plain-language "Where you stand" box under the Executive header, built deterministically from the brief (priority count by severity, call success rate, the first action). New `.exec-summary` style.
- **P2 Industry-standard names.** Renamed: Illustrative Decommission Readiness Score → **Retirement Readiness**; Event-level P95 latency → **P95 response time**; Active-status use cases → **Active use cases**; Classified-call success rate → **Call success rate**; Dormant-status use cases → **Inactive use cases**. (Unclassified events was dropped entirely, below.) Labels, `KPI_INFO`, chart/trace titles, the decision-brief finding, and ~25 test assertions updated.
- **Drop the Unclassified/Uncategorized events card.** Removed from Executive (the Key metrics row is now a single 5-card row) and from Platform Health Volume (now 2 cards). The honesty disclosures (the "unclassified telemetry present" badge, the Platform Health "Learn more" expander, and the undated-events line in Data basis) are kept.
- **P8 Same-family replacement only.** `enrich_models` now suggests only a same-`model_family` candidate (any provider), else "No suitable candidate identified"; the cross-family fallback is removed. Caption updated.
- **P4.1 Demo-only.** The Real/Demo toggle is removed from the UI; the POC runs on the deterministic synthetic scenario telemetry (lifecycle telemetry and Administration's health probe also set to demo). A hidden session flag `nesgen_real_data` lets the metric-correctness tests still exercise the real pipeline.
- **P3 Per-page time window.** The global sidebar window is replaced by an independent per-page control (`page_window(key)` → `st.radio` keyed `tw_<page>`) on Executive, Platform Health, Model Lifecycle and User Adoption, so each page holds its own window. `window_for(*series, key=...)`; Chargeback stays a snapshot. Test render helpers updated to drive the per-page control.
- **P4.2 Provider → Model → Error code cascade.** The synthetic telemetry now gives each model a deterministic SUBSET of error codes (a model never shows a code it does not have), and `error_breakdown` carries the code/message/category per provider+model; the window-wide `errors` table is derived from it. The Error Analysis Assistant's focus is now a required Provider → Model → Error code cascade, and the evidence is scoped to that one model's occurrences of that one code — fixing the bug where a window-wide top-3 attributed a 500 to a model that had none. The obsolete category/playbook/cross-domain evidence blocks were removed from the assistant.
- **P6 Deployment.** New `docs/DEPLOYMENT.md`: how to host the app for the team (VM / Azure App Service / AWS, the Docker image, or Streamlit Community Cloud), secrets (`GEMINI_API_KEY`), DB/data persistence, first-admin bootstrap, and that the POC runs on synthetic scenario data.

Tests updated across `test_phase1_metrics`, `test_phase2_time`, `test_phase3_experience`, `test_demo_mode` (rewritten for demo-only + per-page window), `test_executive_notes`, `test_v11_data`, and `test_error_assistant` (rewritten for the code cascade). Targeted batches all green; full suite: see validation record.
