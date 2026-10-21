from pathlib import Path
import sys,os,importlib.metadata
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if sys.version_info<(3,11):raise SystemExit('Python 3.11+ required.')
from src.config import setting
from src.data import HUB_XLSX,MODEL_XLSX,DATA
print('Python:',sys.version.split()[0]);print('Configured model:',setting('GEMINI_MODEL'));print('Gemini key configured:',bool(os.getenv('GEMINI_API_KEY')))
for name in ['streamlit','google-genai','duckdb','pandas','pyarrow']:print(name,importlib.metadata.version(name))
print('ML Hub workbook:',HUB_XLSX.exists());print('Model workbook:',MODEL_XLSX.exists())
for name in ['LogAnalytics','NewRelic']:print(name,'Parquet files:',len(list((DATA/name).glob('*.parquet'))))
