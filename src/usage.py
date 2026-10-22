"""Durable per-provider-call reservations. Limits include failed and in-flight calls."""
import sqlite3,time,uuid
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from src.data import DB
from src.config import setting
class RateLimitError(RuntimeError):pass

def init():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB,timeout=15) as c:
        c.execute('CREATE TABLE IF NOT EXISTS agent_usage(id INTEGER PRIMARY KEY,request_id TEXT UNIQUE,session_id TEXT,requested_at TEXT,status TEXT)')
        required={'provider':'TEXT','model':'TEXT','estimated_input_tokens':'INTEGER','actual_input_tokens':'INTEGER','output_tokens':'INTEGER','tool_names':'TEXT','error_category':'TEXT','duration_ms':'INTEGER','retry_count':'INTEGER DEFAULT 0'}
        columns={r[1] for r in c.execute('PRAGMA table_info(agent_usage)')}
        for name,kind in required.items():
            if name not in columns:c.execute(f'ALTER TABLE agent_usage ADD COLUMN {name} {kind}')
        c.execute('CREATE TABLE IF NOT EXISTS provider_calls(id TEXT PRIMARY KEY,created REAL,quota_day TEXT,model TEXT,reserved INTEGER,actual INTEGER,status TEXT)')

def reserve(model,estimated):
    init();now=time.time();day=datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    # Include output allowance and retain reservations when calls fail or processes exit.
    with sqlite3.connect(DB,timeout=15) as c:
        c.execute('BEGIN IMMEDIATE')
        minute=c.execute('SELECT COUNT(*),COALESCE(SUM(MAX(reserved,COALESCE(actual,0))),0) FROM provider_calls WHERE created>?',(now-60,)).fetchone()
        daily=c.execute('SELECT COUNT(*) FROM provider_calls WHERE quota_day=?',(day,)).fetchone()[0]
        if minute[0]>=setting('AGENT_REQUESTS_PER_MINUTE'):raise RateLimitError('Project-wide application RPM limit reached. Wait one minute.')
        if daily>=setting('AGENT_REQUESTS_PER_DAY'):raise RateLimitError('Application daily provider-call limit reached.')
        if minute[1]+estimated>setting('AGENT_TOKENS_PER_MINUTE'):raise RateLimitError('Application token reservation limit reached.')
        ident=uuid.uuid4().hex;c.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(ident,now,day,model,int(estimated),None,'started'))
    return ident

def complete(ident,actual,status):
    with sqlite3.connect(DB,timeout=15) as c:c.execute('UPDATE provider_calls SET actual=?,status=? WHERE id=?',(int(actual),status,ident))

def summary():
    init();day=datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
    with sqlite3.connect(DB,timeout=15) as c:
        today=c.execute('SELECT COUNT(*) FROM provider_calls WHERE quota_day=?',(day,)).fetchone()[0]
        minute=c.execute('SELECT COALESCE(SUM(MAX(reserved,COALESCE(actual,0))),0) FROM provider_calls WHERE created>?',(time.time()-60,)).fetchone()[0]
    return {'today':today,'tokens60':minute}

def begin(session,model,estimate):
    init();rid=str(uuid.uuid4())
    with sqlite3.connect(DB) as c:c.execute('INSERT INTO agent_usage(request_id,session_id,requested_at,provider,model,estimated_input_tokens,status) VALUES(?,?,?,?,?,?,?)',(rid,session,datetime.now(timezone.utc).isoformat(),'Gemini',model,estimate,'started'))
    return rid,time.perf_counter()

def finish(rid,start,status,inp=0,out=0,tools='',error='',retry=0):
    with sqlite3.connect(DB) as c:c.execute('UPDATE agent_usage SET status=?,actual_input_tokens=?,output_tokens=?,tool_names=?,error_category=?,duration_ms=?,retry_count=? WHERE request_id=?',(status,inp,out,tools,error,int((time.perf_counter()-start)*1000),retry,rid))
