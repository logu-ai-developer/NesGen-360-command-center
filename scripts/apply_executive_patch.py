from pathlib import Path
p=Path('app.py')
if not p.exists():raise SystemExit('Run from repository root: app.py not found.')
s=p.read_text(encoding='utf-8')
start=s.find('def executive():')
end=s.find('\ndef lifecycle():',start)
if start<0 or end<0:raise SystemExit('Current Executive Overview block was not found. No file changed.')
old=s[start:end]
if 'Today’s focus:' not in old or "panel_title('Leadership action queue')" not in old:
    raise SystemExit('app.py does not match the reviewed V1.0 baseline. No file changed.')
replacement="""def executive():
 from src.executive_ui import render_executive
 render_executive()
"""
backup=p.with_suffix('.py.executive-v1-backup')
if not backup.exists():backup.write_text(s,encoding='utf-8')
p.write_text(s[:start]+replacement+s[end:],encoding='utf-8')
print('Updated app.py. Backup:',backup)
