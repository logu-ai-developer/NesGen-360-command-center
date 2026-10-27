"""Rebuild regressions use isolated databases and explicitly synthetic fixtures."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pandas as pd
import pyarrow as pa
import pytest
from src import data,storage,usage,agent,query_tools


def test_fallbacks_deterministic():
    pd.testing.assert_frame_equal(data.synthetic_apps(),data.synthetic_apps())
    pd.testing.assert_frame_equal(data.synthetic_models(),data.synthetic_models())
    pd.testing.assert_frame_equal(data.synthetic_health(),data.synthetic_health())


def test_missing_allocation_columns_are_safe():
    from src.provider import normalize_allocations
    d=normalize_allocations(pd.DataFrame({'provider':['Azure','Azure;AWS','Unknown']}))
    assert d[['Azure','AWS','GCP']].sum(axis=1).between(.999,1.001).all()
    assert d.loc[1,'Azure']==.5 and d.loc[1,'AWS']==.5


def test_invalid_workbook_returns_complete_fallback(tmp_path,monkeypatch):
    p=tmp_path/'bad.xlsx';p.touch();monkeypatch.setattr(data,'HUB_XLSX',p)
    monkeypatch.setattr(pd,'read_excel',lambda *a,**k:pd.DataFrame({'wrong':[1]}))
    d=data.get_apps()
    assert len(d)==100 and d.attrs['source_mode']=='synthetic fallback'
    assert storage.sources()[0]['mode']=='synthetic fallback'


def test_5000_source_rows_and_missing_optional_fields(tmp_path,monkeypatch):
    p=tmp_path/'hub.xlsx';p.touch();monkeypatch.setattr(data,'HUB_XLSX',p)
    frame=pd.DataFrame({'Application ID':[f'A{i}' for i in range(5000)],'Region':['Europe']*5000,
                        'Expected Daily Users':[10]*5000,'Azure':[50]*5000,'AWS':[30]*5000,'GCP':[20]*5000})
    monkeypatch.setattr(pd,'read_excel',lambda *a,**k:frame)
    d=data.get_apps()
    assert len(d)==5000 and d.attrs['source_mode']=='workbook'
    assert d.monthly_requests.sum()==1500000 and d.environment.eq('Unknown').all()
    assert d.Azure.eq(.5).all()


def test_mixed_model_dates_are_arrow_compatible(tmp_path,monkeypatch):
    p=tmp_path/'models.xlsx';p.touch();monkeypatch.setattr(data,'MODEL_XLSX',p)
    frame=pd.DataFrame({'Model Name':['M1','M2','M3'],'Cloud Provider':['Azure']*3,
        'Retire Date':['2027-01-01','Not announced',None],
        'next_review_date':[pd.Timestamp('2026-11-01'),'N/A','2026-12-01']})
    monkeypatch.setattr(pd,'read_excel',lambda *a,**k:frame)
    d=data.get_models();pa.Table.from_pandas(d,preserve_index=False)
    assert pd.api.types.is_datetime64_any_dtype(d.retire_date)
    assert d.retire_date.isna().sum()==2


def test_registration_persists_and_bootstrap_is_idempotent():
    ident=storage.register_model('New model','Azure','Demo owner','Exploration',80,'Low')
    storage.init();storage.init()
    assert ident in set(data.get_models().id)
    assert len(storage.local_models())==1


def test_empty_data_directory_recreated(tmp_path,monkeypatch):
    db=tmp_path/'replacement'/'nesgen360.db'
    for module in [data,storage,usage]:monkeypatch.setattr(module,'DB',db)
    storage.init();usage.init()
    assert db.exists() and usage.summary()['today']==0


def test_failed_calls_count_against_rpm(monkeypatch):
    monkeypatch.setenv('AGENT_REQUESTS_PER_MINUTE','2')
    a=usage.reserve('test',100);usage.complete(a,0,'failed')
    usage.reserve('test',100)
    with pytest.raises(usage.RateLimitError):usage.reserve('test',100)
    assert usage.summary()['today']==2


def test_token_reservations_block_concurrent_overspend(monkeypatch):
    monkeypatch.setenv('AGENT_TOKENS_PER_MINUTE','150')
    usage.reserve('test',100)
    with pytest.raises(usage.RateLimitError):usage.reserve('test',100)


def test_settings_and_kill_switch_persist():
    storage.set_setting('agent_disabled',True)
    assert storage.get_setting('agent_disabled') is True


def test_scope_applied_to_structured_query(monkeypatch):
    import json
    d=data.synthetic_apps();monkeypatch.setattr(query_tools.dashboard,'get_apps',lambda:d)
    with query_tools.query_session(scope={'region':'Europe'}):
        x=json.loads(query_tools.query_dashboard('{"dataset":"applications","metrics":["application_rows"]}'))
    assert x['rows'][0]['application_rows']==int(d.region.eq('Europe').sum())


def test_two_model_requests_are_both_reserved(monkeypatch):
    from google import genai
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-only')
    real=genai.Client(api_key='offline-test-only')
    client=MagicMock();client.__enter__.return_value=client;client.vertexai=False;client._api_client=real._api_client
    chat=client.chats.create.return_value;chat.get_history.return_value=[]
    u=SimpleNamespace(prompt_token_count=10,candidates_token_count=5,total_token_count=15)
    chat.send_message.side_effect=[SimpleNamespace(function_calls=[SimpleNamespace(name='get_priority_alerts',args={})],usage_metadata=u,text=None),SimpleNamespace(function_calls=[],usage_metadata=u,text='Synthetic alert summary.')]
    monkeypatch.setattr(genai,'Client',MagicMock(return_value=client))
    answer,inp,out=agent.ask('Summarize alerts','preserved-model')
    real.close()
    assert 'Dashboard: Executive overview' in answer and 'get_priority_alerts' not in answer and (inp,out)==(20,10)
    assert usage.summary()['today']==2
    assert client.chats.create.call_args.kwargs['model']=='preserved-model'


def test_scope_and_history_forwarded(monkeypatch):
    from google import genai
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-only')
    real=genai.Client(api_key='offline-test-only');client=MagicMock();client.__enter__.return_value=client;client.vertexai=False;client._api_client=real._api_client
    chat=client.chats.create.return_value;chat.get_history.return_value=[]
    chat.send_message.return_value=SimpleNamespace(function_calls=[],usage_metadata=None,text='No evidence')
    monkeypatch.setattr(genai,'Client',MagicMock(return_value=client))
    agent.ask('Compare','working',history=[{'role':'user','content':'Prior question'}],scope={'region':'Europe'})
    sent=chat.send_message.call_args.args[0]
    assert 'Europe' in sent and 'Prior question' in sent
    real.close()
