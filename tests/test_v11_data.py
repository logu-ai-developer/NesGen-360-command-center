import pandas as pd
from src import data


def test_synthetic_apps_has_100_use_cases_and_contract_columns():
    a=data.synthetic_apps()
    assert len(a)==100
    assert {'use_case_stage','segment','active_users'}.issubset(a.columns)
    assert set(a.segment)=={'B2B','B2C'} and set(a.use_case_stage)<={'Sandbox','Industrialized'}


def test_telemetry_shape_and_consistency():
    t=data.get_telemetry();s=t['stats']
    assert s['success']+s['failed']==s['classified'] and s['classified']+s['unclassified']==s['events']
    assert t['by_model'].calls.sum()==s['classified'] and t['by_model'].failures.sum()==s['failed']
    assert {'model','provider','calls','failures','failure_rate'}.issubset(t['by_model'].columns)
    assert {'error_code','error_message','error_source','occurrences'}.issubset(t['errors'].columns)
    assert (t['by_model'].failures<=t['by_model'].calls).all()


def test_enrich_models_backup_and_readiness():
    m=data.enrich_models(data.synthetic_models())
    assert {'lifecycle_category','suggested_replacement','replacement_risk','has_backup','decommission_readiness','unique_clients'}.issubset(m.columns)
    assert m.decommission_readiness.between(0,100).all()
    assert (m.suggested_replacement!=m.name).all()
    assert 'Sandbox' in set(m.lifecycle_category)


def _models():
    m = data.synthetic_models(8)
    m['evaluation_score'] = 90
    m['risk'] = 'Low'
    m['lifecycle_status'] = 'Current'
    m['stage'] = 'Industrialized'
    m['migration_required'] = 'No'
    m['retire_date'] = pd.NaT
    m['next_review_date'] = pd.Timestamp('2030-01-01')
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
