# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: vsp-rename

## Summary
Renamed user-facing Vision Planning terminology from `VPS` to `VSP` and standardized the expanded name to `Vision Strategy Plan`. Updated visible app labels, help text, screen titles, default stamped action-item values, selected docs, and the directly affected test fixture values. Internal module and filename prefixes remain `vps_*` to avoid a risky mechanical package rename.

## Files changed
- src/getmoredone/app.py
- src/getmoredone/app_settings.py
- src/getmoredone/database.py
- src/getmoredone/models.py
- src/getmoredone/vps_manager.py
- src/getmoredone/vps_schema.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/completed.py
- src/getmoredone/screens/hierarchical.py
- src/getmoredone/screens/item_editor.py
- src/getmoredone/screens/segment_color_utils.py
- src/getmoredone/screens/settings.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/vision_segments.py
- src/getmoredone/screens/vps_editors.py
- src/getmoredone/screens/vps_planning.py
- src/getmoredone/screens/vps_segment_editor.py
- tests/test_vps_hub_crud.py
- README.md
- docs/USER_GUIDE.md

## Verification
- Command: `rg -n "Vision Planning Strategy|Vision Plan Strategy|Visionary Planning System|VPS Plan|VPS Planning|\\bVPS\\b" src/getmoredone docs/USER_GUIDE.md README.md tests/test_vps_hub_crud.py`
- Result: PASS
- Command: `python3 -m py_compile src/getmoredone/app.py src/getmoredone/vps_manager.py src/getmoredone/vps_schema.py src/getmoredone/screens/vps_planning.py src/getmoredone/screens/vision_segments.py src/getmoredone/screens/settings.py src/getmoredone/screens/item_editor.py src/getmoredone/screens/vps_segment_editor.py`
- Result: PASS
- Command: `pytest -q tests/test_vps_hub_crud.py`
- Result: PASS

## Risks / Known gaps
- Internal Python filenames, class names, and test module names still use `vps_*`; this was left unchanged to avoid broader refactor risk.
- Older archival docs outside the targeted docs paths still contain historical `VPS` references.

## Next agent actions
- If full repo-wide naming consistency is required, do a docs-only archival sweep or a separate internal symbol rename pass with broader test coverage.
