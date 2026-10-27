"""Non-secret configuration. The API key is read only from the OS environment."""
import os
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
DEFAULTS={'GEMINI_MODEL':'gemini-3.5-flash-lite','AGENT_REQUESTS_PER_MINUTE':8,'AGENT_REQUESTS_PER_DAY':300,'AGENT_TOKENS_PER_MINUTE':100000,'AGENT_MAX_INPUT_TOKENS':6000,'AGENT_MAX_OUTPUT_TOKENS':600,'AGENT_MAX_TOOL_ROUNDS':6,'AGENT_MAX_HISTORY_MESSAGES':6,'AGENT_MAX_RETRIES':0,'AGENT_COOLDOWN_SECONDS':8,'AGENT_REQUEST_TIMEOUT_SECONDS':60}
def setting(key,default=None):
    if key in os.environ:
        value=os.environ[key]
    else:
        try:
            with (ROOT/'.streamlit/secrets.toml').open('rb') as f: value=tomllib.load(f).get(key,DEFAULTS.get(key,default))
        except FileNotFoundError:value=DEFAULTS.get(key,default)
    expected=DEFAULTS.get(key,default)
    if isinstance(expected,int):return int(value)
    return value
