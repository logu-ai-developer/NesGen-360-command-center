import inspect
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
import pandas as pd
import pytest
from src import agent

@pytest.fixture
def sdk(monkeypatch):
    from google import genai
    monkeypatch.setenv('GEMINI_API_KEY','fake-test-only')
    response=SimpleNamespace(text='Answer based on retrieved dashboard data.',function_calls=[],
        usage_metadata=SimpleNamespace(prompt_token_count=10,candidates_token_count=5,total_token_count=15))
    real=genai.Client(api_key='offline-test-only')
    client=MagicMock();client.__enter__.return_value=client
    client.vertexai=False;client._api_client=real._api_client
    client.chats.create.return_value.send_message.return_value=response
    client.chats.create.return_value.get_history.return_value=[]
    monkeypatch.setattr(genai,'Client',MagicMock(return_value=client))
    yield client,response
    real.close()

@pytest.fixture
def model_data(monkeypatch):
    d=pd.DataFrame({'name':['HighRisk','ReviewDue','Migration','Clear'],
      'provider':['Azure','AWS','GCP','Azure'],'stage':['Industrialized']*4,
      'risk':['High','Low','Low','Low'],
      'lifecycle_status':['Current','Review due','Current','Current'],
      'migration_required':['No','No','Assess','No'],
      'next_review_date':['2099-01-01']*4,'owner':['private@example.invalid']*4})
    monkeypatch.setattr(agent,'get_models',lambda:d.copy())
    return d

def test_provider_prefetch_without_sdk_history(sdk):
    text,inp,out=agent.ask('Which provider has the highest consumption?','working-model')
    assert 'Verified local tools: get_executive_summary' in text
    assert (inp,out)==(10,5)
    client,_=sdk
    assert client.chats.create.call_args.kwargs['model']=='working-model'
    sent=client.chats.create.return_value.send_message.call_args.args[0]
    assert 'LOCAL_DASHBOARD_EVIDENCE' in sent and 'provider_consumption' in sent
    assert client.chats.create.return_value.send_message.call_count==1

def test_model_prefetch_returns_names_without_private_owner(sdk,model_data):
    text,_,_=agent.ask('Which models require governance review?','working-model')
    assert 'get_models_requiring_review' in text
    sent=sdk[0].chats.create.return_value.send_message.call_args.args[0]
    assert 'HighRisk' in sent and 'ReviewDue' in sent and 'Migration' in sent
    assert 'private@example' not in sent

def test_review_rule_and_limit(model_data):
    x=agent.get_models_requiring_review(limit=2)
    assert x['candidate_count']==3 and x['returned_count']==2 and x['truncated']
    assert all('reasons' in row for row in x['models'])

def test_real_execution_accepted_without_history(sdk):
    client,response=sdk
    def send(_):
        agent._TOOL_MAP['get_priority_alerts']()
        return response
    client.chats.create.return_value.send_message.side_effect=send
    text,_,_=agent.ask('Summarize priority alerts','working-model')
    assert 'Verified local tools: get_priority_alerts' in text

def test_history_alone_does_not_prove_execution(sdk):
    client,response=sdk
    response.automatic_function_calling_history=[object()]
    text,_,_=agent.ask('Custom unsupported question','working-model')
    assert 'No dashboard-data tool executed' in text

def test_failed_query_not_counted_as_evidence(sdk):
    client,response=sdk
    def send(_):
        agent._TOOL_MAP['query_dashboard']('{"dataset":"bad","metrics":["bad"]}')
        return response
    client.chats.create.return_value.send_message.side_effect=send
    text,_,_=agent.ask('Custom query','working-model')
    assert 'tool was called but failed' in text

def test_metadata_only_not_counted(sdk):
    client,response=sdk
    def send(_):
        agent._TOOL_MAP['list_datasets']()
        return response
    client.chats.create.return_value.send_message.side_effect=send
    text,_,_=agent.ask('Custom question','working-model')
    assert 'No dashboard-data tool executed' in text

def test_empty_model_text_is_distinct(sdk):
    sdk[1].text=None
    text,_,_=agent.ask('Which provider has the highest consumption?','working-model')
    assert 'retrieved but the model returned no answer text' in text

def test_trace_isolation(sdk):
    agent.ask('Which provider has the highest consumption?','working-model')
    assert agent._TRACE.get() is None
    text,_,_=agent.ask('Unrelated custom question','working-model')
    assert 'No dashboard-data tool executed' in text

def test_sdk_tool_signatures_preserved():
    fn=agent._TOOL_MAP['get_models_requiring_review']
    assert list(inspect.signature(fn).parameters)==['provider','limit']
    assert len(agent.TOOLS)==16
    assert {'get_onboarding_trend','get_chargeback_report','get_platform_report','get_decision_brief'}.issubset(agent._TOOL_MAP)
