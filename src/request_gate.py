"""Process-local session gate. No background model thread or automatic retry."""
import threading
_MUTEX=threading.Lock()
_ACTIVE=set()
def acquire(session):
    with _MUTEX:
        if session in _ACTIVE:return False
        _ACTIVE.add(session);return True
def release(session):
    with _MUTEX:_ACTIVE.discard(session)
def active(session):
    with _MUTEX:return session in _ACTIVE

def queue_request(state,prompt,scope,model,now):
    if state.get('agent_busy') or active(state['agent_session']):return False
    if now<state.get('agent_cooldown_until',0):return False
    if not isinstance(prompt,str) or not prompt.strip():return False
    state['agent_pending']={'prompt':prompt.strip(),'scope':dict(scope),'model':model}
    state['agent_busy']=True
    return True
