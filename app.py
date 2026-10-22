from pathlib import Path
import sys,os,time,uuid,html
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
# V1.1: KPI definitions + rule-based decision brief (src/insights.py); in-card info replaces the old bottom explainer block
from src.insights import KPI_INFO, build_decision_brief, executive_focus, priority_breakdown
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


def sm(df):
 return str(df.attrs.get('source_mode','synthetic'))

def executive():
 # V1.1: focus text, priority count, findings and actions are computed from data (src/insights.py); every card has an in-card info drawer
 a=filtered_apps();m=filtered_models();h=get_health();c=synthetic_charges();brief=build_decision_brief(a,m,h,c,synthetic_alerts())
 header('Executive overview','Decision intelligence','Prioritize the operational, financial and governance decisions that require leadership attention.',source=sm(h))
 st.markdown(f'<div class="callout"><b>Today’s focus:</b> {html.escape(executive_focus(brief))}</div>',unsafe_allow_html=True);cols=st.columns(4)
 with cols[0]:kpi('Platform availability',f"{h.success_rate.mean():.2f}%",'Across selected decision scope',KPI_INFO['availability'],sm(h))
 with cols[1]:kpi('Governed models',len(m),f"{int((m.risk=='High').sum())} high-risk reviews",KPI_INFO['governed_models'],sm(m))
 with cols[2]:kpi('Monthly active apps',int((a.status.astype(str).str.contains('Active|Operational',case=False)).sum()),'Sustained use signal',KPI_INFO['monthly_active_apps'],sm(a))
 with cols[3]:kpi('Priority actions',len(brief),priority_breakdown(brief),KPI_INFO['priority_actions'],'synthetic')
 l,r=st.columns([1.6,1])
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Usage and reliability trend');trend=h.tail(30).copy();fig=go.Figure();fig.add_trace(go.Bar(x=trend.date,y=trend.requests,name='Requests',marker_color='#c6d2e2'));fig.add_trace(go.Scatter(x=trend.date,y=trend.success_rate,name='Success %',yaxis='y2',line=dict(color='#1768ff',width=3)));fig.update_layout(height=330,margin=dict(l=10,r=10,t=15,b=5),plot_bgcolor='white',legend_orientation='h',yaxis2=dict(overlaying='y',side='right',range=[90,100]),hovermode='x unified');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Provider consumption');p=provider_consumption(a);fig=px.pie(p,names='provider',values='monthly_requests',hole=.62,color='provider',color_discrete_map=PROVIDER_COLORS);fig.update_traces(textposition='inside',textinfo='percent',hovertemplate='<b>%{label}</b><br>Monthly requests: %{value:,.0f}<br>Portfolio share: %{percent:.1%}<extra></extra>');fig.update_layout(height=345,margin=dict(l=10,r=10,t=10,b=10),paper_bgcolor='rgba(0,0,0,0)',legend=dict(y=.9,x=1.02));st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 # AI findings (evidence) and recommended actions (owner) come from the same rule-based brief
 fl,fr=st.columns(2)
 with fl:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('AI findings');st.caption('Rule-based analysis of dashboard data; each finding cites its evidence and source.')
  for i in brief:finding_card(i)
  if not brief:st.info('No findings against the current thresholds.')
  st.markdown('</div>',unsafe_allow_html=True)
 with fr:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Recommended actions');st.caption('Next step and accountable owner for each finding.')
  for i in brief:finding_card(i,show_action=True)
  if not brief:st.info('No actions required.')
  st.markdown('</div>',unsafe_allow_html=True)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Leadership action queue');st.dataframe(synthetic_alerts(),hide_index=True,width='stretch');st.markdown('</div>',unsafe_allow_html=True)

def lifecycle():
 tel=get_telemetry();m0=enrich_models(filtered_models(),tel['clients']);d=m0
 header('Model lifecycle','Responsible AI governance','Manage exploration, validation, industrialization, review and retirement with accountable evidence.',source=sm(filtered_models()))
 f1,f2,f3,f4=st.columns(4);risk=f1.selectbox('Risk',['All','Low','Medium','High']);cat=f2.selectbox('Category',['All','Sandbox','Industrialized','Retirement']);stage=f3.selectbox('Lifecycle stage',['All']+sorted(d.stage.dropna().unique().tolist()));search=f4.text_input('Search model or family')
 if risk!='All':d=d[d.risk==risk]
 if cat!='All':d=d[d.lifecycle_category==cat]
 if stage!='All':d=d[d.stage==stage]
 if search:d=d[d.name.astype(str).str.contains(search,case=False,na=False)|d.model_family.astype(str).str.contains(search,case=False,na=False)]
 mode=sm(filtered_models());cols=st.columns(4)
 with cols[0]:kpi('Governed models',len(d),'In selected scope',KPI_INFO['lifecycle_governed'],mode)
 with cols[1]:kpi('Industrialized',int((d.lifecycle_category=='Industrialized').sum()),'Approved operating models',KPI_INFO['industrialized'],mode)
 with cols[2]:kpi('Sandbox',int((d.lifecycle_category=='Sandbox').sum()),'Exploration / validation',KPI_INFO['lifecycle_sandbox'],mode)
 with cols[3]:kpi('Review due',int(d.lifecycle_status.astype(str).str.contains('Review',case=False).sum()),'Evidence refresh required',KPI_INFO['review_due'],mode)
 cols=st.columns(4)
 with cols[0]:kpi('Retirement / migrate',int(d.migration_required.astype(str).isin(['Assess','Yes']).sum()),'Decision ownership required',KPI_INFO['retirement'],mode)
 with cols[1]:kpi('With backup model',f"{int(d.has_backup.sum())} / {len(d)}",'Suggested replacement exists',KPI_INFO['models_with_backup'],'derived',tone='ok' if len(d) and d.has_backup.all() else 'warn')
 with cols[2]:kpi('Avg decommission readiness',f"{d.decommission_readiness.mean():.0f} / 100" if len(d) else 'n/a','Higher = safer to retire',KPI_INFO['readiness'],'derived')
 with cols[3]:kpi('High-risk replacements',int((d.replacement_risk.astype(str).str.casefold()=='high').sum()),'Backup model is itself high risk',KPI_INFO['readiness'],'derived',tone='bad')
 with st.expander('How is evaluation / readiness scored?'):
  st.markdown("**Evaluation score** comes from the model workbook (`score_source`: synthetic POC composite).  \n**Decommission readiness (0-100)** = 40% evaluation score + 20 if a backup model exists + up to 15 for the backup's risk level (Low 15, Medium 8, High 0) + up to 15 for time left before retirement + up to 10 for evaluation evidence status (Current 10, Review due 5, Action required 0).  \n**Suggested replacement** is derived by rule: same provider and family preferred, retiring later than this model, not already retired; best evaluation score wins. **Unique clients** is the number of distinct API client IDs seen in telemetry for the model, not named people.")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Governance portfolio');st.dataframe(d[['name','provider','model_family','lifecycle_category','stage','owner','evaluation_score','risk','unique_clients','suggested_replacement','replacement_risk','decommission_readiness','lifecycle_status','next_review_date','retire_date']].head(100),hide_index=True,width='stretch',height=380);st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.3,1])
 with l:st.plotly_chart(px.bar(d,x='name',y='decommission_readiness',color='risk',color_discrete_map={'Low':'#39b98a','Medium':'#f2a93b','High':'#df4b55'},title='Decommission readiness'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
 with r:
  selected=st.selectbox('Open decision record',d.name.tolist() if len(d) else ['No records']);
  if len(d):row=d[d.name==selected].iloc[0];st.markdown(f"**Owner:** {row.owner}  \n**Lifecycle:** {row.lifecycle_status}  \n**Risk:** {row.risk}  \n**Reason:** {row.risk_reason}  \n**Migration:** {row.migration_required}  \n**Suggested replacement:** {row.suggested_replacement} ({row.replacement_basis}, risk {row.replacement_risk})  \n**Unique API clients:** {row.unique_clients}  \n**Readiness:** {row.decommission_readiness:.0f}/100  \n**Next review:** {row.next_review_date}")

def health():
 h=get_health();d=h.copy();tel=get_telemetry();ts=tel['stats'];tm=tel['mode']
 header('Platform health','Reliability engineering','Correlate service health, failure signals, latency and accountable operational response.',source=sm(h))
 if environment!='All' and 'environment' in d:d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 # Level 1: call volume with colour-coded success / failure cards (telemetry-wide; the environment filter does not apply)
 tot=max(ts['total'],1);cols=st.columns(4)
 with cols[0]:kpi('Total API calls',f"{ts['total']:,}",f"{ts['unclassified']:,} events unclassified" if ts['unclassified'] else 'All calls classified',KPI_INFO['api_calls'],tm)
 with cols[1]:kpi('Successful calls',f"{ts['success']:,}",f"{100*ts['success']/tot:.2f}% of calls",KPI_INFO['calls_success'],tm,tone='ok')
 with cols[2]:kpi('Failed calls',f"{ts['failed']:,}",f"{100*ts['failed']/tot:.2f}% of calls",KPI_INFO['calls_failed'],tm,tone='bad')
 with cols[3]:kpi('P95 latency (true)',f"{ts['p95_ms']/1000:.2f}s" if ts['p95_ms'] else 'n/a','95th percentile over all calls',KPI_INFO['p95_true'],tm)
 cols=st.columns(3)
 with cols[0]:kpi('Daily success rate',f"{d.success_rate.mean():.2f}%",'Target ≥ 98% · mean of daily values',KPI_INFO['success_rate'],sm(h))
 with cols[1]:kpi('P95 latency (daily trend)',f"{d.p95_latency_ms.quantile(.95)/1000:.2f}s",'95th percentile of daily P95s',KPI_INFO['p95_latency'],sm(h))
 with cols[2]:kpi('Services healthy','41 / 43','Illustrative · 2 need attention',KPI_INFO['services_healthy'],'synthetic')
 with st.expander('How is P95 latency evaluated?'):
  st.markdown(f"**True P95** (card above) = 95th percentile of `responseTime` over every classified call: **{(ts['p95_ms'] or 0):,.0f} ms**.  \n**Daily-trend P95** = the chart below takes each day's P95, and the card takes the 95th percentile of those daily values: **{d.p95_latency_ms.quantile(.95):,.0f} ms**. These differ because a percentile of daily percentiles is not the P95 of all calls. Use the true P95 for SLA statements.  \nUnit is milliseconds as logged by the gateway.")
 l,r=st.columns(2)
 with l:st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Success rate');st.plotly_chart(px.line(d,x='date',y='success_rate',range_y=[90,100]),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('P95 latency (daily)');st.plotly_chart(px.line(d,x='date',y='p95_latency_ms'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 # Level 2: which models fail
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Level 2 · Failures by model');bm=tel['by_model'].sort_values('failures',ascending=False).head(15)
 st.plotly_chart(px.bar(bm,x='model',y='failures',color='provider',hover_data=['calls','failure_rate']),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.dataframe(bm.assign(failure_rate=bm.failure_rate.round(2)),hide_index=True,width='stretch');st.markdown('</div>',unsafe_allow_html=True)
 # Level 3: most frequent errors
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Level 3 · Most frequent errors');er=tel['errors'].head(15)
 st.dataframe(er,hide_index=True,width='stretch');st.caption('Error code, message and provider are shown exactly as logged; combinations can look inconsistent in synthetic telemetry.');st.markdown('</div>',unsafe_allow_html=True)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Correlated operational alerts');st.dataframe(synthetic_alerts(),hide_index=True,width='stretch');st.markdown('</div>',unsafe_allow_html=True)

def adoption():
 # V1.1: use-case view (stage, segment, active users) instead of user counts; fields follow docs/DATA_CONTRACTS.md
 full=get_apps();d=filtered_apps().head(100) if full.attrs.get('source_mode')!='workbook' else filtered_apps();mode=sm(full)
 header('User onboarding and adoption','Value realization','Measure how many use cases are onboarded, at which stage, for which segment, and how many people use them.',source=mode)
 stage=d.get('use_case_stage',pd.Series('Unknown',index=d.index)).astype(str);seg=d.get('segment',pd.Series('Unknown',index=d.index)).astype(str)
 active=d.status.astype(str).str.contains('Active|Operational',case=False,na=False);new=d.status.astype(str).str.contains('New',case=False,na=False);dorm=d.status.astype(str).str.contains('Dormant',case=False,na=False)
 cols=st.columns(4)
 with cols[0]:kpi('Use cases onboarded',int(d['id'].nunique()),f"Across {d.region.nunique()} regions",KPI_INFO['use_cases'],mode)
 with cols[1]:kpi('Sandbox',int((stage=='Sandbox').sum()),'Experimenting, not yet industrialized',KPI_INFO['uc_sandbox'],mode)
 with cols[2]:kpi('Industrialized',int((stage=='Industrialized').sum()),'Running in production',KPI_INFO['uc_industrialized'],mode)
 with cols[3]:kpi('Active platform users',f"{int(pd.to_numeric(d.get('active_users',0),errors='coerce').fillna(0).sum()):,}",'Sum across use cases',KPI_INFO['platform_users'],mode)
 cols=st.columns(3)
 with cols[0]:kpi('Monthly active use cases',int(active.sum()),f"{active.mean():.0%} activation" if len(d) else '0% activation',KPI_INFO['adoption_active'],mode)
 with cols[1]:kpi('New this month',int(new.sum()),'Recently onboarded',KPI_INFO['adoption_new'],mode)
 with cols[2]:kpi('Dormant use cases',int(dorm.sum()),'No use in 30 days',KPI_INFO['dormant'],mode,tone='warn')
 l,r=st.columns(2)
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Segment: B2B vs B2C by stage');g=pd.DataFrame({'segment':seg,'stage':stage}).value_counts().reset_index(name='use_cases');st.plotly_chart(px.bar(g,x='segment',y='use_cases',color='stage',barmode='stack'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Regional adoption index');g=d.groupby('region').agg(onboarded=('id','count'),active=('status',lambda x:x.astype(str).str.contains('Active|Operational',case=False).sum())).reindex(REGIONS,fill_value=0).reset_index();fig=go.Figure([go.Bar(name='Onboarded',x=g.region,y=g.onboarded,marker_color='#c6d2e2'),go.Bar(name='Active',x=g.region,y=g.active,marker_color='#1768ff')]);fig.update_layout(barmode='group',height=390,margin=dict(l=20,r=10,t=10,b=20),plot_bgcolor='white',legend_orientation='h');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 cols_show=[c for c in ['id','name','region','use_case_stage','segment','status','active_users','expected_daily_users','business_value','owner','platform','recertification_status'] if c in d]
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Use-case portfolio');st.dataframe(d[cols_show].head(100),hide_index=True,width='stretch',height=360);st.markdown('</div>',unsafe_allow_html=True)

def chargeback():
 header('Chargeback','Financial transparency','Reconcile provider invoices with platform-attributed consumption before allocation and approval.')
 d=synthetic_charges();d['status']=d['variance'].apply(lambda v:'Review' if v>get_setting('chargeback_threshold',5) else 'Matched')
 if provider!='All':d=d[d.provider==provider]
 cols=st.columns(4)
 with cols[0]:kpi('Provider invoice',f"${d.provider_bill.sum()/1000:.1f}K",'Current period',KPI_INFO['invoice'],'synthetic')
 with cols[1]:kpi('Attributed usage',f"${d.platform_usage.sum()/1000:.1f}K",'NesGen / MuleSoft',KPI_INFO['attributed'],'synthetic')
 with cols[2]:kpi('Unexplained amount',f"${(d.provider_bill-d.platform_usage).sum()/1000:.1f}K",'Requires evidence',KPI_INFO['unexplained'],'synthetic')
 with cols[3]:kpi('Review exceptions',int((d.status=='Review').sum()),f"Threshold > {get_setting('chargeback_threshold',5)}%",KPI_INFO['exceptions'],'synthetic')
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
