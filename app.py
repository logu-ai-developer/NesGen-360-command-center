from pathlib import Path
import sys,os,time,uuid,html,logging
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
from src import model_assistant
from src import error_assistant
from src import chargeback_assistant
from src.config import setting
# V1.1: KPI definitions + rule-based decision brief (src/insights.py); in-card info replaces the old bottom explainer block
from src.insights import KPI_INFO, AVAILABILITY_TARGET, build_decision_brief, executive_focus_bullets, priority_breakdown, SEVERITY_ICONS, finding_target, model_review_priority, RISK_BADGES, RISK_COLORS, REVIEW_PRIORITY_LABELS, model_attention_rank, ATTENTION_LABELS, REVIEW_BADGES, RETIREMENT_BADGES, REVIEW_COLORS, RETIREMENT_COLORS, READINESS_STATUS_COLORS, READINESS_STATUS_BADGES
from src.timewindow import WINDOW_DAYS, DEFAULT_WINDOW, resolve_window, previous_window, anchor_date, filter_by_window, describe_basis, period_counts, trend_direction, lifecycle_anchor, lifecycle_date_counts
from src.metrics import health_outcomes, fmt_pct, fmt_count, canonical_use_cases, normalize_stage, normalize_status, active_users_presentation, derived_from, NO_CLASSIFIED_NOTE
from src.storage import init as init_storage,register_model,set_setting,get_setting,sources
init_storage()

llm_model_name = str(setting("GEMINI_MODEL"))

st.set_page_config(page_title='NesGen 360°',page_icon='◉',layout='wide',initial_sidebar_state='expanded');inject_css()
from src.auth_ui import gate,user_management
from src.auth import require_admin
current_user=gate()
# Primary decision modules only. Administration, Solution design, Requirements and Demo & tests are kept as routes/functions
# but hidden from navigation (2026-10-26 review: reachable code, not in the menu). Administration still enforces require_admin().
PAGES=['Executive overview','Platform health','Model lifecycle','Chargeback','User adoption','AI assistant']
with st.sidebar:
 st.markdown('<div class="brand"><div class="brand-title">NesGen 360°</div><div class="brand-sub">Operations & Governance</div></div>',unsafe_allow_html=True)
 page=st.radio('Navigation',PAGES,label_visibility='collapsed',key='nav_page')
 st.divider();st.caption('Innovation challenge prototype');st.caption('Synthetic scenario data only · set the time window on each page')
# Decision-scope filters (Region / Environment / Provider) are hidden from the UI per the 2026-10-26 review; pages default to
# the full portfolio (Global / All / All) so every view still computes exactly as before.
region,environment,provider='Global','All','All'
# P4.1 (2026-10-26): the POC runs on the deterministic synthetic scenario telemetry; the Real/Demo toggle is removed from
# the UI. A hidden session flag ('nesgen_real_data') lets the metric-correctness tests still exercise the real pipeline.
demo=not st.session_state.get('nesgen_real_data',False)

def filtered_apps():
 d=get_apps();
 if region!='Global':d=d[d.region.astype(str).str.casefold()==region.casefold()]
 if provider!='All':d=d[pd.to_numeric(d.get(provider,0),errors='coerce').fillna(0)>0]
 if environment!='All':d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 return d

def filtered_models():
 d=get_models(demo=demo);   # demo-only POC: the whole app runs on the synthetic model inventory (real workbook stays behind the hidden nesgen_real_data flag)
 if provider!='All':d=d[d.provider.astype(str).str.contains(provider,case=False,na=False)]
 return d


def rate_tone(pct):
 # Red only when reliability is below target; green when met; neutral when the rate is unavailable.
 return None if pct is None else ('bad' if pct<AVAILABILITY_TARGET else 'ok')

def window_for(*date_series,key=DEFAULT_WINDOW):
 # One definition for every page (src/timewindow.py), anchored to the latest non-future date of the source being windowed.
 return resolve_window(key,anchor_date(*date_series))

def page_window(page_key):
 # P3: each windowed page carries its own independent time-window control (its own session state), so different pages can show different windows.
 return st.radio('Time window',list(WINDOW_DAYS),index=list(WINDOW_DAYS).index(DEFAULT_WINDOW),key=f'tw_{page_key}',horizontal=True,help='1 Month = 30 days · 3 Months = 90 · 6 Months = 180. Inventory, status, chargeback and alert views are snapshots.')

def demo_banner():
 if demo:st.markdown(f'<div class="callout"><b>DEMO SCENARIO DATA</b> {source_badge("synthetic scenario")} Illustrative synthetic scenario: telemetry on this page is deterministic synthetic demonstration data, not real telemetry.</div>',unsafe_allow_html=True)

def status_chip(label,text,color):
 # Each concept has its own labelled chip; the text and icon carry the meaning, the colour is secondary.
 return f'<span style="display:inline-block;border:1px solid {color};color:{color};border-radius:6px;padding:.05rem .45rem;margin:.15rem .35rem 0 0;font-size:.78rem"><b>{label}:</b> {html.escape(text)}</span>'

def risk_card(row,attention=''):
 # Subtle left-border indicator follows Risk only; Review and Retirement are separate chips with their own palettes.
 key=str(row.risk).casefold();color=RISK_COLORS.get(key,'#65758a');rv=str(row.review_status);rt=str(row.retirement_status);rd=str(getattr(row,'decommission_readiness_status','') or '')
 chips=status_chip('Risk',RISK_BADGES.get(key,str(row.risk)),color)+status_chip('Review',REVIEW_BADGES.get(rv,rv),REVIEW_COLORS.get(rv,'#65758a'))+status_chip('Retirement',RETIREMENT_BADGES.get(rt,rt),RETIREMENT_COLORS.get(rt,'#65758a'))
 if rd:chips+=status_chip('Decommission',READINESS_STATUS_BADGES.get(rd,rd),READINESS_STATUS_COLORS.get(rd,'#65758a'))
 st.markdown(f'<div class="finding" style="border-left-color:{color}"><div class="finding-title">{html.escape(str(row["name"]))}</div><div>{chips}</div><div class="finding-meta">{html.escape(attention) and "Attention: "+html.escape(attention) or "No attention flag"}</div></div>',unsafe_allow_html=True)

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
 a=filtered_apps();m=filtered_models();h_all=get_health(demo);c=synthetic_charges()
 header('Executive overview','Decision intelligence','Prioritize the operational, financial and governance decisions that require leadership attention.',source=sm(h_all))
 tk=page_window('exec')
 hw=window_for(h_all.date,key=tk);h=filter_by_window(h_all,'date',hw);brief=build_decision_brief(a,m,h,c,synthetic_alerts())
 canon,_=canonical_use_cases(a);aw=window_for(canon.created_date,key=tk)
 # P7: a plain-language "where you stand" line, built deterministically from the brief.
 _o=health_outcomes(h);_rate=fmt_pct(_o['success_pct']);_sev={s:sum(1 for i in brief if i['severity']==s) for s in ('Critical','High','Medium','Low')}
 if brief:
  _sevtxt=', '.join(f"{v} {k.lower()}" for k,v in _sev.items() if v)
  _summary=f"You have {len(brief)} priority action{'s' if len(brief)!=1 else ''} ({_sevtxt}). Call success rate is {_rate}. Start with: {brief[0]['title']} → {finding_target(brief[0])}."
 else:
  _summary=f"No priority actions against current thresholds. Call success rate is {_rate}."
 st.markdown(f'<div class="exec-summary"><b>Where you stand:</b> {html.escape(_summary)}</div>',unsafe_allow_html=True)
 compact_basis(hw,sm(h_all));
 with st.expander('Data basis'):
  st.caption('Telemetry · '+describe_basis(hw,'event timestamp',sm(h_all)));st.caption('Approvals · '+describe_basis(aw,'approval date',sm(a))+' · inventory, status, chargeback and alerts are snapshots, not windowed')
 group_title('Priority findings','Select a finding to open its evidence')
 if not brief:st.success('No priority findings identified.',icon='✅')
 for n,item in enumerate(brief[:5]):
  target=finding_target(item);c1,c2=st.columns([5,1.6])
  with c1:st.markdown(f'<div class="finding" style="border-left-color:{SEVERITY_COLORS.get(item["severity"],"#1768ff")}"><div class="finding-module">{html.escape(target)}</div><div class="finding-title">{SEVERITY_ICONS.get(item["severity"],"⚪")} {html.escape(item["title"])}</div><div class="finding-line">{html.escape(item["summary"])}</div><div class="finding-line"><b>Impact:</b> {html.escape(item["impact"])}</div><div class="finding-line"><b>Action:</b> {html.escape(item["recommended_action"])}</div><div class="finding-meta">{html.escape(item["severity"])} · {html.escape(item["category"])} · {html.escape(item["owner"])}</div></div>',unsafe_allow_html=True)
  with c2:st.button(f'Open {target} →',key=f'go_{n}',on_click=go_to,args=(target,),width='stretch')
 group_title('Key metrics');cols=st.columns(4)
 o=health_outcomes(h);tdir=trend_direction(o['success_pct'],health_outcomes(filter_by_window(h_all,'date',previous_window(hw)))['success_pct'],abs_tol=.5)
 with cols[0]:kpi('Call success rate',fmt_pct(o['success_pct']),(success_note(o,tdir,hw,0)),KPI_INFO['classified_success'],sm(h_all),tone=rate_tone(o['success_pct']))
 with cols[1]:kpi('Models in inventory',len(m),f"{int((m.risk=='High').sum())} high-risk reviews",KPI_INFO['models_inventory'],sm(m))
 with cols[2]:kpi('Active use cases',int((canon['status_category']=='Active').sum()),f"{(canon['status_category']=='Active').mean():.0%} of use cases have Active status" if len(canon) else 'No use cases in scope',KPI_INFO['active_status_use_cases'],sm(a))
 with cols[3]:kpi('Priority actions',len(brief),priority_breakdown(brief),KPI_INFO['priority_actions'],'synthetic scenario')
 l,r=st.columns([1.6,1])
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Usage and reliability trend');trend=h.copy();fig=go.Figure();fig.add_trace(go.Bar(x=trend.date,y=trend.requests,name='Requests',marker_color='#c6d2e2'));fig.add_trace(go.Scatter(x=trend.date,y=trend.success_rate,name='Call success %',yaxis='y2',line=dict(color='#1768ff',width=3)));fig.update_layout(height=330,margin=dict(l=10,r=10,t=15,b=5),plot_bgcolor='white',legend_orientation='h',yaxis2=dict(overlaying='y',side='right',range=[90,100]),hovermode='x unified');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Provider consumption');p=provider_consumption(a);fig=px.pie(p,names='provider',values='monthly_requests',hole=.62,color='provider',color_discrete_map=PROVIDER_COLORS);fig.update_traces(textposition='inside',textinfo='percent',hovertemplate='<b>%{label}</b><br>Monthly requests: %{value:,.0f}<br>Portfolio share: %{percent:.1%}<extra></extra>');fig.update_layout(height=345,margin=dict(l=10,r=10,t=10,b=10),paper_bgcolor='rgba(0,0,0,0)',legend=dict(y=.9,x=1.02));st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)

def lifecycle():
 tel=get_telemetry(demo=True);m0=enrich_models(filtered_models(),tel['clients']);d=m0
 header('Model Inventory & Decisions','Responsible AI governance','Model inventory and governance actions: risk, review obligations and retirement are shown separately, with accountable evidence.',source=sm(filtered_models()))
 tk=page_window('lifecycle')
 lw=resolve_window(tk,lifecycle_anchor(m0));lc=lifecycle_date_counts(m0,lw)
 compact_basis(lw,sm(filtered_models()))
 with st.expander('Data basis'):st.caption(describe_basis(lw,'lifecycle dates (review, retirement, migration)',sm(filtered_models()))+' · models with a date in the window: '+(' · '.join(f'{k} {v}' for k,v in lc.items()) or 'no lifecycle dates in this source')+' · the KPIs below are an inventory snapshot, not windowed')
 f1,f2,f3,f4=st.columns(4);risk=f1.selectbox('Risk',['All','Low','Medium','High']);cat=f2.selectbox('Category',['All','Sandbox','Industrialized','Retirement']);stage=f3.selectbox('Lifecycle stage',['All']+sorted(d.stage.dropna().unique().tolist()));search=f4.text_input('Search model or family')
 if risk!='All':d=d[d.risk==risk]
 if cat!='All':d=d[d.lifecycle_category==cat]
 if stage!='All':d=d[d.stage==stage]
 if search:d=d[d.name.astype(str).str.contains(search,case=False,na=False)|d.model_family.astype(str).str.contains(search,case=False,na=False)]
 rank=model_attention_rank(d);d=d.loc[rank.sort_values(kind='stable').index]   # high risk, overdue review, retirement candidate, then the rest; presentation order only
 inv=d.assign(attention=rank.map(ATTENTION_LABELS),risk=d.risk.astype(str).str.casefold().map(RISK_BADGES).fillna(d.risk),review_status=d.review_status.map(REVIEW_BADGES),retirement_status=d.retirement_status.map(RETIREMENT_BADGES),suggested_replacement=d.suggested_replacement.fillna(NO_CANDIDATE))
 mode=sm(filtered_models());n_local=int((m0.get('record_origin',pd.Series(dtype=str))=='locally registered').sum())
 if n_local:st.markdown(f'{source_badge("locally registered")} {n_local} model record(s) were created through the local POC registration workflow and are included below; they are not source-system records.',unsafe_allow_html=True)
 _ind=int((d.lifecycle_category=='Industrialized').sum());_sb=int((d.lifecycle_category=='Sandbox').sum());_rt=int((d.lifecycle_category=='Retirement').sum())
 st.caption(f'Inventory by lifecycle category: {_ind} Industrialized + {_sb} Sandbox + {_rt} Retirement = {_ind+_sb+_rt} total models. (Sandbox is 0 when the model inventory has no sandbox-stage models; this is separate from sandbox *use cases* on User adoption.)')
 cols=st.columns(4)
 with cols[0]:kpi('Models in inventory',len(d),'In selected scope',KPI_INFO['lifecycle_governed'],mode)
 with cols[1]:kpi('Industrialized',_ind,'Category: approved operating models',KPI_INFO['industrialized'],mode)
 with cols[2]:kpi('Sandbox',_sb,'Category: exploration / validation',KPI_INFO['lifecycle_sandbox'],mode)
 with cols[3]:kpi('Retirement',_rt,'Category: retiring or retired',KPI_INFO['retirement_category'],mode)
 st.caption('Governance actions below are separate lenses on the same inventory (review status, migration decision, replacement) — they overlap and are not a share of the total.')
 cols=st.columns(4)
 with cols[0]:kpi('Review due',int(d.lifecycle_status.astype(str).str.contains('Review',case=False).sum()),'Status: evidence refresh required',KPI_INFO['review_due'],mode)
 with cols[1]:kpi('Retirement / migrate',int(d.migration_required.astype(str).isin(['Assess','Yes']).sum()),'Migration decision: Assess or Yes',KPI_INFO['retirement'],mode)
 with cols[2]:kpi('With suggested candidate',f"{int(d.has_backup.sum())} / {len(d)}",f"{len(d)-int(d.has_backup.sum())} have no suitable candidate · not an approval",KPI_INFO['models_with_backup'],derived_from(mode),tone='ok' if len(d) and d.has_backup.all() else 'warn')
 with cols[3]:kpi('Avg retirement readiness',f"{d.decommission_readiness.mean():.0f} / 100" if len(d) else 'n/a','Mean of the 0-100 readiness scores · see scoring below',KPI_INFO['readiness'],derived_from(mode))
 with st.expander('How is the Retirement Readiness score built?'):
  st.markdown("**Retirement Readiness (0-100)** is an indicative prioritisation aid, not an authoritative or approved measure.")
  st.table(pd.DataFrame({'Contributing factor':list(SCORE_WEIGHTS),'Maximum points':list(SCORE_WEIGHTS.values()),'Scoring':['Full points when a suggested candidate exists','Candidate risk: Low 20, Medium 10 (High candidates are never suggested)','Scaled from 90 to 365 days before retirement; full points when no date is set','Evidence: Complete 20, Review due 10, Incomplete 0, not available 10']}))
  st.caption("Limitations: current-model quality is not part of the score. It does not measure migration effort, client impact, cost or approval status. A suggested candidate is derived by rule — preferring the same model family, then the same provider, then the best-scoring suitable model (a cross-provider suggestion is offered only for models that are not High-risk), with an internally available option preferred — and is never the same model, a retired or retiring model, a High-risk model, or a model with incomplete evidence. When none qualifies the field reads 'No suitable candidate identified'. Unique clients is the number of distinct API client IDs seen in telemetry, not named people. The separate green/amber/red decommission status reads like a traffic light: green = active (not retiring), amber = retiring with a suitable replacement, red = retiring with none. Replacement suitability is illustrative synthetic data, not a sourced fact.")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Model inventory and decisions');st.caption('Review candidates first: high risk + overdue review, high risk, review due, migration required, then the rest.');st.dataframe(inv[[c for c in ['attention','name','provider','model_family','lifecycle_category','stage','owner','evaluation_score','risk','review_status','retirement_status','unique_clients','suggested_replacement','replacement_risk','replacement_readiness','migration_readiness','evidence_completeness','retirement_urgency','decommission_readiness','decommission_readiness_status','replacement_availability','lifecycle_status','next_review_date','retire_date','record_origin'] if c in inv]].head(100),hide_index=True,width='stretch',height=380);st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.3,1])
 with l:
  _cdf=d.sort_values('decommission_readiness');_cfig=px.bar(_cdf,y='name',x='decommission_readiness',color='decommission_readiness_status',orientation='h',color_discrete_map=READINESS_STATUS_COLORS,title='Illustrative decommission readiness (bar length = score, colour = retire/replace status)');_cfig.update_layout(legend_title_text=None,legend_orientation='h',height=max(420,22*len(_cdf)+150),margin=dict(l=10,r=10,t=70,b=10),yaxis=dict(title=None,automargin=True),xaxis=dict(title='readiness score (0-100)'));st.plotly_chart(_cfig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
  st.caption('Colour: 🟢 active — not scheduled for retirement (no action) · 🟡 retiring, a suitable replacement is available (manageable) · 🔴 retiring with no suitable replacement (risk). Read it like a traffic light; replacement suitability is illustrative synthetic data.')
 with r:
  selected=st.selectbox('Open decision record',d.name.tolist() if len(d) else ['No records']);
  if len(d):
   row=d[d.name==selected].iloc[0];risk_card(row,ATTENTION_LABELS[int(rank[row.name])])
   cand=f"{row.suggested_replacement} ({row.replacement_basis}, risk {row.replacement_risk})" if pd.notna(row.suggested_replacement) else NO_CANDIDATE
   st.markdown("  "+NL.join(["**Owner:** "+str(row.owner)+"  ","**Lifecycle:** "+str(row.lifecycle_status)+"  ","**Risk reason:** "+str(row.risk_reason)+"  ","**Next review:** "+str(row.next_review_date)+"  ","**Suggested candidate:** "+cand+"  ","**Unique API clients:** "+("N/A" if pd.isna(row.unique_clients) else str(int(row.unique_clients)))]).strip())
   with st.expander('Decommission readiness factors'):
    st.markdown(NL.join(["Decommission status: "+str(row.decommission_readiness_status)+"  ","Replacement availability: "+("N/A" if pd.isna(row.replacement_availability) else str(row.replacement_availability))+"  ","Replacement readiness: "+str(row.replacement_readiness)+"  ","Migration readiness: "+str(row.migration_readiness)+"  ","Evidence completeness: "+str(row.evidence_completeness)+"  ","Retirement urgency: "+str(row.retirement_urgency)+"  ",f"Illustrative Decommission Readiness Score: {row.decommission_readiness:.0f}/100 (illustrative, not authoritative)"]))

 # Phase 4B: Model Evaluation Assistant. Evidence first, AI only on an explicit click, advisory only.
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Model Evaluation Assistant');st.caption('Review the evidence first. AI interpretation is optional and runs only when you select Analyze Model.')
 if len(d):
  mea_name=st.selectbox('Model',d.name.tolist(),key='mea_model');mea_row=d[d.name==mea_name].iloc[0];mea_evidence=model_assistant.build_evidence(mea_row)
  st.table(pd.DataFrame({'Evidence':list(mea_evidence)[1:],'Value':list(mea_evidence.values())[1:]}))
  if st.button('Analyze Model',key='mea_analyze'):
   try:
    with st.spinner('Interpreting the evidence above...'):st.session_state['mea_result']={'model':mea_name,'sections':model_assistant.analyze(mea_evidence,llm_model_name)}
   except Exception as exc:
    _detail=str(getattr(exc,'message',None) or exc)[:300];_k=os.getenv('GEMINI_API_KEY')
    if _k:_detail=_detail.replace(_k,'[REDACTED]')
    logging.getLogger('nesgen.agent').warning('Model assistant unavailable type=%s detail=%s',type(exc).__name__,_detail)
    st.session_state['mea_result']={'model':mea_name,'error':True}
  res=st.session_state.get('mea_result')
  if res and res['model']==mea_name:   # a result belongs to the model it was run for; changing the dropdown never calls the model
   if res.get('error'):st.warning(model_assistant.UNAVAILABLE)
   else:
    st.markdown('**AI Interpretation**')
    for key,label in model_assistant.SECTIONS:st.markdown(f"**{label}**  "+NL+res['sections'][key])
  st.caption(model_assistant.ADVISORY)
 st.markdown('</div>',unsafe_allow_html=True)

def health():
 h=get_health(demo)
 header('Platform health','Reliability engineering','Is reliability acceptable, what is failing, and what should we investigate?',source=sm(h))
 tk=page_window('health')
 hw=window_for(h.date,key=tk);d=filter_by_window(h,'date',hw);tel=get_telemetry(hw,demo);ts=tel['stats'];tm=tel['mode']
 compact_basis(hw,sm(h))
 if environment!='All' and 'environment' in d:d=d[d.environment.astype(str).str.contains(environment,case=False,na=False)]
 env_scope=f'Environment filter: {environment}' if environment!='All' else 'Environment filter: All'
 env_charts='synthetic and demo telemetry carry a per-environment breakdown, so the Environment filter narrows the charts there; the real telemetry aggregates are not broken down by environment, so on real data the Environment filter does not change this page'
 # Review item 2 (2026-10-26 follow-up): the undated-events and scope disclosures live inside Data basis, not as loose page captions.
 with st.expander('Data basis'):
  st.caption(describe_basis(hw,'event timestamp',sm(h))+' · every card, chart and table on this page uses this window')
  if ts['undated_events']:st.caption(f"{ts['undated_events']:,} events have no event timestamp, cannot be placed in a time window and are excluded from this view.")
  st.caption('Scope: KPI cards are telemetry-wide for the selected time window and are not affected by the Environment filter. Charts follow the selected time window; '+env_charts+'. Correlated operational alerts are a fixed snapshot that ignores every filter. '+env_scope+'.')
 if ts['unclassified']:
  st.markdown(f'{source_badge("unclassified telemetry present")} {ts["unclassified_pct"]:.1f}% of telemetry events could not be classified and are excluded from reliability calculations.',unsafe_allow_html=True)
  with st.expander('Learn more'):st.markdown(f"{ts['unclassified']:,} of {ts['events']:,} events ({fmt_pct(ts['unclassified_pct'])}) have no success or failure marker. They are excluded from classified-call success and failure rates and are never counted as successful.")
 note=lambda pct,what:f"{fmt_pct(pct)} of {what}" if ts['classified'] else NO_CLASSIFIED_NOTE
 p95d=d.p95_latency_ms.quantile(.95) if len(d) else float('nan');chart_cfg={'displayModeBar':False,'displaylogo':False,'responsive':True}
 # Phase 5A: Volume, Outcomes, Performance, Failure Analysis, Supporting evidence. Presentation only; every value comes from the same helpers as before.
 # Section 1: volume
 group_title('Volume','Telemetry-wide · time window only');cols=st.columns(2)
 cov=100.0*ts['classified']/ts['events'] if ts['events'] else None
 with cols[0]:kpi('Total events',fmt_count(ts['events']),'All telemetry events in scope',KPI_INFO['total_events'],tm)
 with cols[1]:kpi('Total classified calls',fmt_count(ts['classified']),f"{fmt_pct(cov)} of events classified" if cov is not None else 'No events in scope',KPI_INFO['classified_calls'],tm)
 # Section 2: outcomes (classified calls only; no latency here)
 group_title('Outcomes','Classified calls only · telemetry-wide');cols=st.columns(3)
 with cols[0]:kpi('Successful classified calls',fmt_count(ts['success']),note(ts['success_pct'],'classified calls'),KPI_INFO['calls_success'],tm)
 with cols[1]:kpi('Failed classified calls',fmt_count(ts['failed']),note(ts['failure_pct'],'classified calls'),KPI_INFO['calls_failed'],tm,tone=rate_tone(ts['success_pct']) if rate_tone(ts['success_pct'])=='bad' else None)
 with cols[2]:kpi('Call success rate',fmt_pct(ts['success_pct']),'Target ≥ 98% · not verified availability' if ts['classified'] else NO_CLASSIFIED_NOTE,KPI_INFO['calls_success_rate'],tm,tone=rate_tone(ts['success_pct']))
 oc=d.assign(total_calls=d.successful_calls+d.failed_calls).rename(columns={'total_calls':'Total Calls','successful_calls':'Successful Classified Calls','failed_calls':'Failed Classified Calls'})
 oc_fig=px.line(oc,x='date',y=['Total Calls','Successful Classified Calls','Failed Classified Calls'],color_discrete_map={'Total Calls':'#1768ff','Successful Classified Calls':'#39b98a','Failed Classified Calls':'#df4b55'}).update_layout(legend_title_text=None,yaxis_title='Classified calls',legend_orientation='h')
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Daily Classified Call Outcomes');st.caption('Selected time window and environment. Total Calls = successful + failed classified calls; unclassified events are excluded. The success-rate card above is the primary summary.');st.plotly_chart(oc_fig,width='stretch',config=chart_cfg);st.markdown('</div>',unsafe_allow_html=True)
 # Section 3: performance (event-level P95 is the SLA figure; daily values are trend context only)
 group_title('Performance','Event-level P95 is the SLA figure · daily values are trend context');cols=st.columns(3)
 peak=d.p95_latency_ms.max() if len(d) else float('nan')
 with cols[0]:kpi('P95 response time',f"{ts['p95_ms']/1000:.2f}s" if ts['p95_ms'] else 'N/A','95th percentile over classified calls · telemetry-wide',KPI_INFO['p95_true'],tm)
 with cols[1]:kpi('P95 latency (daily trend)',f"{p95d/1000:.2f}s" if p95d==p95d else 'N/A','95th percentile of daily P95s · selected time window',KPI_INFO['p95_latency'],sm(h))
 with cols[2]:kpi('Peak daily P95',f"{peak/1000:.2f}s" if peak==peak else 'N/A','Highest single-day P95 · selected time window',KPI_INFO['peak_daily_p95'],sm(h))
 with st.expander('How is P95 latency evaluated?'):
  st.markdown(f"**Event-level P95 latency** (first card) = 95th percentile of `responseTime` over every classified call: **{(ts['p95_ms'] or 0):,.0f} ms**.  \n**Daily P95 trend** = the chart below takes each day's P95, and the second card takes the 95th percentile of those daily values: **{(p95d if p95d==p95d else 0):,.0f} ms**. **Peak daily P95** is the highest of the daily values. These differ because a percentile of daily percentiles is not the P95 of all calls. Use the event-level P95 for SLA statements, never the daily values.  \nUnit is milliseconds as logged by the gateway.")
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Daily P95 trend');st.caption('Follows the selected time window. Trend context only, not an SLA figure.');st.plotly_chart(px.line(d,x='date',y='p95_latency_ms'),width='stretch',config=chart_cfg);st.markdown('</div>',unsafe_allow_html=True)
 # Section 4: failure analysis, ranked bars; coordinated only through data the telemetry really carries (model rows carry their provider)
 group_title('Failure analysis','Ranked by failed classified calls')
 bm_all=tel['by_model'].sort_values('failures',ascending=False);bp=tel['by_provider'].sort_values('failures',ascending=False);ebd=tel.get('error_breakdown')
 _err_linked=ebd is not None and len(ebd)   # synthetic/demo telemetry links errors to provider+model; real telemetry does not
 focus=st.selectbox('Focus provider',['All providers']+bp.provider.astype(str).tolist(),key='ph_provider_focus',help='Scopes the failed-calls-by-model view and, where the telemetry links errors to a provider, the error views too.')
 bm=(bm_all if focus=='All providers' else bm_all[bm_all.provider.astype(str)==focus]).head(10)
 # Scope the error code chart to the focus provider when the telemetry links errors to a provider (synthetic/demo); otherwise it is window-wide.
 if _err_linked and focus!='All providers':
  _scoped=ebd[ebd.provider.astype(str)==focus]
  er=_scoped.groupby(['error_code','error_message'],as_index=False).occurrences.sum().rename(columns={'occurrences':'occurrences'}).sort_values('occurrences',ascending=False).head(10)
 else:
  er=tel['errors'].head(10).copy()
 st.caption('Navigation: start with the provider ranking, pick a provider to see its models and (on demo telemetry) its error codes. '+('On this telemetry errors are linked to a provider and model, so the error views below follow the focus provider.' if _err_linked else 'Limitation: real telemetry does not link errors to a model or provider, so the error view is window-wide.')+' Error source/counts are shown as logged.')
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Most frequent errors');st.caption(('Failed classified calls by error code for '+focus+'.' if _err_linked and focus!='All providers' else 'All failed classified calls in scope.'))
 if len(er):
  er['error']=er.error_code.astype(str)+' · '+er.error_message.astype(str).str.slice(0,40);st.plotly_chart(px.bar(er,x='occurrences',y='error',orientation='h').update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(er)+60),margin=dict(l=10,r=10,t=10,b=10)),width='stretch',config=chart_cfg)
 else:st.info('No failed classified calls in this window.')
 with st.expander('Error breakdown by provider, model and code'):
  if _err_linked:
   st.dataframe(error_breakdown_table(ebd,focus,top=20),hide_index=True,width='stretch')
   st.caption('Real per-model failure counts for the selected window'+('' if focus=='All providers' else ' and the '+focus+' focus')+'. Failed occurrences = failed classified calls with that error code on that model. Meaning is general knowledge of standard API error codes.')
  else:
   st.dataframe(error_reference_table(tel['errors'].head(10)),hide_index=True,width='stretch')
   st.caption('Real telemetry does not link errors to a model/provider, so the window-wide error codes are shown with their general meaning.')
 st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns([1.4,1])
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Failed classified calls by model'+('' if focus=='All providers' else f' · {focus}'))
  if len(bm):st.plotly_chart(px.bar(bm,x='failures',y='model',color='provider',orientation='h',hover_data=['calls','failure_rate']).update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(bm)+80),margin=dict(l=10,r=10,t=10,b=10),legend_orientation='h'),width='stretch',config=chart_cfg)
  else:st.info('No classified calls in this window.')
  st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Failed classified calls by provider')
  if len(bp):st.plotly_chart(px.bar(bp,x='failures',y='provider',color='provider',orientation='h',hover_data=['calls','failure_rate']).update_layout(yaxis=dict(autorange='reversed',title=None),height=max(240,36*len(bm_all.head(10))+80),margin=dict(l=10,r=10,t=10,b=10),showlegend=False),width='stretch',config=chart_cfg)
  else:st.info('No classified calls in this window.')
  st.markdown('</div>',unsafe_allow_html=True)
 # Section 5: Error Analysis Assistant (Phase 5B V1). Evidence first, AI only on an explicit click, advisory and explanation only.
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Error Analysis Assistant');st.caption("Optional. Pick a provider, a model, then one of that model's error codes; Analyze Failures explains what that error means, why it typically happens, how to reduce it and what the caller can do — general knowledge of standard error codes, grounded in the observed counts. Verify against your system.")
 ebd=tel.get('error_breakdown')
 if ebd is None or not len(ebd):
  st.info('No per-model error breakdown is available for this telemetry.');ea_focus=error_assistant.make_focus()
 else:
  ea_provider=st.selectbox('Provider',sorted(ebd.provider.astype(str).unique()),key='ea_provider')
  ea_ms=sorted(ebd[ebd.provider.astype(str)==ea_provider].model.astype(str).unique())
  ea_model=st.selectbox('Model',ea_ms,key='ea_model_focus') if ea_ms else None
  ea_codes=sorted(ebd[(ebd.provider.astype(str)==ea_provider)&(ebd.model.astype(str)==str(ea_model))].error_code.astype(str).unique()) if ea_model else []
  ea_code=st.selectbox('Error code',ea_codes,key='ea_code') if ea_codes else None
  ea_focus=error_assistant.make_focus(None,ea_provider,ea_model,ea_code)
 ea_evidence=error_assistant.build_evidence(tel,d,hw,ea_focus)
 st.table(pd.DataFrame({'Evidence':list(ea_evidence),'Value':[str(v) for v in ea_evidence.values()]}))
 if st.button('Analyze Failures',key='ea_analyze'):
  try:
   with st.spinner('Interpreting the evidence above...'):st.session_state['ea_result']={'focus':ea_focus,'sections':error_assistant.analyze(ea_evidence,llm_model_name)}
  except Exception as exc:
   _detail=str(getattr(exc,'message',None) or exc)[:300];_k=os.getenv('GEMINI_API_KEY')
   if _k:_detail=_detail.replace(_k,'[REDACTED]')
   logging.getLogger('nesgen.agent').warning('Error assistant unavailable type=%s detail=%s',type(exc).__name__,_detail)
   st.session_state['ea_result']={'focus':ea_focus,'error':True}
 ea_res=st.session_state.get('ea_result')
 if ea_res and ea_res['focus']==ea_focus:   # a result belongs to the focus it ran for; changing focus hides the stale result without a new call
  if ea_res.get('error'):st.warning(error_assistant.UNAVAILABLE)
  else:
   st.markdown('**AI Interpretation**')
   for key,label in error_assistant.SECTIONS:st.markdown(f"**{label}**  "+NL+ea_res['sections'][key])
 st.caption(error_assistant.ADVISORY)
 st.markdown('</div>',unsafe_allow_html=True)
 # Section 6: supporting evidence
 group_title('Supporting evidence')
 with st.expander('View supporting evidence'):
  rename={'calls':'classified_calls','failures':'failed_classified_calls','failure_rate':'failure_rate_pct_of_classified'}
  st.dataframe(tel['errors'].head(15),hide_index=True,width='stretch');st.caption('Error code, message, category and source are shown as recorded. Synthetic/demo telemetry uses a consistent code→category taxonomy; real telemetry code/message combinations can look inconsistent.')
  st.dataframe(tel['by_model'].sort_values('failures',ascending=False).head(15).assign(failure_rate=lambda x:x.failure_rate.round(2)).rename(columns=rename),hide_index=True,width='stretch')
  st.dataframe(bp.assign(failure_rate=bp.failure_rate.round(2)).rename(columns=rename),hide_index=True,width='stretch');st.caption('Failures by provider and by model. Unclassified events are not attributed to any model; a missing model name is shown as Unknown.')
 with st.expander('Correlated operational alerts · Illustrative synthetic scenario (fixed snapshot)'):
  st.caption('Illustrative synthetic scenario: fixed demonstration alerts, not live telemetry. They do not follow the time window, the Environment filter or the Data mode.')
  st.dataframe(synthetic_alerts(),hide_index=True,width='stretch')

def adoption():
 # V1.1: use-case view (stage, segment, active users) instead of user counts; fields follow docs/DATA_CONTRACTS.md
 full=get_apps();d=filtered_apps().head(100) if full.attrs.get('source_mode')!='workbook' else filtered_apps();mode=sm(full)
 header('User onboarding and adoption','Value realization','Measure how many use cases are in the portfolio, at which stage, for which segment, and how many people use them.',source=mode)
 tk=page_window('adoption')
 # Canonical identity: counts use distinct application/use-case IDs; stage and status are separate dimensions (src/metrics.py).
 canon,meta=canonical_use_cases(d);n=len(canon)
 if 'created_date' in canon:compact_basis(window_for(canon.created_date,key=tk),mode)
 stage=canon.get('use_case_stage',pd.Series('Unknown',index=canon.index)).map(normalize_stage);status=canon['status_category']
 seg=canon.get('segment',pd.Series('Unknown',index=canon.index)).astype(str)
 users_label,users_key,users_why=active_users_presentation(full.attrs.get('active_users_basis'))
 users_missing=full.attrs.get('active_users_basis')=='not supplied'
 share=lambda k:f"{(status==k).mean():.0%} of canonical use cases" if n else 'No use cases in scope'
 group_title('Portfolio','Stage is a portfolio stage, separate from status');cols=st.columns(3)
 with cols[0]:kpi('Use cases in portfolio',n,f"Across {canon.region.nunique()} regions"+(f" · {meta['missing_id_rows']} rows without an ID not counted" if meta['missing_id_rows'] else ''),KPI_INFO['use_cases'],mode)
 with cols[1]:kpi('Sandbox use cases',int((stage=='Sandbox').sum()),'Stage: experimenting, not yet industrialized',KPI_INFO['uc_sandbox'],mode)
 with cols[2]:kpi('Industrialized use cases',int((stage=='Industrialized').sum()),'Stage: running in production',KPI_INFO['uc_industrialized'],mode)
 group_title('Status','Status field, not measured activity');cols=st.columns(4)
 with cols[0]:kpi('Active use cases',int((status=='Active').sum()),share('Active')+' · status field, not measured activity',KPI_INFO['active_status_use_cases'],mode)
 with cols[1]:kpi('New-status use cases',int((status=='New').sum()),share('New')+' · status field, not approval date',KPI_INFO['adoption_new'],mode)
 with cols[2]:kpi('Inactive use cases',int((status=='Dormant').sum()),share('Dormant')+' · status field, no validated last-activity timestamp',KPI_INFO['dormant'],mode,tone='warn')
 with cols[3]:kpi('Onboarding-status use cases',int((status=='Onboarding').sum()),share('Onboarding')+' · status field',KPI_INFO['adoption_onboarding'],mode)
 group_title('Usage');cols=st.columns(4)
 with cols[0]:kpi(users_label,'N/A' if users_missing else f"{int(pd.to_numeric(canon.get('active_users',0),errors='coerce').fillna(0).sum()):,}",users_why,KPI_INFO[users_key],mode)
 with st.expander('Reconciliation: identity, stage and status'):
  st.markdown(f"**Rows in scope:** {meta['rows']:,} · **Canonical use cases (distinct IDs):** {meta['canonical_use_cases']:,} · **Duplicate-ID rows collapsed:** {meta['duplicate_canonical_id_count']:,} · **Rows without an ID (preserved, not counted):** {meta['missing_id_rows']:,}  \n**By stage:** "+' · '.join(f"{k} {v:,}" for k,v in meta['by_stage'].items())+"  \n**By status:** "+' · '.join(f"{k} {v:,}" for k,v in meta['by_status'].items())+f"  \n**Unknown status:** {meta['unknown_status_count']:,} (preserved, not forced into a known category)  \nStage and status are separate dimensions; each one sums to the canonical total ({'reconciled' if meta['reconciles'] else 'NOT reconciled'}). Status is not activity: no validated last-activity timestamp exists.")
 if 'created_date' in canon:
  aw=window_for(canon.created_date,key=tk);dated=canon.created_date.notna();inw=filter_by_window(canon,'created_date',aw);pw=previous_window(aw);prev=filter_by_window(canon,'created_date',pw)
  group_title('Approval-based trend','Approval dates, not activity')
  with st.expander('Data basis'):st.caption('Approval-based trend · '+describe_basis(aw,'approval date',mode)+'. Approval dates are not activity; no monthly-active metric is derived from them.')
  cols=st.columns(3)
  with cols[0]:kpi('Newly approved use cases',len(inw),aw.window_label+' · approval date'+vs_previous(trend_direction(len(inw),len(prev)),aw),KPI_INFO['newly_approved'],mode)
  with cols[1]:kpi('Previous period approvals',len(prev),pw.window_label+' · approval date',KPI_INFO['newly_approved'],mode)
  with cols[2]:kpi('Use cases without approval date',int((~dated).sum()),'Not placed in any window',KPI_INFO['newly_approved'],mode,tone='warn' if (~dated).any() else None)
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Approval-based trend: newly approved use cases per 7 days');st.plotly_chart(px.bar(period_counts(canon.created_date,aw),x='period_start',y='count'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 l,r=st.columns(2)
 with l:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Segment: B2B vs B2C by stage');g=pd.DataFrame({'segment':seg,'stage':stage}).value_counts().reset_index(name='use_cases');st.plotly_chart(px.bar(g,x='stage',y='use_cases',color='segment',barmode='group',color_discrete_map={'B2B':'#1768ff','B2C':'#f2a93b'},text='use_cases',pattern_shape='segment',pattern_shape_map={'B2B':'','B2C':'/'}).update_traces(textposition='outside'),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
 with r:
  st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Regional use cases: in portfolio vs Active-status');g=canon.assign(active=status=='Active').groupby('region').agg(onboarded=('id','count'),active=('active','sum'));g=g.reindex(REGIONS+[x for x in g.index if x not in REGIONS],fill_value=0).reset_index();fig=go.Figure([go.Bar(name='In portfolio',x=g.region,y=g.onboarded,marker_color='#c6d2e2',text=g.onboarded,textposition='outside'),go.Bar(name='Active-status',x=g.region,y=g.active,marker_color='#1768ff',text=g.active,textposition='outside')]);fig.update_layout(barmode='group',height=390,margin=dict(l=20,r=10,t=20,b=20),plot_bgcolor='white',legend_orientation='h');st.plotly_chart(fig,width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True});st.markdown('</div>',unsafe_allow_html=True)
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
 # Chargeback Reconciliation Assistant: evidence first, AI only on an explicit click, advisory and explanation only. Routed team is rule-based (computed in the evidence), not decided by the model.
 st.markdown('<div class="panel">',unsafe_allow_html=True);panel_title('Chargeback Reconciliation Assistant');st.caption("Optional. Pick a provider (or the whole portfolio); Analyze Reconciliation explains the invoice-vs-attributed variance in plain language and routes the next step: provider billing log higher than MuleSoft-attributed usage → the Interface team (MuleSoft API Manager layer); lower → the Azure / Microsoft provider billing team. Advisory only; amounts are a synthetic scenario.")
 cb_thr=get_setting('chargeback_threshold',5);cb_all=synthetic_charges()
 cb_provider=st.selectbox('Provider focus',['All providers']+cb_all.provider.astype(str).tolist(),key='cb_provider_focus')
 cb_focus=chargeback_assistant.make_focus(None if cb_provider=='All providers' else cb_provider)
 cb_evidence=chargeback_assistant.build_evidence(cb_all,cb_focus,cb_thr)
 st.table(pd.DataFrame({'Evidence':list(cb_evidence),'Value':[str(v) for v in cb_evidence.values()]}))
 if st.button('Analyze Reconciliation',key='cb_analyze'):
  try:
   with st.spinner('Interpreting the reconciliation evidence above...'):st.session_state['cb_result']={'focus':cb_focus,'sections':chargeback_assistant.analyze(cb_evidence,llm_model_name)}
  except Exception as exc:
   _detail=str(getattr(exc,'message',None) or exc)[:300];_k=os.getenv('GEMINI_API_KEY')
   if _k:_detail=_detail.replace(_k,'[REDACTED]')
   logging.getLogger('nesgen.agent').warning('Chargeback assistant unavailable type=%s detail=%s',type(exc).__name__,_detail)
   st.session_state['cb_result']={'focus':cb_focus,'error':True}
 cb_res=st.session_state.get('cb_result')
 if cb_res and cb_res['focus']==cb_focus:   # a result belongs to the focus it ran for; changing focus hides the stale result without a new call
  if cb_res.get('error'):st.warning(chargeback_assistant.UNAVAILABLE)
  else:
   st.markdown('**AI Interpretation**')
   for key,label in chargeback_assistant.SECTIONS:st.markdown(f"**{label}**  "+NL+cb_res['sections'][key])
 st.caption(chargeback_assistant.ADVISORY)
 st.markdown('</div>',unsafe_allow_html=True)

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
