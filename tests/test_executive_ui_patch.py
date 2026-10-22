from pathlib import Path
import ast

def test_patch_module_compiles():
    root=Path(__file__).resolve().parents[1]
    ast.parse((root/'src/executive_ui.py').read_text(encoding='utf-8'))

def test_required_behaviors_present():
    text=(Path(__file__).resolve().parents[1]/'src/executive_ui.py').read_text(encoding='utf-8')
    assert "Today's focus points in bulletin" in text
    assert 'class="callout"' not in text
    assert "key='priority_actions_toggle'" in text
    assert "key='hide_actions'" in text
    assert "st.session_state.get('exec_actions_open',False)" in text
    assert "'total_requests','Total requests'" in text
    assert "'successful_requests','Successful requests (HTTP 200 OK)'" in text
    assert "'failed_requests','Failed requests (non-200/error)'" in text
    assert "Path(DATA)/'LogAnalytics'" in text
    assert 'month_start=now.replace(day=1)' in text
