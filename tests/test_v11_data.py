import pandas as pd
from src import data, metrics


def test_synthetic_apps_has_100_use_cases_and_contract_columns():
    a=data.synthetic_apps()
    assert len(a)==100
    assert {'use_case_stage','segment','active_users'}.issubset(a.columns)
    assert set(a.segment)=={'B2B','B2C'} and set(a.use_case_stage)<={'Sandbox','Industrialized'}


def test_synthetic_apps_has_exactly_undated_k_rows_without_approval_date():
    # WS-4/UA-09: demo must exercise the "Use cases without approval date" path. The undated rows keep every other
    # attribute (ID, status, stage, segment, active users); only the approval date is missing.
    a=data.synthetic_apps()
    undated=a[a.created_date.isna()]
    assert len(undated)==data.UNDATED_K==5
    assert undated.id.notna().all() and (undated.id.astype(str).str.strip()!='').all()        # IDs retained → still canonical
    assert set(undated.status)<=set(a.status) and set(undated.use_case_stage)<=set(a.use_case_stage)
    assert set(undated.segment)<=set(a.segment)
    assert len(metrics.canonical_use_cases(a)[0])==100                                         # undated rows are still counted as use cases


def test_telemetry_shape_and_consistency():
    t=data.get_telemetry();s=t['stats']
    assert s['success']+s['failed']==s['classified'] and s['classified']+s['unclassified']==s['events']
    assert t['by_model'].calls.sum()==s['classified'] and t['by_model'].failures.sum()==s['failed']
    assert {'model','provider','calls','failures','failure_rate'}.issubset(t['by_model'].columns)
    assert {'error_code','error_message','error_source','occurrences'}.issubset(t['errors'].columns)
    assert (t['by_model'].failures<=t['by_model'].calls).all()


def test_enrich_models_backup_and_readiness():
    m=data.enrich_models(data.synthetic_models())
    assert {'lifecycle_category','suggested_replacement','replacement_risk','has_backup','decommission_readiness',
            'unique_clients','decommission_readiness_status','replacement_availability'}.issubset(m.columns)
    assert m.decommission_readiness.between(0,100).all()
    assert (m.suggested_replacement!=m.name).all()
    assert 'Sandbox' in set(m.lifecycle_category)


def test_decommission_readiness_status_active_amber_red():
    # Traffic-light read conventionally: green = active (not retiring), amber = retiring with a replacement, red = retiring with none.
    amber=data.enrich_models(_set_retiring(_models(),avail='Internal'),today='2026-10-23')
    assert amber.loc[0,'decommission_readiness_status']=='Retiring: replacement available' and amber.loc[0,'has_backup']
    assert (amber.loc[1:,'decommission_readiness_status']=='Active (not retiring)').all()   # the rest are not retiring -> green
    red=_models().head(3)
    red.loc[0,'stage']='Retirement planned'            # retiring
    red.loc[[1,2],'risk']='High'                       # the only other models are unsuitable -> no candidate in the pool
    red=data.enrich_models(red,today='2026-10-23')
    assert red.loc[0,'decommission_readiness_status']=='Retiring: no replacement' and not red.loc[0,'has_backup']


def _set_retiring(m,avail):
    m.loc[0,'stage']='Retirement planned'              # model 0 scheduled for retirement; models 1.. are eligible candidates
    m['availability']=avail
    return m


def _models():
    m = data.synthetic_models(8)
    m['evaluation_score'] = 90
    m['risk'] = 'Low'
    m['lifecycle_status'] = 'Current'
    m['stage'] = 'Industrialized'
    m['migration_required'] = 'No'
    m['retire_date'] = pd.NaT
    m['next_review_date'] = pd.Timestamp('2030-01-01')
    m['model_family'] = 'GPT'   # P8: candidates are same-family only, so the test models must share a family to have one
    return m


def test_candidates_exclude_invalid_models():
    m = _models()
    m.loc[1, 'lifecycle_status'] = 'Retired'                   # retired
    m.loc[2, 'retire_date'] = pd.Timestamp('2027-03-31')      # scheduled for retirement
    m.loc[3, 'risk'] = 'High'                                  # unsuitable
    m.loc[4, 'evaluation_evidence_status'] = 'Action required' # incomplete evidence
    m.loc[5, 'lifecycle_status'] = 'Retirement approved'      # approved retirement
    e = data.enrich_models(m, today='2026-10-23')
    bad = set(e.loc[[1, 2, 3, 4, 5], 'name'])
    assert not (set(e.suggested_replacement.dropna()) & bad)
    assert (e.suggested_replacement.fillna('') != e.name).all()


def test_future_retire_date_is_scheduled_not_retired():
    # Follow-up: a 'Retired' label with a future retire date must read Scheduled, not Retired (no contradiction).
    m = _models().head(2)
    m.loc[0, 'lifecycle_status'] = 'Retired'
    m.loc[0, 'retire_date'] = pd.Timestamp('2026-12-09')              # future vs today below
    e = data.enrich_models(m, today='2026-10-17')
    assert e.loc[0, 'retirement_status'] == 'Scheduled'
    m2 = _models().head(1)
    m2.loc[0, 'lifecycle_status'] = 'Retired'                         # no future date -> genuinely Retired
    assert data.enrich_models(m2, today='2026-10-17').loc[0, 'retirement_status'] == 'Retired'


def test_availability_is_derived_for_models_without_the_field():
    # Workbook models carry no availability; enrich derives an illustrative, deterministic one so readiness is not blank.
    m = _models()
    del m['availability']
    e = data.enrich_models(m, today='2026-10-23')
    assert 'availability' in e and set(e.availability) <= {'Internal', 'External'}
    assert list(e.availability) == list(data.enrich_models(m.copy(), today='2026-10-23').availability)


def test_no_suitable_candidate_is_none_not_weak_pick():
    m = _models().head(2)
    m['risk'] = 'High'
    e = data.enrich_models(m, today='2026-10-23')
    assert e.suggested_replacement.isna().all() and not e.has_backup.any()
    assert (e.replacement_readiness == 'No suitable candidate').all()


def test_status_concepts_are_independent_and_ranked():
    from src.insights import model_attention_rank
    m = _models()
    m.loc[0, 'risk'] = 'High'
    m.loc[1, 'next_review_date'] = pd.Timestamp('2026-01-01')
    m.loc[2, 'migration_required'] = 'Assess'
    e = data.enrich_models(m, today='2026-10-23')
    assert e.loc[1, 'review_status'] == 'Overdue' and e.loc[2, 'retirement_status'] == 'Candidate'
    assert list(model_attention_rank(e).iloc[:4]) == [1, 2, 3, 4]


def test_illustrative_score_weights_sum_to_100():
    assert sum(data.SCORE_WEIGHTS.values()) == 100


def test_low_evaluation_score_is_not_an_exclusion_rule():
    m = _models().head(2)
    m['evaluation_score'] = 40                                  # no numeric threshold may disqualify a candidate
    e = data.enrich_models(m, today='2026-10-23')
    assert e.suggested_replacement.notna().all() and not hasattr(data, 'MIN_CANDIDATE_SCORE')


def test_candidate_rule_falls_back_from_family_to_provider_to_any():
    # Broadened rule (2026-10-26): same family -> same provider -> best available (non-High-risk only).
    m = data.synthetic_models(6)
    m['risk'] = 'Low'; m['lifecycle_status'] = 'Current'; m['stage'] = 'Industrialized'; m['migration_required'] = 'No'
    m['retire_date'] = pd.NaT; m['next_review_date'] = pd.Timestamp('2030-01-01')
    m['model_family'] = [f'F{i}' for i in range(len(m))]        # every model a unique family -> no same-family option
    m['provider'] = 'Azure'                                     # all same provider -> provider tier supplies a candidate
    e = data.enrich_models(m, today='2026-10-23')
    assert e.has_backup.all() and set(e.replacement_basis.dropna()) == {'same provider'}


def test_high_risk_model_gets_no_cross_provider_fallback_candidate():
    m = data.synthetic_models(4)
    m['risk'] = ['High', 'Low', 'Low', 'Low']                   # model 0 is High-risk
    m['lifecycle_status'] = 'Current'; m['stage'] = 'Industrialized'; m['migration_required'] = 'Assess'   # all retiring candidates
    m['retire_date'] = pd.NaT; m['next_review_date'] = pd.Timestamp('2030-01-01')
    m['model_family'] = ['A', 'B', 'C', 'D']                    # all distinct families
    m['provider'] = ['Azure', 'AWS', 'GCP', 'GCP']              # model 0 Azure is alone -> no same-provider either
    e = data.enrich_models(m, today='2026-10-23')
    assert pd.isna(e.loc[0, 'suggested_replacement']) and not e.loc[0, 'has_backup']        # High-risk: no cross fallback -> red
    assert e.loc[1, 'has_backup'] and e.loc[1, 'replacement_basis'] == 'best available model'   # Low-risk: cross fallback allowed


def test_error_reference_table_has_six_columns_with_meanings():
    errs = pd.DataFrame({'error_code': [429, 503], 'error_message': ['Rate limit exceeded', 'Model unavailable'],
                         'error_category': ['Rate limit / Quota', 'Upstream provider error'], 'occurrences': [100, 50]})
    t = data.error_reference_table(errs)
    assert list(t.columns) == ['Error code', 'Message', 'Category', 'Occurrences', 'Meaning', 'How to reduce']
    assert 'rate limit' in t.loc[t['Error code'] == 429, 'Meaning'].iloc[0].lower()
    assert 'deployment quota' in t.loc[t['Error code'] == 429, 'How to reduce'].iloc[0].lower()
