from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.storage import init
from src.usage import init as usage_init
from src.data import DATA,DB

def main():
    for folder in ['LogAnalytics','NewRelic']:(DATA/folder).mkdir(parents=True,exist_ok=True)
    init();usage_init()
    from src.storage import connect
    from src.data import synthetic_apps,synthetic_models,synthetic_health,synthetic_charges,synthetic_alerts
    with connect() as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table,loader in [('applications',synthetic_apps),('models',synthetic_models),('platform_health_daily',synthetic_health),('provider_charges',synthetic_charges),('operational_alerts',synthetic_alerts)]:
            if table not in tables:loader().to_sql(table,c,index=False,if_exists='fail')
    print('Operational schema ready:',DB.name)
if __name__=='__main__':main()
