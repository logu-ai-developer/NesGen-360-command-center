from pathlib import Path
import os,sqlite3,uuid
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; DATA=Path(os.getenv('NESGEN_DATA_DIR',ROOT/'data')); DB=Path(os.getenv('NESGEN_SQLITE_PATH',DATA/'nesgen360.db')); DUCK=DATA/'nesgen360.duckdb'
MODEL=DATA/'Model details Page.xlsx'; HUB=DATA/'ML_HUB_synthetic_5000rows.xlsx'; NR=str(DATA/'NewRelic'/'*.parquet').replace('\\','/')
SCHEMA='''CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY,month TEXT UNIQUE,requests_m REAL,active_apps INTEGER,cost_k REAL,success_rate REAL,p95_latency REAL);CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,name TEXT,provider TEXT,stage TEXT,owner TEXT,evaluation_score INTEGER,risk TEXT,environment TEXT);CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,severity TEXT,title TEXT,source TEXT,metric TEXT,owner TEXT,status TEXT,environment TEXT);CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY,name TEXT,region TEXT,environment TEXT,status TEXT,monthly_requests INTEGER,owner TEXT);CREATE TABLE IF NOT EXISTS charges(id INTEGER PRIMARY KEY,provider TEXT,period TEXT,provider_bill REAL,platform_usage REAL,variance REAL,status TEXT);'''
def con(path=None):
 p=Path(path or DB);p.parent.mkdir(parents=True,exist_ok=True);return sqlite3.connect(p,check_same_thread=False)
def query(sql,p=(),path=None):
 with con(path) as c:return pd.read_sql_query(sql,c,params=p)
def bootstrap(reset=False,path=None,import_excel=True):
 target=Path(path or DB)
 with con(target) as c:
  if reset:c.executescript('DROP TABLE IF EXISTS metrics;DROP TABLE IF EXISTS models;DROP TABLE IF EXISTS alerts;DROP TABLE IF EXISTS applications;DROP TABLE IF EXISTS charges;')
  c.executescript(SCHEMA)
  if c.execute('select count(*) from metrics').fetchone()[0]==0:c.executemany('insert into metrics(month,requests_m,active_apps,cost_k,success_rate,p95_latency) values(?,?,?,?,?,?)',[('May',52,38,41,98.7,2.1),('Jun',61,42,47,98.4,2.3),('Jul',68,49,53,98.1,2.5),('Aug',73,54,58,98.0,2.6),('Sep',81,61,64,97.9,2.7),('Oct',92,72,69,97.8,2.8)])
  if c.execute('select count(*) from models').fetchone()[0]==0:c.executemany('insert into models values(?,?,?,?,?,?,?,?)',[('MOD-104','Orion Reasoning','Azure','Industrialized','Core AI Platform',91,'Low','Production'),('MOD-109','Terra Chat','AWS','Sandbox validation','Model Enablement',84,'Medium','Sandbox'),('MOD-112','Luna Multimodal','GCP','Exploration','Innovation Team',78,'Medium','Sandbox'),('MOD-098','Atlas Text','Azure','Retirement planned','Core AI Platform',69,'High','Production')])
  if c.execute('select count(*) from alerts').fetchone()[0]==0:c.executemany('insert into alerts values(?,?,?,?,?,?,?,?)',[('ALT-2071','Critical','Elevated failure rate in pre-production','Log Analytics','8.6% failures','Platform Support','Open','Pre-production'),('ALT-2064','High','Provider and MuleSoft usage variance','Reconciliation','7.4% variance','FinOps','Investigating','Production'),('ALT-2058','Medium','Model evaluation nearing expiry','Lifecycle','12 days remaining','Model Enablement','Assigned','Production')])
  if c.execute('select count(*) from applications').fetchone()[0]==0:c.executemany('insert into applications values(?,?,?,?,?,?,?)',[('APP-101','Recipe Assistant','Europe','Production','Active',420000,'Regional Product'),('APP-102','Service Desk Copilot','Asia','Production','Active',315000,'Employee Services'),('APP-103','Document Intelligence','Americas','Pre-production','Onboarding',64000,'Supply Chain'),('APP-104','Marketing Studio','AMEA','Production','Dormant',0,'Marketing')])
  if c.execute('select count(*) from charges').fetchone()[0]==0:c.executemany('insert into charges(provider,period,provider_bill,platform_usage,variance,status) values(?,?,?,?,?,?)',[('Azure','2026-10',128400,126920,1.15,'Matched'),('AWS','2026-10',89640,83010,7.4,'Review'),('GCP','2026-10',61250,60080,1.91,'Matched')])
  c.commit()
  if import_excel and MODEL.exists():pd.read_excel(MODEL).to_sql('model_details_table',c,if_exists='replace',index=False)
  if import_excel and HUB.exists():pd.read_excel(HUB).to_sql('onboarding_table',c,if_exists='replace',index=False)
 return target
def exists(t,path=None):return not query("select name from sqlite_master where type='table' and name=?",(t,),path).empty
def models(provider='All',risk='All',stage='All',search=''):
 if exists('model_details_table'):
  sql='SELECT rowid id,"Model Name" name,"Cloud Provider" provider,governance_stage stage,accountable_owner owner,evaluation_score,risk,lifecycle_status,lifecycle_risk,risk_reason,migration_required,next_review_date,"Retire Date" retire_date,"Model Family" model_family FROM model_details_table WHERE 1=1';p=[]
  if provider!='All':sql+=' AND "Cloud Provider" LIKE ?';p.append('%'+provider+'%')
  if risk!='All':sql+=' AND risk=?';p.append(risk)
  if stage!='All':sql+=' AND governance_stage=?';p.append(stage)
  if search:sql+=' AND lower("Model Name") LIKE ?';p.append('%'+search.lower()+'%')
  return query(sql+' ORDER BY evaluation_score DESC',p)
 sql='SELECT *,NULL lifecycle_status,NULL lifecycle_risk,NULL risk_reason,NULL migration_required,NULL next_review_date,NULL retire_date,NULL model_family FROM models WHERE 1=1';p=[]
 if provider!='All':sql+=' AND provider=?';p.append(provider)
 if risk!='All':sql+=' AND risk=?';p.append(risk)
 if stage!='All':sql+=' AND stage=?';p.append(stage)
 if search:sql+=' AND lower(name) LIKE ?';p.append('%'+search.lower()+'%')
 return query(sql+' ORDER BY evaluation_score DESC',p)
def apps(region='Global'):
 if exists('onboarding_table'):
  sql='SELECT "Application ID" id,"APM Name" name,Region region,coalesce("LATEST STATUS OF USE CASE","Use Case Status") status,"Expected Daily Users" expected_daily_users,"Business Value" business_value,"Functional Owner" owner,Platform platform,Function function,"RECERTIFICATION STATUS" recertification_status FROM onboarding_table'
  return query(sql) if region=='Global' else query(sql+' WHERE Region=?',(region,))
 return query('select * from applications') if region=='Global' else query('select * from applications where region=?',(region,))
def alerts(env='All'):return query("select * from alerts order by case severity when 'Critical' then 1 when 'High' then 2 else 3 end") if env=='All' else query('select * from alerts where environment=?',(env,))
def charges(provider='All'):return query('select * from charges') if provider=='All' else query('select * from charges where provider=?',(provider,))
def metrics():return query('select * from metrics order by id')
def add_model(v):
 with con() as c:c.execute('insert into models values(?,?,?,?,?,?,?,?)',v);c.commit()
def analytics(env='All'):
 import duckdb
 folder=DATA/'NewRelic'; has=folder.exists() and any(folder.glob('*.parquet')); src=f"read_parquet('{NR}',union_by_name=true)" if has else ('new_relic_log_table' if DUCK.exists() else None)
 if not src:return None,pd.DataFrame(),pd.DataFrame()
 c=duckdb.connect(str(DUCK) if DUCK.exists() else ':memory:',read_only=DUCK.exists());where='';p=[]
 if env!='All':where=' WHERE upper("Attributes.BusinessKeys.environment")=?';p=[env.upper().replace('PRE-PRODUCTION','NONPROD')]
 one=c.execute(f'SELECT count(*) requests,round(quantile_cont("Attributes.BusinessKeys.responseTime",.95),0) p95,round(100.0*sum(CASE WHEN coalesce("SeverityText",\'INFO\') NOT IN (\'ERROR\',\'FATAL\') THEN 1 ELSE 0 END)/count(*),2) success,round(sum("Attributes.BusinessKeys.total_cost"),2) cost FROM {src}{where}',p).df().iloc[0].to_dict()
 prov=c.execute(f'SELECT "Attributes.BusinessKeys.provider" provider,count(*) requests FROM {src}{where} GROUP BY 1 ORDER BY 2 DESC',p).df()
 daily=c.execute(f'SELECT substr("Timestamp_1",1,10) day,count(*) requests,round(avg("Attributes.BusinessKeys.responseTime"),0) latency FROM {src}{where} GROUP BY 1 ORDER BY 1',p).df();c.close();return one,prov,daily
def answer(q):
 q=q.lower()
 if any(x in q for x in ('variance','cost','charge')):return 'Review AWS case ALT-2064. Synthetic variance is 7.4%, above the 5% review threshold.'
 if any(x in q for x in ('model','govern')):return 'Prioritize High lifecycle risk, review-due evidence and near-retirement models; assign migration ownership.'
 return 'Address the critical pre-production reliability alert first, followed by the AWS reconciliation exception.'
