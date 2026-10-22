"""Executive Overview V1 UI. All controls on this page are local to their panel."""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from src.components import header
from src.data import get_apps,get_models,get_health,synthetic_alerts,DATA,ENVS
from src.provider import PROVIDER_COLORS

FOCUS_POINTS=[
    'Protect pre-production reliability.',
    'Explain the current provider-consumption variance.',
    'Assign ownership for models approaching review or retirement.',
]

def _metric_card(label,value,note,calculation,source,key):
    with st.container(border=True):
        left,right=st.columns([8,1])
        left.caption(label);left.markdown(f'## {value}');left.caption(note)
        with right:
            with st.popover('ⓘ',help='How this metric is calculated'):
                st.markdown('**How this value was calculated**')
                st.write(calculation)
                st.markdown('**Source**')
                st.write(source)

def _date_series(frame,column):
    return pd.to_datetime(frame[column],errors='coerce',utc=True).dt.tz_localize(None)

def _trend_data(health,start,end,environments):
    d=health.copy();d['date']=_date_series(d,'date')
    d=d[d.date.between(start,end+pd.Timedelta(days=1),inclusive='left')]
    if 'environment' in d and environments:
        d=d[d.environment.astype(str).isin(environments)]
    d['total_requests']=pd.to_numeric(d.requests,errors='coerce').fillna(0).clip(lower=0)
    rate=pd.to_numeric(d.success_rate,errors='coerce').fillna(0).clip(0,100)/100
    d['successful_requests']=(d.total_requests*rate).round()
    d['failed_requests']=(d.total_requests-d.successful_requests).clip(lower=0)
    return d.sort_values('date')

def _trend_chart(d):
    fig=go.Figure()
    for field,label,color in [
        ('total_requests','Total requests','#64748b'),
        ('successful_requests','Successful requests (HTTP 200 OK)','#10a36d'),
        ('failed_requests','Failed requests (non-200/error)','#e5484d')]:
        fig.add_trace(go.Scatter(x=d.date,y=d[field],name=label,mode='lines+markers',
            line=dict(color=color,width=3),marker=dict(size=7),
            customdata=d[['total_requests','successful_requests','failed_requests']],
            hovertemplate='<b>%{x|%d %b %Y}</b><br>'+label+': %{y:,.0f}<br>Total: %{customdata[0]:,.0f}<br>Successful: %{customdata[1]:,.0f}<br>Failed: %{customdata[2]:,.0f}<extra></extra>'))
    fig.update_layout(height=365,margin=dict(l=10,r=10,t=10,b=100),plot_bgcolor='white',
        hovermode='x unified',legend=dict(orientation='h',y=-0.22,yanchor='top',x=0,xanchor='left',font=dict(size=11),bgcolor='rgba(0,0,0,0)'),
        xaxis_title=None,yaxis_title='Request count')
    return fig

def _la_provider_mtd(start,end,environments):
    """Aggregate Log Analytics events by a recognized provider column, without guessing."""
    files=sorted((Path(DATA)/'LogAnalytics').glob('*.parquet'))
    if not files:return None,'Synthetic fallback: Log Analytics Parquet not present'
    try:
        import duckdb
        with duckdb.connect(':memory:',config={'memory_limit':'512MB','threads':'2'}) as c:
            c.read_parquet([str(p) for p in files],union_by_name=True).create_view('la')
            cols={r[0] for r in c.execute('DESCRIBE la').fetchall()}
            time_col=next((x for x in ['TimeGenerated','Timestamp','timestamp'] if x in cols),None)
            provider_col=next((x for x in ['provider_s','Provider_s','provider','Provider','cloudProvider_s'] if x in cols),None)
            env_col=next((x for x in ['environment_s','Environment_s','environment','Environment'] if x in cols),None)
            if not time_col or not provider_col:return None,'Synthetic fallback: approved Log Analytics time/provider columns are unavailable'
            sql=f'''SELECT CAST("{provider_col}" AS VARCHAR) provider,COUNT(*) requests
                    FROM la WHERE TRY_CAST("{time_col}" AS TIMESTAMP)>=? AND TRY_CAST("{time_col}" AS TIMESTAMP)<?'''
            params=[start.to_pydatetime(),(end+pd.Timedelta(days=1)).to_pydatetime()]
            if environments and env_col:
                sql+=' AND CAST("'+env_col+'" AS VARCHAR) IN ('+','.join('?' for _ in environments)+')';params+=environments
            sql+=' GROUP BY 1 ORDER BY 2 DESC'
            out=c.execute(sql,params).df()
        out=out[out.provider.notna() & out.provider.ne('')]
        return out,'Log Analytics Parquet: event counts by provider'
    except Exception as exc:
        return None,'Synthetic fallback: Log Analytics source rejected ('+type(exc).__name__+')'

def _synthetic_provider():
    return pd.DataFrame({'provider':['Azure','AWS','GCP'],'requests':[76500000,60400000,38000000]})

def _provider_chart(d):
    fig=px.pie(d,names='provider',values='requests',hole=.62,color='provider',color_discrete_map=PROVIDER_COLORS)
    fig.update_traces(textposition='inside',textinfo='percent',hovertemplate='<b>%{label}</b><br>Requests: %{value:,.0f}<br>Share: %{percent:.1%}<extra></extra>')
    fig.update_layout(height=365,margin=dict(l=5,r=5,t=5,b=5),paper_bgcolor='rgba(0,0,0,0)',legend=dict(y=.9,x=1.02))
    return fig

def render_executive():
    header('Executive overview','Decision intelligence','Prioritize the operational, financial and governance decisions that require leadership attention.')
    with st.expander("Today's focus points in bulletin",expanded=False):
        for point in FOCUS_POINTS:st.markdown('• '+point)

    apps=get_apps();models=get_models();health=get_health();alerts=synthetic_alerts()
    health_dates=_date_series(health,'date').dropna();latest=health_dates.max().normalize() if not health_dates.empty else pd.Timestamp.now().normalize()
    default_start=max(health_dates.min().normalize(),latest-pd.Timedelta(days=6)) if not health_dates.empty else latest-pd.Timedelta(days=6)

    cards=st.columns(4)
    with cards[0]:
        _metric_card('Platform availability',f"{pd.to_numeric(health.success_rate,errors='coerce').mean():.2f}%",'Selected telemetry snapshot',
            'Successful HTTP 200 OK calls ÷ total calls × 100. All other response outcomes are failed calls.',
            'New Relic telemetry: total calls and HTTP 200 OK responses.','availability')
    with cards[1]:
        _metric_card('Governed models',len(models),f"{int(models.risk.astype(str).str.casefold().eq('high').sum())} high-risk reviews",
            'Count of model records in the current governed model catalog.',
            'Model details page/workbook across all providers, plus locally registered models.','models')
    with cards[2]:
        status=apps.status.astype(str).str.casefold()
        active=int(status.isin(['active','operational']).sum())
        _metric_card('Monthly active apps',active,'Status-based signal',
            'Applications whose normalized current status is exactly Active or Operational.',
            'ML Hub application portfolio. This is status-based, not measured user activity.','apps')
    with cards[3]:
        priority=len(alerts)
        _metric_card('Priority actions',priority,'Click below to show or hide queue',
            'Count of current priority scenario records presented in the action queue.',
            'Operational alerts, chargeback scenarios and model-lifecycle review scenarios.','actions')
        if st.button('Show / hide action queue',key='priority_actions_toggle',type='primary',width='stretch'):
            st.session_state.exec_actions_open=not st.session_state.get('exec_actions_open',False)

    left,right=st.columns([1.65,1])
    with left:
        with st.container(border=True):
            title_col, filter_col = st.columns([4, 1])
            with title_col:
                st.subheader('Usage and reliability trend')
            with filter_col:
                with st.popover('Filters', width='stretch'):
                    selected_dates = st.date_input('Period', value=(default_start.date(), latest.date()), max_value=latest.date(), key='exec_trend_period')
                    env_options = sorted(health.environment.dropna().astype(str).unique()) if 'environment' in health else ENVS
                    environments = st.multiselect('Environment', env_options, default=env_options, key='exec_trend_env')
                    model_options = sorted(models.name.dropna().astype(str).unique())
                    selected_models = st.multiselect('Models', model_options, default=model_options, placeholder='Search and select models', key='exec_trend_models')
            if isinstance(selected_dates, (tuple, list)):
                start = pd.Timestamp(selected_dates[0]) if selected_dates else default_start
                end = pd.Timestamp(selected_dates[-1]) if selected_dates else latest
            else:
                start = end = pd.Timestamp(selected_dates)
            trend=_trend_data(health,start,end,environments)
            if not selected_models:st.info('Select at least one model. Current daily health adapter is not model-granular, so model selection is displayed but cannot narrow this aggregate.')
            elif trend.empty:st.warning('No reliability records match the selected period and environment.')
            else:st.plotly_chart(_trend_chart(trend),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
            st.caption('Total, successful and failed request counts use one request axis. Successful + failed equals total for every plotted date.')

    with right:
        with st.container(border=True):
            st.subheader('Provider consumption')
            now=pd.Timestamp.now(tz='UTC').tz_localize(None).normalize();month_start=now.replace(day=1)
            pdates=st.date_input('Period',value=(month_start.date(),now.date()),max_value=now.date(),key='exec_provider_period')
            penvs=st.multiselect('Environment',ENVS,default=ENVS,key='exec_provider_env')
            if isinstance(pdates,(tuple,list)) and len(pdates)==2:pstart,pend=map(pd.Timestamp,pdates)
            else:pstart=pend=pd.Timestamp(pdates)
            pdata,source=_la_provider_mtd(pstart,pend,penvs)
            if pdata is None or pdata.empty:pdata=_synthetic_provider()
            st.plotly_chart(_provider_chart(pdata),width='stretch',config={'displayModeBar':False,'displaylogo':False,'responsive':True})
            st.caption('Source: '+source+'. Default period is month-to-date; users can change the period and environment.')

    if st.session_state.get('exec_actions_open',False):
        with st.container(border=True):
            title_col,close_col=st.columns([8,1])
            title_col.subheader('Leadership action queue')
            if close_col.button('Hide',key='hide_actions'):st.session_state.exec_actions_open=False;st.rerun()
            st.dataframe(alerts,hide_index=True,width='stretch')
