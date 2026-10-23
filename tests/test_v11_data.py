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
