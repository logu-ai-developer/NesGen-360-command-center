from pathlib import Path
import pytest
from src import request_gate as gate,agent

def test_queue_once_freezes_scope_and_model():
    state={'agent_session':'queue-test','agent_busy':False};scope={'region':'Europe'}
    assert gate.queue_request(state,'Question',scope,'working',100)
    scope['region']='Asia'
    assert not gate.queue_request(state,'Second',{},'other',101)
    assert state['agent_pending']['scope']['region']=='Europe'
    assert state['agent_pending']['prompt']=='Question'

def test_process_gate_rejects_overlap():
    assert gate.acquire('lock-test')
    try:
        assert not gate.acquire('lock-test')
        assert not gate.queue_request({'agent_session':'lock-test'},'q',{},'m',100)
    finally:gate.release('lock-test')
    assert not gate.active('lock-test')

def test_cooldown_rejects_queue():
    assert not gate.queue_request({'agent_session':'cooldown','agent_cooldown_until':200},'q',{},'m',100)

@pytest.mark.parametrize('exc',[ConnectionResetError(10054,'connection reset'),RuntimeError('WinError 10054'),RuntimeError('RemoteProtocolError')])
def test_connection_reset_classified(exc):assert agent.classify_error(exc)=='network'

def test_chained_reset():
    exc=RuntimeError('transport failed');exc.__cause__=ConnectionResetError('peer reset')
    assert agent.classify_error(exc)=='network'

def app():
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    at.sidebar.radio[0].set_value('AI assistant').run()
    return at

def test_audience_and_suggestion_never_call_model(monkeypatch):
    from src import assistant_ui
    calls=[];monkeypatch.setattr(assistant_ui,'ask',lambda *a,**k:calls.append(1))
    at=app();at.selectbox(key='ai_example_audience').set_value('Chargeback / FinOps').run()
    at.selectbox(key='ai_suggested_question').set_value('Show unexplained amounts by provider.').run()
    assert not at.exception and calls==[]

def test_controls_disabled_during_model_call(monkeypatch):
    from src import assistant_ui
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-only')
    at=app();calls=[]
    def ask(*args,**kwargs):
        calls.append(args[0])
        assert at.button[0].disabled
        assert at.selectbox(key='ai_example_audience').disabled
        assert at.selectbox(key='ai_suggested_question').disabled
        assert at.chat_input[0].disabled
        return 'Mock answer',10,5
    monkeypatch.setattr(assistant_ui,'ask',ask)
    next(b for b in at.button if b.label=='Analyze suggested question').click().run()
    assert not at.exception and len(calls)==1
    assert not at.chat_input[0].disabled
    at.selectbox(key='ai_example_audience').set_value('Business Stakeholders').run()
    assert len(calls)==1

def test_chat_submit_once_and_failure_unlocks(monkeypatch):
    from src import assistant_ui
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-only');at=app();calls=[]
    def ask(*a,**k):calls.append(1);raise ConnectionResetError(10054,'reset')
    monkeypatch.setattr(assistant_ui,'ask',ask)
    at.chat_input[0].set_value('Show chargeback').run()
    assert not at.exception and len(calls)==1
    assert not at.chat_input[0].disabled
    assert any('connection was interrupted' in e.value.lower() for e in at.error)
    at.selectbox(key='ai_example_audience').set_value('Business Stakeholders').run()
    assert len(calls)==1
