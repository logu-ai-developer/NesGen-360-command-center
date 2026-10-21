"""AI page only. Other V0 routes are unchanged."""
import os,time,uuid,logging
from src.request_gate import queue_request,acquire,release,active
import streamlit as st
from src.agent import ask,classify_error
from src.config import setting
from src.storage import get_setting
from src.usage import summary,begin,finish
from src.components import header

EXAMPLES={
 'Platform Team':[
  'What requires attention today in Platform health?',
  'Which models require governance review?',
  'Show platform health summary.',
  'Using New Relic, compare event counts and P95 latency by provider for the latest available seven days.'],
 'Regional Product Owners & Managers':[
  'What was the onboarding trend in the last 10 days?',
  'What was the onboarding trend in the last 90 days?',
  'What was the onboarding trend in the latest available 90 days?',
  'Show weekly onboarding approvals for Europe over the last 90 days.',
  'Count applications by region and recertification status.'],
 'Business Stakeholders':[
  'What requires action today?',
  'Which provider has the highest consumption?',
  'Summarize the top operational, governance and reconciliation issues requiring a decision.'],
 'Chargeback / FinOps':[
  'Using Chargeback, compare provider invoices and attributed usage.',
  'Which providers exceed the configured reconciliation threshold?',
  'Show unexplained amounts by provider.',
  'Is this reconciliation based on live MuleSoft records or a synthetic scenario?']}


def render_assistant(scope):
    model=str(setting('GEMINI_MODEL'))
    header('AI assistant','Decision support',f'Ask {model}, grounded in approved local dashboard evidence.')
    st.info('Read-only dashboard tools. No web access, arbitrary SQL, record changes or paid-provider fallback.')
    defaults={'agent_session':str(uuid.uuid4()),'agent_messages':[],'agent_cooldown_until':0,
              'agent_busy':False,'agent_pending':None}
    for key,value in defaults.items():
        if key not in st.session_state:st.session_state[key]=value
    ss=st.session_state
    # Recover from a cancelled rerun only after the old execution released its gate.
    if ss.agent_busy and not ss.agent_pending and not active(ss.agent_session):ss.agent_busy=False
    busy=ss.agent_busy or active(ss.agent_session)
    def submit_chat():queue_request(ss,ss.get('ai_chat_prompt',''),scope,model,time.time())
    def submit_suggestion():queue_request(ss,ss.get('ai_suggested_question',''),scope,model,time.time())
    col1,col2=st.columns([4,1])
    with col2:
        with st.expander('💡 Example Questions',expanded=True):
            audience=st.selectbox('Audience',list(EXAMPLES),key='ai_example_audience',disabled=busy)
            for question in EXAMPLES[audience]:st.markdown('• '+question)
            st.caption('Changing the audience only changes examples. It never submits a model request. “Last N days” ends today UTC.')
        with st.expander('Limits explained'):
            st.caption('Tool rounds apply to one question. Three rounds allow up to four model requests. RPM/RPD count each model request.')
    with col1:
        for m in ss.agent_messages:
            with st.chat_message(m['role']):
                if m.get('error'):st.error(m['content'])
                else:st.markdown(m['content'])
                if m.get('usage'):st.caption(m['usage'])
        st.selectbox('Suggested question',EXAMPLES[audience],key='ai_suggested_question',disabled=busy)
        st.chat_input('Ask about NesGen 360 dashboard data',key='ai_chat_prompt',disabled=busy,on_submit=submit_chat)
        st.button('Analyze suggested question',type='primary',disabled=busy,on_click=submit_suggestion)
        if ss.agent_messages and st.button('Clear conversation',disabled=busy):
            ss.agent_messages=[];st.rerun()
        if busy:st.caption('One request is running. Send, Analyze, Audience, Suggested question and Clear are temporarily disabled.')
        pending=ss.agent_pending
        if pending and acquire(ss.agent_session):
            # Consume before calling the model. A widget rerun cannot replay it.
            ss.agent_pending=None
            prompt=pending['prompt'];rid=None;started=None;interrupted=True
            try:
                now=time.time();u=summary();estimate=max(1,len(prompt)//4)
                if get_setting('agent_disabled',False):raise RuntimeError('Application limit: AI assistant disabled')
                if len(prompt)>int(setting('AGENT_MAX_INPUT_TOKENS'))*4:raise RuntimeError('Application input limit reached')
                if u['today']>=int(setting('AGENT_REQUESTS_PER_DAY')):raise RuntimeError('Application daily limit reached')
                if not os.getenv('GEMINI_API_KEY'):raise RuntimeError('GEMINI_API_KEY is missing')
                history=ss.agent_messages.copy()
                ss.agent_messages.append({'role':'user','content':prompt})
                rid,started=begin(ss.agent_session,pending['model'],estimate)
                with st.spinner('Retrieving governed dashboard evidence...'):
                    answer,inp,out=ask(prompt,pending['model'],int(setting('AGENT_MAX_OUTPUT_TOKENS')),int(setting('AGENT_MAX_TOOL_ROUNDS')),history=history,scope=pending['scope'])
                finish(rid,started,'success',inp,out)
                ss.agent_messages.append({'role':'assistant','content':answer,
                    'usage':f"{pending['model']} · {inp:,} input tokens · {out:,} output tokens (all model requests)"})
                interrupted=False
            except Exception as exc:
                category=classify_error(exc)
                if rid:finish(rid,started,'failed',error=category)
                # Safe diagnostic only: no key, prompt, source records or exception message.
                incident=uuid.uuid4().hex[:10]
                logging.getLogger('nesgen.agent').warning('AI incident=%s type=%s category=%s',incident,type(exc).__name__,category)
                messages={'authentication':'Gemini authentication failed. Check the OS API key and restart.',
                    'provider_quota':'Provider quota reached. Wait before a deliberate retry.',
                    'timeout':'The model request timed out. No automatic retry was attempted.',
                    'network':'The connection was interrupted or reset (possibly WinError 10054). No automatic retry was attempted. Wait, then retry once.',
                    'application_limit':'Application safety limit reached. Wait or narrow the question.',
                    'response_blocked':'The model blocked the response. Rephrase the question.',
                    'unknown':'Request failed safely. Use the incident ID to correlate local diagnostics.'}
                ss.agent_messages.append({'role':'assistant','error':True,'content':messages.get(category,messages['unknown'])+' Incident: '+incident})
                ss.agent_cooldown_until=time.time()+int(setting('AGENT_COOLDOWN_SECONDS'))
                interrupted=False
            finally:
                release(ss.agent_session);ss.agent_busy=False
                if interrupted:
                    if rid:finish(rid,started,'interrupted',error='ui_interrupted')
                    ss.agent_messages.append({'role':'assistant','error':True,'content':'The UI run was interrupted. The request was not replayed automatically; provider completion may be unknown.'})
            st.rerun()
