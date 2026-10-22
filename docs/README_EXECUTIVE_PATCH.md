# Executive Overview UI patch

Apply this patch to the current V1.0 repository represented by `nesgen360-final-project-bundle-v1.0.txt`.

## Add
- `src/executive_ui.py`
- `tests/test_executive_ui_patch.py`
- `docs/EXECUTIVE_OVERVIEW_PATCH.md`

## Behavior
- Removes the yellow Today's Focus banner.
- Adds a collapsed `Today's focus points in bulletin` section with three bullets.
- Calculation/source text is hidden inside each KPI information popover.
- Priority Actions has a Show/hide button. The Leadership Action Queue is absent by default, appears only after the button is clicked, and can be hidden again.
- Usage/reliability controls belong only to that chart.
- Total, successful and failed request counts are displayed as three lines on one request-count axis. Successful + failed = total.
- Provider consumption uses Log Analytics event counts by provider when compatible provider and time columns exist. Default is UTC month-to-date. Users can change period/environment.
- If Log Analytics provider fields are unavailable, a clearly labelled synthetic provider fallback is shown. The current documented Log Analytics contract does not guarantee a provider column.
- No login, AI Assistant, data files, database, secrets, model settings or other page functions are changed.

## Install
1. Stop Streamlit.
2. Extract this patch into the repository root, preserving folders.
3. Run the baseline-aware installer. It creates `app.py.executive-v1-backup` before changing only `executive()`:

```powershell
python scripts\apply_executive_patch.py
```

4. Validate:

```powershell
python -m py_compile app.py src\executive_ui.py
python -m pytest -q tests\test_executive_ui_patch.py
```

5. Restart the app.

The installer refuses to edit `app.py` if the reviewed V1.0 Executive Overview markers are not present.

## Important data boundary
The existing daily health adapter exposes daily total requests and a success-rate percentage. The patch derives successful and failed counts from those fields. The current source contract does not expose a model dimension in that daily frame; therefore the model multiselect is visible/searchable but cannot narrow the aggregate until model-granular telemetry is added. The UI states this rather than pretending the filter was applied.
