"""Scenario (demo) telemetry: the POC runs on the deterministic synthetic scenario data (P4.1 removed the Real/Demo
toggle). The data layer still supports a real path; these tests cover the data layer and the demo-rendered pages."""
import re
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from src import data, storage
from src.timewindow import WINDOW_DAYS
from tests.test_phase1_metrics import APP, S, F, no_gemini, write_telemetry  # noqa: F401
from tests.test_phase2_time import card

KEYS = ('Call success rate', 'Failed classified calls', 'P95 response time')


def real_week():
    """7 real-style days, like the actual Parquet: identical in every window."""
    write_telemetry([(S, 'INFO', f'2026-07-0{d}') for d in range(1, 8)] * 2 + [(F, 'ERROR', f'2026-07-0{d}') for d in range(1, 8)])


def render(page, window='6 Months', mode=None):
    # The app is demo-only now; `mode` is ignored. The time window is a per-page radio (key 'tw_<page>').
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value(page).run()
    tw = [r for r in at.radio if str(r.key).startswith('tw_')]
    if tw and window:
        tw[0].set_value(window).run()
    assert not at.exception and not at.error, [x.value for x in at.error]
    return at, '\n'.join(m.value for m in at.markdown) + '\n' + '\n'.join(str(c.value) for c in at.caption)


def test_demo_frames_are_the_existing_deterministic_synthetic_data_and_labelled():
    d = data.get_health(demo=True)
    pd.testing.assert_frame_equal(d, data.synthetic_health(), check_exact=True)
    assert d.attrs['source_mode'] == 'synthetic scenario' and 'Demo Scenario Data' in d.attrs['source_detail']
    assert data.get_telemetry(demo=True)['mode'] == 'synthetic scenario'


def test_demo_does_not_touch_real_telemetry_or_recorded_source_status():
    # The data layer still supports a real path; demo never overwrites the recorded source status (even though the app
    # itself now always runs demo).
    real_week()
    before = data.get_health()
    assert before.attrs['source_mode'] == 'parquet'
    status = storage.sources()
    data.get_health(demo=True), data.get_telemetry(demo=True)
    assert storage.sources() == status
    pd.testing.assert_frame_equal(data.get_health(), before)
    assert data.get_telemetry()['mode'] == 'parquet' and data.get_telemetry()['stats']['events'] == 21


@pytest.mark.parametrize('page', ['Executive overview', 'Platform health'])
def test_demo_mode_responds_to_the_window(page, no_gemini):
    texts = {k: render(page, k)[1] for k in WINDOW_DAYS}
    for t in texts.values():
        assert re.search(r'Last (30|90|180) days \(2026-\d\d-\d\d to 2026-10-17\)', t)           # synthetic anchor
    for key in ('Call success rate',):
        assert len({card(texts[k], key) for k in WINDOW_DAYS}) == 3, key


def test_demo_banner_is_absent_on_platform_health_and_executive(no_gemini):
    # The DEMO SCENARIO DATA callout was removed from Platform Health (2026-10-26 usability request); the
    # 'synthetic scenario' source badge/basis line still discloses the data origin on the page.
    _, ph = render('Platform health', '1 Month')
    assert 'DEMO SCENARIO DATA' not in ph and 'synthetic scenario' in ph
    _, ex = render('Executive overview', '1 Month')
    assert 'DEMO SCENARIO DATA' not in ex
