from pathlib import Path
import sys,os,time,uuid
sys.path.insert(0,str(Path(__file__).parent))
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.data import *
from src.agent import ask, classify_error
from src.provider import provider_consumption, PROVIDER_COLORS
from src.usage import summary as usage_summary, begin as usage_begin, finish as usage_finish
from src.components import *
from src.config import setting
from src.storage import init as init_storage,register_model,set_setting,get_setting,sources
init_storage()

llm_model_name = str(setting("GEMINI_MODEL"))

st.set_page_config(page_title='NesGen 360°',page_icon='◉',layout='wide',initial_sidebar_state='expanded');inject_css()
from src.auth_ui import gate,user_management
from src.auth import require_admin
current_user=gate()
PAGES=['Executive overview','Model lifecycle','Platform health','User adoption','Chargeback','AI assistant','Administration','Solution design','Requirements','Demo & tests']
if current_user['role']!='admin':PAGES=[p for p in PAGES if p!='Administration']
with st.sidebar:
 st.markdown('<div class="brand"><div class="brand-title">NesGen 360°</div><div class="brand-sub">Operations & Governance</div></div>',unsafe_allow_html=True)
 page=st.radio('Navigation',PAGES,label_visibility='collapsed')
 st.divider();st.caption('DECISION SCOPE');provider=st.selectbox('Provider',['All']+PROVIDERS,key='provider');region=st.selectbox('Region',['Global']+REGIONS,key='region');environment=st.selectbox('Environment',['All']+ENVS,key='environment')
 st.divider();st.caption('Innovation challenge prototype');st.caption('Synthetic and sanitized data only')

def filtered_apps():
 d=get_apps();
 if region!='Global':d=d[d.region.astype(str).str.casefold()==region.casefold()]
 if provider!='All':d=d[pd.to_numeric(d.get(provider,0),errors='coerce').fillna(0)>0]
 if environment!='All':d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 return d

def filtered_models():
 d=get_models();
 if provider!='All':d=d[d.provider.astype(str).str.contains(provider,case=False,na=False)]
 return d

def executive():
 from src.executive_ui import render_executive
 render_executive()

def lifecycle():
 header('Model lifecycle','Responsible AI governance','Manage exploration, validation, industrialization, review and retirement with accountable evidence.')
 d=filtered_models();f1,f2,f3=st.columns(3);risk=f1.selectbox('Risk',['All','Low','Medium','High']);stage=f2.selectbox('Lifecycle stage',['All']+sorted(d.stage.dropna().unique().tolist()));search=f3.text_input('Search model or family')
 if risk!='All':d=d[d.risk==risk]
 if stage!='All':d=d[d.stage==stage]
 if search:d=d[d.name.astype(str).str.contains(search,case=False,na=False)|d.model_family.astype(str).str.contains(search,case=False,na=False)]
 cols=st.columns(4)
 with cols[0]:kpi('Governed models',len(d),'In selected scope')
 with cols[1]:kpi('Industrialized',int((d.stage=='Industrialized').sum()),'Approved operating models')
 with cols[2]:kpi('Review due',int(d.lifecycle_status.astype(str).str.contains('Review',case=False).sum()),'Evidence refresh required')
 with cols[3]:kpi('Retirement / migrate',int(d.migration_required.astype(str).isin(['Assess','Yes']).sum()),'Decision ownership required')
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Governance portfolio');st.dataframe(d[['name','provider','model_family','stage','owner','evaluation_score','risk','lifecycle_status','next_review_date','retire_date']],hide_index=True,width='stretch',height=380);st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.3,1])
 with l:st.plotly_chart(px.bar(d,x='name',y='evaluation_score',color='risk',color_discrete_map={'Low':'#39b98a','Medium':'#f2a93b','High':'#df4b55'},title='Evaluation readiness'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
 with r:
  selected=st.selectbox('Open decision record',d.name.tolist() if len(d) else ['No records']);
  if len(d):row=d[d.name==selected].iloc[0];st.markdown(f"**Owner:** {row.owner}  \n**Lifecycle:** {row.lifecycle_status}  \n**Risk:** {row.risk}  \n**Reason:** {row.risk_reason}  \n**Migration:** {row.migration_required}  \n**Next review:** {row.next_review_date}")

def health():
 header('Platform health','Reliability engineering','Correlate service health, failure signals, latency and accountable operational response.')
 h=get_health();d=h.copy()
 if environment!='All' and 'environment' in d:d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 cols=st.columns(4)
 with cols[0]:kpi('Success rate',f"{d.success_rate.mean():.2f}%",'Target ≥ 98%')
 with cols[1]:kpi('P95 latency',f"{d.p95_latency_ms.quantile(.95)/1000:.2f}s",'Selected period')
 with cols[2]:kpi('Request volume',f"{int(d.requests.sum()/1_000_000)}M",'90-day synthetic window')
 with cols[3]:kpi('Services healthy','41 / 43','2 need attention')
 l,r=st.columns(2)
 with l:st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Success rate');st.plotly_chart(px.line(d,x='date',y='success_rate',range_y=[90,100]),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('P95 latency');st.plotly_chart(px.line(d,x='date',y='p95_latency_ms'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Correlated operational alerts');st.dataframe(synthetic_alerts(),hide_index=True,width='stretch');st.markdown('</div>',unsafe_allow_html=True)

def adoption():
 header('User onboarding and adoption','Value realization','Measure whether onboarding converts into sustained use across regions, applications and environments.')
 full=get_apps();d=filtered_apps();active=d.status.astype(str).str.contains('Active|Operational',case=False,na=False);new=d.status.astype(str).str.contains('New',case=False,na=False);dorm=d.status.astype(str).str.contains('Dormant',case=False,na=False)
 # react reference values are preserved by fallback dataset
 cols=st.columns(4)
 with cols[0]:kpi('Onboarded apps',len(d),f"Across {d.region.nunique()} regions")
 with cols[1]:kpi('Monthly active',int(active.sum()),f"{active.mean():.0%} activation" if len(d) else '0% activation')
 with cols[2]:kpi('New this month',int(new.sum()),f"{int((d[new].environment=='Production').sum()) if len(d) else 0} reached production")
 with cols[3]:kpi('Dormant apps',int(dorm.sum()),'No use in 30 days')
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Regional adoption index');g=d.groupby('region').agg(onboarded=('id','count'),active=('status',lambda x:x.astype(str).str.contains('Active|Operational',case=False).sum())).reindex(REGIONS,fill_value=0).reset_index();fig=go.Figure([go.Bar(name='Onboarded',x=g.region,y=g.onboarded,marker_color='#c6d2e2'),go.Bar(name='Active',x=g.region,y=g.active,marker_color='#1768ff')]);fig.update_layout(barmode='group',height=390,margin=dict(l=20,r=10,t=10,b=20),plot_bgcolor='white',legend_orientation='h');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Application portfolio');st.dataframe(d[['id','name','region','status','expected_daily_users','business_value','owner','platform','recertification_status']].head(500),hide_index=True,width='stretch',height=360);st.markdown('</div>',unsafe_allow_html=True)

def chargeback():
 header('Chargeback','Financial transparency','Reconcile provider invoices with platform-attributed consumption before allocation and approval.')
 d=synthetic_charges();d['status']=d['variance'].apply(lambda v:'Review' if v>get_setting('chargeback_threshold',5) else 'Matched')
 if provider!='All':d=d[d.provider==provider]
 cols=st.columns(4)
 with cols[0]:kpi('Provider invoice',f"${d.provider_bill.sum()/1000:.1f}K",'Current period')
 with cols[1]:kpi('Attributed usage',f"${d.platform_usage.sum()/1000:.1f}K",'NesGen / MuleSoft')
 with cols[2]:kpi('Unexplained amount',f"${(d.provider_bill-d.platform_usage).sum()/1000:.1f}K",'Requires evidence')
 with cols[3]:kpi('Review exceptions',int((d.status=='Review').sum()),f"Threshold > {get_setting('chargeback_threshold',5)}%")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Provider reconciliation');fig=px.bar(d,x='provider',y=['provider_bill','platform_usage'],barmode='group',color_discrete_sequence=['#c6d2e2','#1768ff']);st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.dataframe(d,hide_index=True,width='stretch');st.markdown('</div>',unsafe_allow_html=True)
 if st.button('Run reconciliation',type='primary'):st.success(f"Reconciliation completed: {int((d.status=='Review').sum())} provider(s) above the configured threshold.")

def assistant():
 from src.assistant_ui import render_assistant
 render_assistant({'provider':provider,'region':region,'environment':environment})

def administration():
 require_admin()
 user_management()
 header('Administration','Controlled configuration','Manage prototype thresholds, ownership, lifecycle rules and synthetic records.');u=usage_summary();c=st.columns(4);c[0].metric('Gemini model',f'{llm_model_name}');c[1].metric('Requests today',f"{u['today']} / 300");c[2].metric('Tokens last minute',f"{u['tokens60']:,} / 100,000");c[3].metric('API key','Configured' if os.getenv('GEMINI_API_KEY') else 'Missing')
 tabs=st.tabs(['Governance settings','Register model','Data sources'])
 with tabs[0]:
  threshold=st.slider('Chargeback review threshold (%)',1,15,int(get_setting('chargeback_threshold',5)))
  dormancy=st.slider('Dormancy threshold (days)',7,90,int(get_setting('dormancy_days',30)))
  disabled=st.checkbox('Disable AI assistant',value=bool(get_setting('agent_disabled',False)))
  if st.button('Save configuration'):
   set_setting('chargeback_threshold',threshold);set_setting('dormancy_days',dormancy);set_setting('agent_disabled',disabled);st.success('Configuration saved to SQLite.')
  st.caption('Dormancy threshold is stored for future activity-log rules; current workbook status labels are not reclassified without activity dates.')
 with tabs[1]:
  with st.form('register'):
   name=st.text_input('Model name');cloud=st.selectbox('Provider',PROVIDERS);owner=st.text_input('Accountable owner');stage=st.selectbox('Lifecycle stage',['Exploration','Sandbox validation','Industrialized','Retirement planned']);score=st.slider('Evaluation score',0,100,75);risk=st.selectbox('Risk',['Low','Medium','High']);submitted=st.form_submit_button('Register synthetic model',type='primary')
  if submitted:
   try:
    ident=register_model(name,cloud,owner,stage,score,risk);st.success('Model saved: '+ident)
   except ValueError as exc:st.error(str(exc))
 with tabs[2]:
  get_apps();get_models();get_health()
  st.dataframe(pd.DataFrame(sources()),hide_index=True,width='stretch')
  st.caption('Source rejection is explicit. Fallback rows remain synthetic; workbook classification must be checked before sending aggregates to a personal API.')

def solution():
 header('Solution design','Enterprise architecture','Explain how the prototype evolves into a governed, scalable and supportable enterprise platform.')
 st.markdown('''<div class="panel"><div class="panel-title">Target logical flow</div><h3>Source systems → Governed ingestion → Decision data products → NesGen 360° experience</h3><p>New Relic, Log Analytics, provider billing, onboarding and model-governance sources feed quality-controlled data products. Streamlit demonstrates the decision experience while production services add identity, authorization, audit and managed persistence.</p></div>''',unsafe_allow_html=True)
 cols=st.columns(4)
 for col,(a,b,c) in zip(cols,[('Experience','Streamlit prototype','Responsive decision journeys'),('Operational store','SQLite → PostgreSQL','Governance and workflow'),('Analytics','DuckDB / Parquet','Efficient local aggregates'),('Security','Entra ID + Key Vault','RBAC, secrets and audit')]):
  with col:kpi(a,b,c)
 st.subheader('POC-to-production roadmap');st.progress(.35,text='POC: coherent decision experience');st.progress(.2,text='Pilot: governed read-only connectors');st.progress(.1,text='Production: identity, SRE, audit and scale')

def requirements():
 header('Requirements','Traceability','Separate implemented prototype capability from production and future-enterprise commitments.')
 req=pd.DataFrame([['REQ-01','Application starts repeatably','POC','Implemented'],['REQ-02','Primary journey works end to end','POC','Implemented'],['REQ-03','Synthetic fallback for every page','POC','Implemented'],['REQ-04','Entra ID and RBAC','Production','Planned'],['REQ-05','Live governed connectors','Production','Planned'],['REQ-06','Dashboard-grounded Gemini agent','POC','Implemented'],['REQ-07','Audit, retention and lineage','Production','Planned']],columns=['ID','Requirement','Classification','Status']);st.dataframe(req,hide_index=True,width='stretch');st.caption('Implemented means implemented in the local innovation-challenge prototype, not approved for production.')

def demo_tests():
 header('Demo & tests','Challenge readiness','Protect the live demonstration path, verify critical journeys and disclose limitations honestly.')
 cols=st.columns(3)
 with cols[0]:kpi('Page routes','10','Run tests for current status')
 with cols[1]:kpi('Core scenarios','4 / 4','Reliability, adoption, cost, governance')
 with cols[2]:kpi('Fallback mode','Ready','No external dependency required')
 st.subheader('3–5 minute demonstration flow');st.markdown('''1. **Executive overview:** establish the three decision gaps.  
2. **Platform health:** trace the 8.6% pre-production signal.  
3. **Chargeback:** run reconciliation and explain the 7.4% AWS exception.  
4. **Model lifecycle:** show evidence, review and retirement ownership.  
5. **User adoption:** connect onboarding to sustained use and regional value.''')
 st.subheader('Pre-demonstration checklist');
 for x in ['Run automated tests','Start app from clean terminal','Verify all ten pages','Confirm 1366×768 display scaling','Keep screenshots available as fallback','State that all data is synthetic']:st.checkbox(x,value=x not in ['Keep screenshots available as fallback'])

ROUTES={'Executive overview':executive,'Model lifecycle':lifecycle,'Platform health':health,'User adoption':adoption,'Chargeback':chargeback,'AI assistant':assistant,'Administration':administration,'Solution design':solution,'Requirements':requirements,'Demo & tests':demo_tests}
safe_page(ROUTES[page])
st.markdown('<div class="small-muted" style="margin-top:2rem">NesGen 360° innovation challenge prototype · Synthetic data only · Not approved for production</div>',unsafe_allow_html=True)
