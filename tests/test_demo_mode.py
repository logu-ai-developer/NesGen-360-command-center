"""Demo Scenario Data mode: swaps only Executive telemetry metrics and Platform Health; real data is never touched."""
import re
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import data, storage
from src.timewindow import WINDOW_DAYS
from tests.test_phase1_metrics import APP, S, F, no_gemini, write_telemetry  # noqa: F401
from tests.test_phase2_time import card

KEYS = ('Classified-call success rate', 'Failed classified calls', 'Unclassified events', 'P95 latency (true)')


def real_week():
    """7 real-style days, like the actual Parquet: identical in every window."""
    write_telemetry([(S, 'INFO', f'2026-07-0{d}') for d in range(1, 8)] * 2 + [(F, 'ERROR', f'2026-07-0{d}') for d in range(1, 8)])


def render(page, window='6 Months', mode=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value(page).run()
    next(r for r in at.sidebar.radio if r.key == 'time_window').set_value(window).run()
    if mode:
        next(r for r in at.sidebar.radio if r.key == 'data_mode').set_value(mode).run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return at, '\n'.join(m.value for m in at.markdown) + '\n' + '\n'.join(str(c.value) for c in at.caption)


def test_selector_defaults_to_real_data_and_lists_both_modes():
    at = AppTest.from_file(APP, default_timeout=60).run()
    box = next(r for r in at.sidebar.radio if r.key == 'data_mode')
    assert box.value == 'Real Data' and list(box.options) == ['Real Data', 'Demo Scenario Data']
    assert [r.key for r in at.sidebar.radio][1:3] == ['time_window', 'data_mode']
    assert any('Data Mode: Real Data' in c.value for c in at.sidebar.caption)


def test_demo_frames_are_the_existing_deterministic_synthetic_data_and_labelled():
    d = data.get_health(demo=True)
    pd.testing.assert_frame_equal(d, data.synthetic_health(), check_exact=True)
    assert d.attrs['source_mode'] == 'synthetic scenario' and 'Demo Scenario Data' in d.attrs['source_detail']
    assert data.get_telemetry(demo=True)['mode'] == 'synthetic scenario'


def test_demo_does_not_touch_real_telemetry_or_recorded_source_status():
    real_week()
    before = data.get_health()
    assert before.attrs['source_mode'] == 'parquet'
    status = storage.sources()
    data.get_health(demo=True), data.get_telemetry(demo=True)
    assert storage.sources() == status                                   # demo never overwrites adapter status
    pd.testing.assert_frame_equal(data.get_health(), before)
    assert data.get_telemetry()['mode'] == 'parquet' and data.get_telemetry()['stats']['events'] == 21


def test_real_mode_is_identical_across_windows_and_has_no_demo_label(no_gemini):
    real_week()
    texts = {k: render('Platform health', k)[1] for k in WINDOW_DAYS}
    for key in KEYS:
        assert len({card(texts[k], key) for k in WINDOW_DAYS}) == 1
    assert all('DEMO SCENARIO DATA' not in t for t in texts.values())


@pytest.mark.parametrize('page', ['Executive overview', 'Platform health'])
def test_demo_mode_is_unmistakable_and_responds_to_the_window(page, no_gemini):
    real_week()
    texts = {k: render(page, k, 'Demo Scenario Data')[1] for k in WINDOW_DAYS}
    for t in texts.values():
        assert 'DEMO SCENARIO DATA' in t and 'synthetic scenario' in t and 'not real telemetry' in t
        assert re.search(r'Last (30|90|180) days \(2026-\d\d-\d\d to 2026-10-17\)', t)           # synthetic anchor, not the real July week
    for key in ('Classified-call success rate', 'Unclassified events'):
        assert len({card(texts[k], key) for k in WINDOW_DAYS}) == 3, key


@pytest.mark.parametrize('page', ['User adoption', 'Model lifecycle', 'Chargeback'])
def test_other_pages_are_not_replaced_by_demo_mode(page, no_gemini):
    real_week()
    _, real = render(page)
    _, demo = render(page, mode='Demo Scenario Data')
    assert 'DEMO SCENARIO DATA' not in demo
    strip = lambda t: re.sub(r'(Data Mode:|rendered)[^\n]*', '', t)       # the sidebar indicator and clock are the only expected differences
    assert strip(real) == strip(demo)


def test_switching_back_restores_real_values(no_gemini):
    real_week()
    at, text = render('Platform health', '1 Month', 'Demo Scenario Data')
    demo_failed = card(text, 'Failed classified calls')
    next(r for r in at.sidebar.radio if r.key == 'data_mode').set_value('Real Data').run()
    back = '\n'.join(m.value for m in at.markdown)
    assert card(back, 'Failed classified calls') == '7' and demo_failed != '7' and 'DEMO SCENARIO DATA' not in back
