"""Explicit local registration/settings reset; never deletes workbooks or telemetry."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.storage import init,connect
p=argparse.ArgumentParser();p.add_argument('--confirm-reset',action='store_true');args=p.parse_args()
if not args.confirm_reset:raise SystemExit('No changes made. Pass --confirm-reset to clear local model registrations and settings. Usage counters are retained.')
init()
with connect() as c:
    c.execute('DELETE FROM local_models');c.execute('DELETE FROM app_settings')
print('Local registrations/settings reset. Source files and usage counters retained.')
