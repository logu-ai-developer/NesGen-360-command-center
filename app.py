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
from src.insights import KPI_INFO, AVAILABILITY_TARGET, build_decision_brief, executive_focus_bullets, priority_breakdown, SEVERITY_ICONS, finding_target, model_review_priority, RISK_BADGES, RISK_COLORS, REVIEW_PRIORITY_LABELS
from src.timewindow import WINDOW_DAYS, DEFAULT_WINDOW, resolve_window, previous_window, anchor_date, filter_by_window, describe_basis, period_counts, trend_direction, lifecycle_anchor, lifecycle_date_counts
from src.metrics import health_outcomes, fmt_pct, canonical_use_cases, normalize_stage, normalize_status, active_users_presentation, derived_from, NO_CLASSIFIED_NOTE
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
 page=st.radio('Navigation',PAGES,label_visibility='collapsed',key='nav_page')
 st.divider();st.caption('TIME WINDOW')
 time_key=st.radio('Time window',list(WINDOW_DAYS),index=list(WINDOW_DAYS).index(DEFAULT_WINDOW),key='time_window',help='Fixed day counts: 1 Month = 30, 3 Months = 90, 6 Months = 180 days. Applies to telemetry and approval dates; inventory, status, chargeback and alert views are snapshots.')
 st.caption(f'Time Window: {time_key} ({WINDOW_DAYS[time_key]} days)')
 st.divider();st.caption('DATA MODE')
 data_mode=st.radio('Data mode',['Real Data','Demo Scenario Data'],key='data_mode',help='Real Data uses the source-backed telemetry. Demo Scenario Data swaps only the Executive telemetry metrics and Platform Health to deterministic synthetic telemetry spanning 180 days.')
 demo=data_mode=='Demo Scenario Data'
 st.caption('Data Mode: '+data_mode+(' · synthetic' if demo else ''))
 st.divider();st.caption('DECISION SCOPE');region=st.selectbox('Region',['Global']+REGIONS,key='region');environment=st.selectbox('Environment',['All']+ENVS,key='environment');provider=st.selectbox('Provider',['All']+PROVIDERS,key='provider')
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


def rate_tone(pct):
 # Red only when reliability is below target; green when met; neutral when the rate is unavailable.
 return None if pct is None else ('bad' if pct<AVAILABILITY_TARGET else 'ok')

def window_for(*date_series):
 # One definition for every page (src/timewindow.py), anchored to the latest non-future date of the source being windowed.
 return resolve_window(time_key,anchor_date(*date_series))

def demo_banner():
 if demo:st.markdown(f'<div class="callout"><b>DEMO SCENARIO DATA</b> {source_badge("synthetic scenario")} Telemetry on this page is deterministic synthetic demonstration data, not real telemetry.</div>',unsafe_allow_html=True)

def risk_card(row,attention=''):
 # Subtle left-border indicator (red / amber / green), not a fully coloured row.
 key=str(row.risk).casefold();color=RISK_COLORS.get(key,'#65758a')
 st.markdown(f'<div class="finding" style="border-left-color:{color}"><div class="finding-title">{RISK_BADGES.get(key,html.escape(str(row.risk)))} · {html.escape(str(row["name"]))}</div><div class="finding-meta">{html.escape(attention) or "No review flag"}</div></div>',unsafe_allow_html=True)

NL=chr(10)   # KPI notes use line breaks (rendered as <br> by kpi())

def undated_line(undated):
 return f"{undated:,} undated events excluded" if undated else ''

def success_note(o,tdir,window,undated):
 # Primary note: what needs attention. Methodology and caveats live in the drawer; the Unclassified events card shows undated events.
 if not o['classified']:return NO_CLASSIFIED_NOTE
 if o['success_pct']<AVAILABILITY_TARGET:return f"Below {AVAILABILITY_TARGET:.0f}% target · {o['failed']:,} failed calls require investigation"
 return f"Meets {AVAILABILITY_TARGET:.0f}% target · {o['failed']:,} failed calls in selected window"

def unclassified_note(o,undated):
 if not o['events'] and not undated:return 'No events in window'
 return NL.join(x for x in (f"{fmt_pct(o['unclassified_pct'])} of events in selected window" if o['events'] else 'No events in selected window',undated_line(undated)) if x)

def go_to(page_name):
 # Session-state routing: runs as a button callback, i.e. before the sidebar radio is instantiated on the next run.
 st.session_state['nav_page']=page_name

def compact_basis(window,mode,note=''):
 st.caption(f"Window: {window.window_label} · Source: {mode} · Last available: {window.window_end:%Y-%m-%d}"+note)

def vs_previous(direction,window):
 return f" · {direction} vs previous {window.window_days} days" if direction else ''

def sm(df):
 return str(df.attrs.get('source_mode','synthetic fallback'))

def executive():
 # V1.1: focus text, priority count, findings and actions are computed from data (src/insights.py); every card has an in-card info drawer
 a=filtered_apps();m=filtered_models();h_all=get_health(demo);hw=window_for(h_all.date);h=filter_by_window(h_all,'date',hw);c=synthetic_charges();brief=build_decision_brief(a,m,h,c,synthetic_alerts())
 header('Executive overview','Decision intelligence','Prioritize the operational, financial and governance decisions that require leadership attention.',source=sm(h_all))
 demo_banner()
 canon,_=canonical_use_cases(a);aw=window_for(canon.created_date)
 compact_basis(hw,sm(h_all));
 with st.expander('Data basis'):
  st.caption('Telemetry · '+describe_basis(hw,'event timestamp',sm(h_all)));st.caption('Approvals · '+describe_basis(aw,'approval date',sm(a))+' · inventory, status, chargeback and alerts are snapshots, not windowed')
 group_title('Priority findings','Select a finding to open its evidence')
 if not brief:st.success('No priority findings identified.',icon='✅')
 for n,item in enumerate(brief[:5]):
  target=finding_target(item);c1,c2=st.columns([5,1.6])
  with c1:st.markdown(f'<div class="finding" style="border-left-color:{SEVERITY_COLORS.get(item["severity"],"#1768ff")}"><div class="finding-title">{SEVERITY_ICONS.get(item["severity"],"⚪")} {html.escape(item["title"])}</div><div class="finding-meta">{html.escape(item["category"])} · {html.escape(item["severity"])} · {html.escape(item["owner"])}</div></div>',unsafe_allow_html=True)
  with c2:st.button(f'Open {target} →',key=f'go_{n}',on_click=go_to,args=(target,),width='stretch')
 group_title('Key metrics');cols=st.columns(4)
 undated=get_telemetry(hw,demo)['stats']['undated_events'];o=health_outcomes(h);tdir=trend_direction(o['success_pct'],health_outcomes(filter_by_window(h_all,'date',previous_window(hw)))['success_pct'],abs_tol=.5)
 with cols[0]:kpi('Classified-call success rate',fmt_pct(o['success_pct']),(success_note(o,tdir,hw,undated)),KPI_INFO['classified_success'],sm(h_all),tone=rate_tone(o['success_pct']))
 with cols[1]:kpi('Models in inventory',len(m),f"{int((m.risk=='High').sum())} high-risk reviews",KPI_INFO['models_inventory'],sm(m))
 with cols[2]:kpi('Active-status use cases',int((canon['status_category']=='Active').sum()),f"{(canon['status_category']=='Active').mean():.0%} of use cases have Active status" if len(canon) else 'No use cases in scope',KPI_INFO['active_status_use_cases'],sm(a))
 with cols[3]:kpi('Priority actions',len(brief),priority_breakdown(brief),KPI_INFO['priority_actions'],'synthetic scenario')
 new_now=len(filter_by_window(canon,'created_date',aw));new_prev=len(filter_by_window(canon,'created_date',previous_window(aw)));cols=st.columns(4)
 with cols[0]:kpi('Newly approved use cases',new_now,aw.window_label+' · approval date'+vs_previous(trend_direction(new_now,new_prev),aw),KPI_INFO['newly_approved'],sm(a))
 with cols[1]:kpi('Unclassified events',f"{o['unclassified']:,}",unclassified_note(o,undated),KPI_INFO['unclassified_events'],'unclassified telemetry present' if o['unclassified'] or undated else sm(h_all),tone='warn' if o['unclassified'] or undated else None)
 l,r=st.columns([1.6,1])
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Usage and reliability trend');trend=h.copy();fig=go.Figure();fig.add_trace(go.Bar(x=trend.date,y=trend.requests,name='Requests',marker_color='#c6d2e2'));fig.add_trace(go.Scatter(x=trend.date,y=trend.success_rate,name='Classified-call success %',yaxis='y2',line=dict(color='#1768ff',width=3)));fig.update_layout(height=330,margin=dict(l=10,r=10,t=15,b=5),plot_bgcolor='white',legend_orientation='h',yaxis2=dict(overlaying='y',side='right',range=[90,100]),hovermode='x unified');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
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
 lw=resolve_window(time_key,lifecycle_anchor(m0));lc=lifecycle_date_counts(m0,lw)
 compact_basis(lw,sm(filtered_models()))
 with st.expander('Data basis'):st.caption(describe_basis(lw,'lifecycle dates (review, retirement, migration)',sm(filtered_models()))+' · models with a date in the window: '+(' · '.join(f'{k} {v}' for k,v in lc.items()) or 'no lifecycle dates in this source')+' · the KPIs below are an inventory snapshot, not windowed')
 f1,f2,f3,f4=st.columns(4);risk=f1.selectbox('Risk',['All','Low','Medium','High']);cat=f2.selectbox('Category',['All','Sandbox','Industrialized','Retirement']);stage=f3.selectbox('Lifecycle stage',['All']+sorted(d.stage.dropna().unique().tolist()));search=f4.text_input('Search model or family')
 if risk!='All':d=d[d.risk==risk]
 if cat!='All':d=d[d.lifecycle_category==cat]
 if stage!='All':d=d[d.stage==stage]
 if search:d=d[d.name.astype(str).str.contains(search,case=False,na=False)|d.model_family.astype(str).str.contains(search,case=False,na=False)]
 rank=model_review_priority(d);d=d.loc[rank.sort_values(kind='stable').index]   # review candidates first; presentation order only
 inv=d.assign(attention=rank.map(REVIEW_PRIORITY_LABELS),risk=d.risk.astype(str).str.casefold().map(RISK_BADGES).fillna(d.risk))
 mode=sm(filtered_models());n_local=int((m0.get('record_origin',pd.Series(dtype=str))=='locally registered').sum())
 if n_local:st.markdown(f'{source_badge("locally registered")} {n_local} model record(s) were created through the local POC registration workflow and are included below; they are not source-system records.',unsafe_allow_html=True)
 cols=st.columns(4)
 with cols[0]:kpi('Models in inventory',len(d),'In selected scope',KPI_INFO['lifecycle_governed'],mode)
 with cols[1]:kpi('Industrialized',int((d.lifecycle_category=='Industrialized').sum()),'Approved operating models',KPI_INFO['industrialized'],mode)
 with cols[2]:kpi('Sandbox',int((d.lifecycle_category=='Sandbox').sum()),'Exploration / validation',KPI_INFO['lifecycle_sandbox'],mode)
 with cols[3]:kpi('Review due',int(d.lifecycle_status.astype(str).str.contains('Review',case=False).sum()),'Evidence refresh required',KPI_INFO['review_due'],mode)
 cols=st.columns(4)
 with cols[0]:kpi('Retirement / migrate',int(d.migration_required.astype(str).isin(['Assess','Yes']).sum()),'Decision ownership required',KPI_INFO['retirement'],mode)
 with cols[1]:kpi('With backup model',f"{int(d.has_backup.sum())} / {len(d)}",'Suggested replacement exists',KPI_INFO['models_with_backup'],derived_from(mode),tone='ok' if len(d) and d.has_backup.all() else 'warn')
 with cols[2]:kpi('Avg decommission readiness',f"{d.decommission_readiness.mean():.0f} / 100" if len(d) else 'n/a','Higher = safer to retire',KPI_INFO['readiness'],derived_from(mode))
 with cols[3]:kpi('Replacement candidates requiring review',int((d.replacement_risk.astype(str).str.casefold()=='high').sum()),'Alternative model may require additional assessment',KPI_INFO['readiness'],derived_from(mode),tone='warn')
 with st.expander('How is evaluation / readiness scored?'):
  st.markdown("**Evaluation score** comes from the model workbook (`score_source`: synthetic POC composite).  \n**Decommission readiness (0-100)** = 40% evaluation score + 20 if a backup model exists + up to 15 for the backup's risk level (Low 15, Medium 8, High 0) + up to 15 for time left before retirement + up to 10 for evaluation evidence status (Current 10, Review due 5, Action required 0).  \n**Suggested replacement** is derived by rule: same provider and family preferred, retiring later than this model, not already retired; best evaluation score wins. **Unique clients** is the number of distinct API client IDs seen in telemetry for the model, not named people.")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Model inventory and decisions');st.caption('Review candidates first: high risk + overdue review, high risk, review due, migration required, then the rest.');st.dataframe(inv[[c for c in ['attention','name','provider','model_family','lifecycle_category','stage','owner','evaluation_score','risk','unique_clients','suggested_replacement','replacement_risk','decommission_readiness','lifecycle_status','next_review_date','retire_date','record_origin'] if c in inv]].head(100),hide_index=True,width='stretch',height=380);st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.3,1])
 with l:st.plotly_chart(px.bar(d,x='name',y='decommission_readiness',color='risk',color_discrete_map={'Low':'#39b98a','Medium':'#f2a93b','High':'#df4b55'},title='Decommission readiness'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
 with r:
  selected=st.selectbox('Open decision record',d.name.tolist() if len(d) else ['No records']);
  if len(d):row=d[d.name==selected].iloc[0];risk_card(row,REVIEW_PRIORITY_LABELS[int(rank[row.name])]);st.markdown(f"**Owner:** {row.owner}  \n**Lifecycle:** {row.lifecycle_status}  \n**Risk:** {row.risk}  \n**Reason:** {row.risk_reason}  \n**Migration:** {row.migration_required}  \n**Suggested replacement:** {row.suggested_replacement} ({row.replacement_basis}, risk {row.replacement_risk})  \n**Unique API clients:** {'N/A' if pd.isna(row.unique_clients) else int(row.unique_clients)}  \n**Readiness:** {row.decommission_readiness:.0f}/100  \n**Next review:** {row.next_review_date}")

def health():
 h=get_health(demo);hw=window_for(h.date);d=filter_by_window(h,'date',hw);tel=get_telemetry(hw,demo);ts=tel['stats'];tm=tel['mode']
 header('Platform health','Reliability engineering','Is reliability acceptable, what is failing, and what should we investigate?',source=sm(h))
 demo_banner()
 compact_basis(hw,sm(h))
 with st.expander('Data basis'):st.caption(describe_basis(hw,'event timestamp',sm(h))+' · every card, chart and table on this page uses this window')
 if environment!='All' and 'environment' in d:d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 if ts['undated_events']:st.caption(f"{ts['undated_events']:,} events have no event timestamp, cannot be placed in a time window and are excluded from this view.")
 if ts['unclassified']:
  st.markdown(f'{source_badge("unclassified telemetry present")} {ts["unclassified_pct"]:.1f}% of telemetry events could not be classified and are excluded from reliability calculations.',unsafe_allow_html=True)
  with st.expander('Learn more'):st.markdown(f"{ts['unclassified']:,} of {ts['events']:,} events ({fmt_pct(ts['unclassified_pct'])}) have no success or failure marker. They are excluded from classified-call success and failure rates and are never counted as successful.")
 note=lambda pct,what:f"{fmt_pct(pct)} of {what}" if ts['classified'] else NO_CLASSIFIED_NOTE
 p95d=d.p95_latency_ms.quantile(.95) if len(d) else float('nan');chart_cfg={'displayModeBar':False,'displaylogo':False,'responsive':True}
 # Section 1: reliability status (telemetry-wide; the environment filter does not apply to the cards)
 group_title('Reliability status');cols=st.columns(3)
 with cols[0]:kpi('Classified-call success rate',fmt_pct(ts['success_pct']),'Target ≥ 98% · not verified availability' if ts['classified'] else NO_CLASSIFIED_NOTE,KPI_INFO['calls_success_rate'],tm,tone=rate_tone(ts['success_pct']))
 with cols[1]:kpi('Failed classified calls',f"{ts['failed']:,}",note(ts['failure_pct'],'classified calls'),KPI_INFO['calls_failed'],tm,tone=rate_tone(ts['success_pct']) if rate_tone(ts['success_pct'])=='bad' else None)
 with cols[2]:kpi('P95 latency (true)',f"{ts['p95_ms']/1000:.2f}s" if ts['p95_ms'] else 'N/A','95th percentile over classified calls',KPI_INFO['p95_true'],tm)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Daily classified-call success rate (%)');st.plotly_chart(px.line(d,x='date',y='success_rate',range_y=[90,100]),width='stretch',config=chart_cfg);st.markdown('</div>',unsafe_allow_html=True)
 # Section 2: investigation areas, ranked bars first; evidence tables stay available in an expander
 group_title('Investigation areas','Ranked by failed classified calls')
 er=tel['errors'].head(10).copy();bm=tel['by_model'].sort_values('failures',ascending=False).head(10);bp=tel['by_provider'].sort_values('failures',ascending=False)
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Most frequent errors')
 if len(er):
  er['error']=er.error_code.astype(str)+' · '+er.error_message.astype(str).str.slice(0,40);st.plotly_chart(px.bar(er,x='occurrences',y='error',orientation='h',hover_data=['error_source']).update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(er)+60),margin=dict(l=10,r=10,t=10,b=10)),width='stretch',config=chart_cfg)
 else:st.info('No failed classified calls in this window.')
 st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.4,1])
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Failed classified calls by model')
  if len(bm):st.plotly_chart(px.bar(bm,x='failures',y='model',color='provider',orientation='h',hover_data=['calls','failure_rate']).update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(bm)+80),margin=dict(l=10,r=10,t=10,b=10),legend_orientation='h'),width='stretch',config=chart_cfg)
  else:st.info('No classified calls in this window.')
  st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Failed classified calls by provider')
  if len(bp):st.plotly_chart(px.bar(bp,x='failures',y='provider',color='provider',orientation='h',hover_data=['calls','failure_rate']).update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(bm)+80),margin=dict(l=10,r=10,t=10,b=10),showlegend=False),width='stretch',config=chart_cfg)
  else:st.info('No classified calls in this window.')
  st.markdown('</div>',unsafe_allow_html=True)
 with st.expander('Evidence tables (errors, models, providers)'):
  rename={'calls':'classified_calls','failures':'failed_classified_calls','failure_rate':'failure_rate_pct_of_classified'}
  st.dataframe(tel['errors'].head(15),hide_index=True,width='stretch');st.caption('Error code, message and provider are shown exactly as logged; combinations can look inconsistent in synthetic telemetry.')
  st.dataframe(tel['by_model'].sort_values('failures',ascending=False).head(15).assign(failure_rate=lambda x:x.failure_rate.round(2)).rename(columns=rename),hide_index=True,width='stretch')
  st.dataframe(bp.assign(failure_rate=bp.failure_rate.round(2)).rename(columns=rename),hide_index=True,width='stretch');st.caption('Failures by provider and by model. Unclassified events are not attributed to any model; a missing model name is shown as Unknown.')
 # Section 3: supporting metrics
 group_title('Supporting telemetry metrics');cols=st.columns(4)
 with cols[0]:kpi('Unclassified events',f"{ts['unclassified']:,}",f"{fmt_pct(ts['unclassified_pct'])} of events · excluded from success and failure rates" if ts['events'] else 'No events in scope',KPI_INFO['unclassified_events'],'unclassified telemetry present' if ts['unclassified'] else tm,tone='warn' if ts['unclassified'] else None)
 with cols[1]:kpi('P95 latency (daily trend)',f"{p95d/1000:.2f}s" if p95d==p95d else 'N/A','95th percentile of daily P95s',KPI_INFO['p95_latency'],sm(h))
 with cols[2]:kpi('Total classified calls',f"{ts['classified']:,}",f"{ts['events']:,} events in scope",KPI_INFO['classified_calls'],tm)
 with cols[3]:kpi('Successful classified calls',f"{ts['success']:,}",note(ts['success_pct'],'classified calls'),KPI_INFO['calls_success'],tm)
 with st.expander('How is P95 latency evaluated?'):
  st.markdown(f"**True P95** (card above) = 95th percentile of `responseTime` over every classified call: **{(ts['p95_ms'] or 0):,.0f} ms**.  \n**Daily-trend P95** = the chart below takes each day's P95, and the card takes the 95th percentile of those daily values: **{(p95d if p95d==p95d else 0):,.0f} ms**. These differ because a percentile of daily percentiles is not the P95 of all calls. Use the true P95 for SLA statements.  \nUnit is milliseconds as logged by the gateway.")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('P95 latency (daily)');st.plotly_chart(px.line(d,x='date',y='p95_latency_ms'),width='stretch',config=chart_cfg);st.markdown('</div>',unsafe_allow_html=True)
 with st.expander('Correlated operational alerts'):st.dataframe(synthetic_alerts(),hide_index=True,width='stretch')

def adoption():
 # V1.1: use-case view (stage, segment, active users) instead of user counts; fields follow docs/DATA_CONTRACTS.md
 full=get_apps();d=filtered_apps().head(100) if full.attrs.get('source_mode')!='workbook' else filtered_apps();mode=sm(full)
 header('User onboarding and adoption','Value realization','Measure how many use cases are onboarded, at which stage, for which segment, and how many people use them.',source=mode)
 # Canonical identity: counts use distinct application/use-case IDs; stage and status are separate dimensions (src/metrics.py).
 canon,meta=canonical_use_cases(d);n=len(canon)
 if 'created_date' in canon:compact_basis(window_for(canon.created_date),mode)
 stage=canon.get('use_case_stage',pd.Series('Unknown',index=canon.index)).map(normalize_stage);status=canon['status_category']
 seg=canon.get('segment',pd.Series('Unknown',index=canon.index)).astype(str)
 users_label,users_key,users_why=active_users_presentation(full.attrs.get('active_users_basis'))
 users_missing=full.attrs.get('active_users_basis')=='not supplied'
 share=lambda k:f"{(status==k).mean():.0%} of canonical use cases" if n else 'No use cases in scope'
 group_title('Portfolio','Stage is a portfolio stage, separate from status');cols=st.columns(3)
 with cols[0]:kpi('Use cases onboarded',n,f"Across {canon.region.nunique()} regions"+(f" · {meta['missing_id_rows']} rows without an ID not counted" if meta['missing_id_rows'] else ''),KPI_INFO['use_cases'],mode)
 with cols[1]:kpi('Sandbox use cases',int((stage=='Sandbox').sum()),'Stage: experimenting, not yet industrialized',KPI_INFO['uc_sandbox'],mode)
 with cols[2]:kpi('Industrialized use cases',int((stage=='Industrialized').sum()),'Stage: running in production',KPI_INFO['uc_industrialized'],mode)
 group_title('Status','Status field, not measured activity');cols=st.columns(4)
 with cols[0]:kpi('Active-status use cases',int((status=='Active').sum()),share('Active')+' · status field, not measured activity',KPI_INFO['active_status_use_cases'],mode)
 with cols[1]:kpi('New-status use cases',int((status=='New').sum()),share('New')+' · status field, not approval date',KPI_INFO['adoption_new'],mode)
 with cols[2]:kpi('Dormant-status use cases',int((status=='Dormant').sum()),share('Dormant')+' · no validated last-activity timestamp',KPI_INFO['dormant'],mode,tone='warn')
 with cols[3]:kpi('Onboarding-status use cases',int((status=='Onboarding').sum()),share('Onboarding')+' · status field',KPI_INFO['adoption_onboarding'],mode)
 group_title('Usage');cols=st.columns(4)
 with cols[0]:kpi(users_label,'N/A' if users_missing else f"{int(pd.to_numeric(canon.get('active_users',0),errors='coerce').fillna(0).sum()):,}",users_why,KPI_INFO[users_key],mode)
 with st.expander('Reconciliation: identity, stage and status'):
  st.markdown(f"**Rows in scope:** {meta['rows']:,} · **Canonical use cases (distinct IDs):** {meta['canonical_use_cases']:,} · **Duplicate-ID rows collapsed:** {meta['duplicate_canonical_id_count']:,} · **Rows without an ID (preserved, not counted):** {meta['missing_id_rows']:,}  \n**By stage:** "+' · '.join(f"{k} {v:,}" for k,v in meta['by_stage'].items())+"  \n**By status:** "+' · '.join(f"{k} {v:,}" for k,v in meta['by_status'].items())+f"  \n**Unknown status:** {meta['unknown_status_count']:,} (preserved, not forced into a known category)  \nStage and status are separate dimensions; each one sums to the canonical total ({'reconciled' if meta['reconciles'] else 'NOT reconciled'}). Status is not activity: no validated last-activity timestamp exists.")
 if 'created_date' in canon:
  aw=window_for(canon.created_date);dated=canon.created_date.notna();inw=filter_by_window(canon,'created_date',aw);pw=previous_window(aw);prev=filter_by_window(canon,'created_date',pw)
  group_title('Approval-based trend','Approval dates, not activity')
  with st.expander('Data basis'):st.caption('Approval-based trend · '+describe_basis(aw,'approval date',mode)+'. Approval dates are not activity; no monthly-active metric is derived from them.')
  cols=st.columns(3)
  with cols[0]:kpi('Newly approved use cases',len(inw),aw.window_label+' · approval date'+vs_previous(trend_direction(len(inw),len(prev)),aw),KPI_INFO['newly_approved'],mode)
  with cols[1]:kpi('Previous period approvals',len(prev),pw.window_label+' · approval date',KPI_INFO['newly_approved'],mode)
  with cols[2]:kpi('Use cases without approval date',int((~dated).sum()),'Not placed in any window',KPI_INFO['newly_approved'],mode,tone='warn' if (~dated).any() else None)
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Approval-based trend: newly approved use cases per 7 days');st.plotly_chart(px.bar(period_counts(canon.created_date,aw),x='period_start',y='count'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns(2)
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Segment: B2B vs B2C by stage');g=pd.DataFrame({'segment':seg,'stage':stage}).value_counts().reset_index(name='use_cases');st.plotly_chart(px.bar(g,x='stage',y='use_cases',color='segment',barmode='group',color_discrete_map={'B2B':'#1768ff','B2C':'#f2a93b'}),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Regional use cases: onboarded vs Active-status');g=canon.assign(active=status=='Active').groupby('region').agg(onboarded=('id','count'),active=('active','sum'));g=g.reindex(REGIONS+[x for x in g.index if x not in REGIONS],fill_value=0).reset_index();fig=go.Figure([go.Bar(name='Onboarded',x=g.region,y=g.onboarded,marker_color='#c6d2e2'),go.Bar(name='Active-status',x=g.region,y=g.active,marker_color='#1768ff')]);fig.update_layout(barmode='group',height=390,margin=dict(l=20,r=10,t=10,b=20),plot_bgcolor='white',legend_orientation='h');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 cols_show=[c for c in ['id','name','region','use_case_stage','segment','status','active_users','expected_daily_users','business_value','owner','platform','recertification_status'] if c in d]
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Use-case portfolio (one row per canonical ID)');st.dataframe(canon[cols_show].head(100),hide_index=True,width='stretch',height=360);st.markdown('</div>',unsafe_allow_html=True)

def chargeback():
 header('Chargeback','Financial transparency','Reconcile provider invoices with platform-attributed consumption before allocation and approval.')
 d=synthetic_charges();d['status']=d['variance'].apply(lambda v:'Review' if v>get_setting('chargeback_threshold',5) else 'Matched')
 if provider!='All':d=d[d.provider==provider]
 st.caption('Window: none (snapshot) · Source: synthetic scenario · Fixed demonstration records')
 cols=st.columns(4)
 with cols[0]:kpi('Provider invoice',f"${d.provider_bill.sum()/1000:.1f}K",'Current period',KPI_INFO['invoice'],'synthetic scenario')
 with cols[1]:kpi('Attributed usage',f"${d.platform_usage.sum()/1000:.1f}K",'NesGen / MuleSoft',KPI_INFO['attributed'],'synthetic scenario')
 with cols[2]:kpi('Unexplained amount',f"${(d.provider_bill-d.platform_usage).sum()/1000:.1f}K",'Requires evidence',KPI_INFO['unexplained'],'synthetic scenario')
 with cols[3]:kpi('Review exceptions',int((d.status=='Review').sum()),f"Threshold > {get_setting('chargeback_threshold',5)}%",KPI_INFO['exceptions'],'synthetic scenario')
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
