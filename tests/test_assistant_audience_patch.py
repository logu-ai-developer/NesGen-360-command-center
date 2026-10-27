"""Offline audience/date/source/loop regressions. All fixtures are synthetic."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import ast,json,zipfile
import pandas as pd
import pytest
from src import agent,assistant_insights as insights

@pytest.fixture
def approvals(monkeypatch):
    d=pd.DataFrame({'id':['A','B','B','F','X'],'region':['Europe']*5,
        'created_date':pd.to_datetime(['2026-10-11','2026-10-20 23:59','2026-10-20','2026-12-02',None],format='mixed')})
    monkeypatch.setattr(insights,'get_apps',lambda:d.copy())
    monkeypatch.setattr(insights,'today_utc',lambda:pd.Timestamp('2026-10-20'))
    return d

def test_ten_day_window_future_warning_and_zero_buckets(approvals):
    x=insights.get_onboarding_trend(10)
    assert x['date_range']=={'start':'2026-10-11','end':'2026-10-20','anchor':'today','inclusive_days':10}
    assert x['future_dated_rows_excluded']==1 and x['invalid_date_rows']==1
    assert x['window_approval_rows']==3 and x['window_unique_applications']==2
    assert len(x['buckets'])==10 and sum(b['approval_rows'] for b in x['buckets'])==3
    assert 'active' not in x

def test_latest_excludes_future_dates(approvals):
    assert insights.get_onboarding_trend(90,anchor='latest')['date_range']['end']=='2026-10-20'

def test_weekly_trend_and_invalid_buckets(approvals):
    x=insights.get_onboarding_trend(90,bucket='week')
    assert x['bucket']=='week' and 12<=len(x['buckets'])<=14
    assert insights.get_onboarding_trend(365,bucket='day')['status']=='error'

@pytest.mark.parametrize('days',[0,-1,4000])
def test_invalid_days(approvals,days):assert insights.get_onboarding_trend(days)['status']=='error'

def test_chargeback_metric_and_scenario_labels():
    x=insights.get_chargeback_report()
    assert x['source']=='Dashboard: Chargeback' and not x['live_mulesoft_reconciliation']
    assert 'NOT requests' in x['metric']
    aws=next(p for p in x['providers'] if p['provider']=='AWS')
    assert aws['stored_variance_percent']==7.4 and aws['review_required']

def test_alerts_do_not_claim_today():
    assert 'not verified' in insights.get_decision_brief()['freshness'].casefold()
    assert 'NOT verified' in insights.get_platform_report()['alert_freshness']

def test_source_explicit_prefetch():
    state={'attempts':0,'success':[],'failed':[],'cache':{},'duplicates':0,'chargeback_only':True}
    token=agent._TRACE.set(state)
    try:
        x=agent._prefetch('Refer Chargeback and answer which provider has the highest consumption?')
        assert x['source']=='Dashboard: Chargeback'
        assert agent._TOOL_MAP['get_executive_summary']()['status']=='error'
        result=agent._TOOL_MAP['query_dashboard']('{"dataset":"applications","metrics":["application_rows"]}')
        assert (json.loads(result) if isinstance(result,str) else result)['status']=='error'
    finally:agent._TRACE.reset(token)

def test_duplicate_tool_result_reused(monkeypatch):
    calls=[]
    def test_data():
        calls.append(1);return {'source':'test','value':10}
    fn=agent._tracked(test_data);state={'attempts':0,'success':[],'failed':[],'cache':{},'duplicates':0}
    token=agent._TRACE.set(state)
    try:
        assert fn()==fn();assert len(calls)==1 and state['duplicates']==1
    finally:agent._TRACE.reset(token)

def test_one_sources_footer_cleaning():
    assert agent._clean_answer('Finding\n\n**Sources:** wrong\nExtra')=='Finding'

@pytest.fixture
def fake_sdk(monkeypatch):
    from google import genai
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-only')
    real=genai.Client(api_key='offline-test-only');client=MagicMock();client.__enter__.return_value=client
    client.vertexai=False;client._api_client=real._api_client
    chat=client.chats.create.return_value;chat.get_history.return_value=[]
    monkeypatch.setattr(genai,'Client',MagicMock(return_value=client))
    yield client,chat
    real.close()

def response(text='Evidence answer.',calls=None):
    return SimpleNamespace(text=text,function_calls=calls or [],usage_metadata=SimpleNamespace(prompt_token_count=10,candidates_token_count=5,total_token_count=15))

def test_onboarding_prefetch_finishes_in_one_request(fake_sdk,approvals):
    client,chat=fake_sdk;chat.send_message.return_value=response()
    text,inp,out=agent.ask('What was the onboarding trend in the last 10 days?','unchanged-model')
    assert 'Dashboard: User adoption' in text and 'get_onboarding_trend' not in text and (inp,out)==(10,5)
    assert chat.send_message.call_count==1
    assert client.chats.create.call_args.kwargs['model']=='unchanged-model'
    assert 'future_dated_rows_excluded' in chat.send_message.call_args.args[0]

def test_final_turn_disables_tools(fake_sdk):
    _,chat=fake_sdk
    chat.send_message.side_effect=[response(None,[SimpleNamespace(name='get_priority_alerts',args={})]),response('Summary\nSources: invented')]
    text,_,_=agent.ask('Summarize priority alerts','working',max_rounds=1)
    assert chat.send_message.call_count==2
    assert chat.send_message.call_args.kwargs['config'].tools==[]
    assert 'invented' not in text and text.count('Sources retrieved:')==1

def test_evidence_returned_when_final_model_still_calls_tool(fake_sdk):
    _,chat=fake_sdk
    call=SimpleNamespace(name='get_priority_alerts',args={})
    chat.send_message.side_effect=[response(None,[call]),response(None,[call])]
    text,_,_=agent.ask('Summarize priority alerts','working',max_rounds=1)
    assert 'Retrieved evidence' in text and 'tool-round budget reached' not in text

def test_non_assistant_routes_unchanged():
    import zipfile
    # AST structural comparison against the delivered baseline when available.
    baseline=Path('/mnt/data/nesgen360-v01-rebuilt.zip')
    if not baseline.exists():return
    with zipfile.ZipFile(baseline) as z:old=ast.parse(z.read('nesgen-360-final/app.py').decode())
    new=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text())
    oldf={n.name:ast.dump(n,include_attributes=False) for n in old.body if isinstance(n,ast.FunctionDef)}
    newf={n.name:ast.dump(n,include_attributes=False) for n in new.body if isinstance(n,ast.FunctionDef)}
    assert all(newf[k]==v for k,v in oldf.items() if k not in ('assistant','administration'))
    admin=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='administration')
    assert ast.unparse(admin.body[0])=='require_admin()'
    assert ast.unparse(admin.body[1])=='user_management()'

def test_ai_page_empty_history_and_audience_panel():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    at.sidebar.radio[0].set_value('AI assistant').run()
    assert not at.exception and not at.error
    assert at.selectbox(key='ai_example_audience').value=='Platform Team'
    at.selectbox(key='ai_example_audience').set_value('Regional Product Owners & Managers').run()
    assert not at.exception
    # The audience's examples are now clickable buttons; switching audience swaps them in.
    assert any('last 10 days' in b.label for b in at.button)
