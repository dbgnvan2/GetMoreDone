# UI Color Inventory

Generated via deterministic `rg` scans from repo root.

## Scan Commands
```bash
rg -n "fg_color=|hover_color=|text_color=|border_color=|button_color=|progress_color=|selected_color=|corner_radius=|highlight_color=" .
rg -n "#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b" .
rg -n -i "\"(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\"|\'(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\'" .
rg -n "set_default_color_theme\(|set_appearance_mode\(" .
```

## 1) Summary Counts By Type

- Hex colors (match count): **290**
- Named colors (match count): **204**
- Tuple colors / appearance tuples (match count): **1**
- CustomTkinter theme API usage (`set_default_color_theme`/`set_appearance_mode`) line count: **6**
- Widget explicit overrides (line count): **374**

Widget override property breakdown:

| Property | Count |
|---|---:|
| `border_color` | 12 |
| `button_color` | 2 |
| `corner_radius` | 15 |
| `fg_color` | 176 |
| `highlight_color` | 2 |
| `hover_color` | 70 |
| `progress_color` | 2 |
| `selected_color` | 2 |
| `text_color` | 124 |

AppSettings persisted color/theme fields:

```text
22:    appearance_mode: str = "dark"  # system | dark | light
23:    theme_name: str = "graphite"
59:    # Drag Schedule date box text color (hex)
60:    drag_schedule_date_text_color: str = "#FFFFFF"
94:                settings.appearance_mode = cls._normalize_appearance_mode(
95:                    settings.appearance_mode)
96:                settings.theme_name = cls._normalize_theme_name(
97:                    settings.theme_name)
108:        self.appearance_mode = self._normalize_appearance_mode(
109:            self.appearance_mode)
110:        self.theme_name = self._normalize_theme_name(self.theme_name)
122:    def _normalize_appearance_mode(value: Optional[str]) -> str:
128:    def _normalize_theme_name(value: Optional[str]) -> str:
```

Hex top values:

| Color | Count |
|---|---:|
| `#dce4ee` | 21 |
| `#ffffff` | 15 |
| `#374151` | 14 |
| `#979da2` | 10 |
| `#4b5563` | 9 |
| `#2f6fa0` | 9 |
| `#245c88` | 9 |
| `#00ff00` | 7 |
| `#334155` | 6 |
| `#3e454a` | 6 |
| `#949a9f` | 6 |
| `#565b5e` | 6 |
| `#1f2937` | 5 |
| `#f9f9fa` | 5 |
| `#000000` | 4 |
| `#343638` | 4 |
| `#285e85` | 4 |
| `#1c476a` | 4 |
| `#64748b` | 3 |
| `#94a3b8` | 3 |

Named top values:

| Color | Count |
|---|---:|
| `green` | 53 |
| `gray` | 43 |
| `red` | 43 |
| `white` | 23 |
| `darkgreen` | 21 |
| `orange` | 7 |
| `blue` | 6 |
| `black` | 4 |
| `yellow` | 3 |
| `cyan` | 1 |

## 2) Complete Occurrence Table (Grouped by Color Value, then File)

Each row is from grep output and includes `file:line` and a short snippet.

### `#000000`

| File:Line | Snippet |
|---|---|
| `tests/test_vps_integration.py:1484` | `color_hex="#000000",` |
| `tests/test_vps_integration.py:1610` | `name="Third", description="", color_hex="#000000", order_index=3` |
| `tests/test_vps_integration.py:1613` | `name="First", description="", color_hex="#000000", order_index=1` |
| `tests/test_vps_integration.py:1616` | `name="Second", description="", color_hex="#000000", order_index=2` |

### `#0000ff`

| File:Line | Snippet |
|---|---|
| `test_vps_data_integrity.py:199` | `color_hex="#0000FF",` |
| `tests/test_vps_integration.py:1507` | `color_hex="#0000FF",` |
| `tests/test_vps_integration.py:1634` | `valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]` |

### `#00bcd4`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:630` | `('seg-6', 'Recreation', 'Hobbies and leisure activities', '#00BCD4', 6),` |

### `#00ff00`

| File:Line | Snippet |
|---|---|
| `test_vps_data_integrity.py:58` | `color_hex="#00FF00",` |
| `tests/test_vps_integration.py:1397` | `color_hex="#00FF00",` |
| `tests/test_vps_integration.py:1492` | `color_hex="#00FF00"` |
| `tests/test_vps_integration.py:1499` | `assert segment['color_hex'] == "#00FF00"` |
| `tests/test_vps_integration.py:1551` | `color_hex="#00FF00",` |
| `tests/test_vps_integration.py:1581` | `color_hex="#00FF00",` |
| `tests/test_vps_integration.py:1634` | `valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]` |

### `#00ffaa`

| File:Line | Snippet |
|---|---|
| `tests/test_vision_planning_regressions.py:39` | `assert screen._get_date_text_color() == "#00FFAA"` |

### `#0284c7`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:53` | `("APE Weekly", "ape_weekly", "#0284C7", "#0369A1"),` |
| `src/getmoredone/screens/vps_planning.py:23` | `"Week": "#0284C7",` |

### `#0369a1`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:53` | `("APE Weekly", "ape_weekly", "#0284C7", "#0369A1"),` |

### `#059669`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:22` | `"Month": "#059669",` |

### `#0891b2`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:86` | `hover_color="#0891B2"` |
| `src/getmoredone/screens/vision_planning_hub.py:49` | `("Vision Elements", "vision_elements", "#0E7490", "#0891B2"),` |

### `#0d9488`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:55` | `ctk.CTkLabel(chip_row, text="Category", fg_color="#0D9488", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)` |
| `src/getmoredone/screens/vision_planning_hub.py:51` | `("APE Assignment", "ape_assignment", "#0D9488", "#0F766E"),` |
| `src/getmoredone/screens/vps_planning.py:19` | `"Annual Plan": "#0D9488",` |

### `#0e7490`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:85` | `fg_color="#0E7490",` |
| `src/getmoredone/screens/vision_planning_hub.py:49` | `("Vision Elements", "vision_elements", "#0E7490", "#0891B2"),` |

### `#0ea5e9`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#0f172a`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:33` | `header_frame = ctk.CTkFrame(self, fg_color="#0F172A")` |

### `#0f766e`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:51` | `("APE Assignment", "ape_assignment", "#0D9488", "#0F766E"),` |
| `src/getmoredone/screens/vps_planning.py:118` | `fg_color="#0F766E",` |

### `#10b981`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#112233`

| File:Line | Snippet |
|---|---|
| `tests/test_weekly_item_filters.py:25` | `(seg_id, "Creative", "Test Segment", "#112233", 1, 1, now, now),` |

### `#115e59`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:119` | `hover_color="#115E59"` |

### `#123456`

| File:Line | Snippet |
|---|---|
| `tests/test_vps_integration.py:1634` | `valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]` |

### `#14375e`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:199` | `"#14375e"` |
| `themes/graphite.json:210` | `"#14375e"` |
| `themes/graphite.json:279` | `"#14375e"` |

### `#144870`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:199` | `"#144870"` |
| `themes/ocean.json:210` | `"#144870"` |
| `themes/ocean.json:279` | `"#144870"` |

### `#14b8a6`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#163d6d`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:51` | `"primary_hover": "#163D6D",` |

### `#1c476a`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:39` | `"#1C476A"` |
| `themes/ocean.json:95` | `"#1C476A"` |
| `themes/ocean.json:153` | `"#1C476A"` |
| `themes/ocean.json:242` | `"#1C476A"` |

### `#1d1e1e`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:303` | `"#1D1E1E"` |

### `#1d2732`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:19` | `"#1D2732"` |

### `#1d4e89`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:50` | `"primary": "#1D4E89",` |

### `#1d4ed8`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:54` | `ctk.CTkLabel(chip_row, text="SubSegment", fg_color="#1D4ED8", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)` |
| `src/getmoredone/screens/vision_planning_hub.py:50` | `("Annual Vision Segments", "annual_vision_segments", "#2563EB", "#1D4ED8"),` |
| `src/getmoredone/screens/vps_planning.py:108` | `fg_color="#1D4ED8",` |

### `#1e232b`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:19` | `"#1E232B"` |

### `#1e2c40`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:214` | `"#1e2c40"` |

### `#1e40af`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:109` | `hover_color="#1E40AF"` |

### `#1f2937`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:1104` | `fg_color="#1F2937",` |
| `themes/graphite.json:39` | `"#1F2937"` |
| `themes/graphite.json:95` | `"#1F2937"` |
| `themes/graphite.json:153` | `"#1F2937"` |
| `themes/graphite.json:242` | `"#1F2937"` |

### `#1f2b24`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:65` | `"success_tint": "#1F2B24",` |

### `#1f538d`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:195` | `"#1f538d"` |
| `themes/graphite.json:206` | `"#1f538d"` |
| `themes/graphite.json:275` | `"#1f538d"` |

### `#1f6aa5`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:195` | `"#1F6AA5"` |
| `themes/ocean.json:206` | `"#1F6AA5"` |
| `themes/ocean.json:275` | `"#1F6AA5"` |

### `#203a4f`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:214` | `"#203A4F"` |

### `#2196f3`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:626` | `('seg-2', 'Purposeful Activity', 'Career, work, and meaningful projects', '#2196F3', 2),` |

### `#223247`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:67` | `"selected_tint": "#223247",` |

### `#233140`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:23` | `"#233140"` |

### `#234567`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:213` | `"#234567",` |

### `#242a33`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:23` | `"#242A33"` |

### `#244b6f`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:61` | `"primary_hover": "#244B6F",` |

### `#245c88`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:35` | `"#245C88"` |
| `themes/ocean.json:87` | `"#245C88"` |
| `themes/ocean.json:120` | `"#245C88"` |
| `themes/ocean.json:145` | `"#245C88"` |
| `themes/ocean.json:169` | `"#245C88"` |
| `themes/ocean.json:173` | `"#245C88"` |
| `themes/ocean.json:187` | `"#245C88"` |
| `themes/ocean.json:191` | `"#245C88"` |
| `themes/ocean.json:238` | `"#245C88"` |

### `#2563eb`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:50` | `("Annual Vision Segments", "annual_vision_segments", "#2563EB", "#1D4ED8"),` |
| `src/getmoredone/screens/vps_planning.py:18` | `"Annual Vision": "#2563EB",` |

### `#27577d`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:213` | `"#27577D",` |

### `#285e85`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:38` | `"#285E85",` |
| `themes/ocean.json:94` | `"#285E85",` |
| `themes/ocean.json:152` | `"#285E85",` |
| `themes/ocean.json:241` | `"#285E85",` |

### `#2a2f38`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:62` | `"ghost_hover": "#2A2F38",` |

### `#2c5d8a`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:60` | `"primary": "#2C5D8A",` |

### `#2f6fa0`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:34` | `"#2F6FA0",` |
| `themes/ocean.json:86` | `"#2F6FA0",` |
| `themes/ocean.json:119` | `"#2F6FA0",` |
| `themes/ocean.json:144` | `"#2F6FA0",` |
| `themes/ocean.json:168` | `"#2F6FA0",` |
| `themes/ocean.json:172` | `"#2F6FA0",` |
| `themes/ocean.json:186` | `"#2F6FA0",` |
| `themes/ocean.json:190` | `"#2F6FA0",` |
| `themes/ocean.json:237` | `"#2F6FA0",` |

### `#325882`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:198` | `"#325882",` |
| `themes/graphite.json:209` | `"#325882",` |
| `themes/graphite.json:278` | `"#325882",` |

### `#334155`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/segment_color_utils.py:9` | `DEFAULT_SEGMENT_COLOR = "#334155"` |
| `src/getmoredone/screens/vision_elements.py:53` | `ctk.CTkLabel(chip_row, text="Segment", fg_color="#334155", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)` |
| `src/getmoredone/screens/vision_elements.py:94` | `fg_color="#334155",` |
| `src/getmoredone/screens/vps_planning.py:97` | `fg_color="#334155",` |
| `src/getmoredone/vps_manager.py:610` | `color_map[name] = row["color_hex"] or "#334155"` |
| `src/getmoredone/vps_manager.py:620` | `color = (row["color_hex"] or "").strip() or "#334155"` |

### `#343638`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:67` | `"#343638"` |
| `themes/graphite.json:230` | `"#343638"` |
| `themes/ocean.json:67` | `"#343638"` |
| `themes/ocean.json:230` | `"#343638"` |

### `#36719f`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:198` | `"#36719F",` |
| `themes/ocean.json:209` | `"#36719F",` |
| `themes/ocean.json:278` | `"#36719F",` |

### `#374151`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:1105` | `hover_color="#374151",` |
| `themes/graphite.json:35` | `"#374151"` |
| `themes/graphite.json:38` | `"#374151",` |
| `themes/graphite.json:87` | `"#374151"` |
| `themes/graphite.json:94` | `"#374151",` |
| `themes/graphite.json:120` | `"#374151"` |
| `themes/graphite.json:145` | `"#374151"` |
| `themes/graphite.json:152` | `"#374151",` |
| `themes/graphite.json:169` | `"#374151"` |
| `themes/graphite.json:173` | `"#374151"` |
| `themes/graphite.json:187` | `"#374151"` |
| `themes/graphite.json:191` | `"#374151"` |
| `themes/graphite.json:238` | `"#374151"` |
| `themes/graphite.json:241` | `"#374151",` |

### `#3a2328`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:66` | `"critical_tint": "#3A2328",` |

### `#3a4350`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:63` | `"border": "#3A4350",` |

### `#3a7ebf`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:194` | `"#3a7ebf",` |
| `themes/graphite.json:205` | `"#3a7ebf",` |
| `themes/graphite.json:274` | `"#3a7ebf",` |

### `#3b8ed0`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:194` | `"#3B8ED0",` |
| `themes/ocean.json:205` | `"#3B8ED0",` |
| `themes/ocean.json:274` | `"#3B8ED0",` |

### `#3e454a`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:42` | `"#3E454A",` |
| `themes/graphite.json:90` | `"#3E454A",` |
| `themes/graphite.json:148` | `"#3E454A",` |
| `themes/ocean.json:42` | `"#3E454A",` |
| `themes/ocean.json:90` | `"#3E454A",` |
| `themes/ocean.json:148` | `"#3E454A",` |

### `#444444`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:134` | `fg_color="#444444",` |
| `src/getmoredone/screens/settings.py:1096` | `fg_color="#444444",` |

### `#475569`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:95` | `hover_color="#475569"` |
| `src/getmoredone/screens/vps_planning.py:98` | `hover_color="#475569"` |

### `#4a4d50`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:116` | `"#4A4D50"` |
| `themes/ocean.json:116` | `"#4A4D50"` |

### `#4a90e2`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_segment_editor.py:22` | `self.selected_color = segment['color_hex'] if segment else "#4A90E2"` |
| `src/getmoredone/screens/vps_segment_editor.py:202` | `"Invalid color code. Must be in format #RRGGBB (e.g., #4A90E2)"` |

### `#4b5563`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:34` | `"#4B5563",` |
| `themes/graphite.json:86` | `"#4B5563",` |
| `themes/graphite.json:119` | `"#4B5563",` |
| `themes/graphite.json:144` | `"#4B5563",` |
| `themes/graphite.json:168` | `"#4B5563",` |
| `themes/graphite.json:172` | `"#4B5563",` |
| `themes/graphite.json:186` | `"#4B5563",` |
| `themes/graphite.json:190` | `"#4B5563",` |
| `themes/graphite.json:237` | `"#4B5563",` |

### `#4caf50`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:625` | `('seg-1', 'Health', 'Physical and mental wellbeing', '#4CAF50', 1),` |

### `#555555`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:135` | `hover_color="#555555",` |
| `src/getmoredone/screens/settings.py:1097` | `hover_color="#555555",` |

### `#565b5e`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:71` | `"#565B5E"` |
| `themes/graphite.json:234` | `"#565B5E"` |
| `themes/graphite.json:307` | `"#565B5E"` |
| `themes/ocean.json:71` | `"#565B5E"` |
| `themes/ocean.json:234` | `"#565B5E"` |
| `themes/ocean.json:307` | `"#565B5E"` |

### `#64748b`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:54` | `"muted_text": "#64748B",` |
| `src/getmoredone/vps_manager.py:644` | `return "#64748B"` |
| `src/getmoredone/vps_manager.py:652` | `return "#64748B"` |

### `#660000`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:1612` | `hover_color="#660000"` |

### `#673ab7`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:633` | `('seg-9', 'Personal Growth', 'Self-improvement and spirituality', '#673AB7', 9),` |

### `#6b7280`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/item_editor.py:3328` | `text_color="#6B7280"` |

### `#6bcb77`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:354` | `return "#6BCB77"` |

### `#7c3aed`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:17` | `"TL Vision": "#7C3AED",` |

### `#7e22ce`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:129` | `hover_color="#7E22CE"` |

### `#808080`

| File:Line | Snippet |
|---|---|
| `tests/test_vps_integration.py:1589` | `color_hex="#808080",` |

### `#8b0000`

| File:Line | Snippet |
|---|---|
| `docs/VPS_DELETION_SAFETY.md:98` | `- Red warning box (color: `#8B0000`)` |
| `src/getmoredone/screens/settings.py:1524` | `warning_frame = ctk.CTkFrame(dialog, fg_color="#8B0000")` |
| `src/getmoredone/screens/settings.py:1611` | `fg_color="#8B0000",` |

### `#8b5cf6`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#8bc34a`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:631` | `('seg-7', 'Contribution', 'Giving back and community involvement', '#8BC34A', 7),` |

### `#9333ea`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:128` | `fg_color="#9333EA",` |

### `#939ba2`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:115` | `"#939BA2",` |
| `themes/ocean.json:115` | `"#939BA2",` |

### `#93c5fd`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_elements.py:47` | `text_color="#93C5FD"` |

### `#949a9f`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:43` | `"#949A9F"` |
| `themes/graphite.json:91` | `"#949A9F"` |
| `themes/graphite.json:149` | `"#949A9F"` |
| `themes/ocean.json:43` | `"#949A9F"` |
| `themes/ocean.json:91` | `"#949A9F"` |
| `themes/ocean.json:149` | `"#949A9F"` |

### `#94a3b8`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:42` | `text_color="#94A3B8"` |
| `src/getmoredone/screens/vps_planning.py:70` | `text_color="#94A3B8"` |
| `src/getmoredone/theme.py:64` | `"muted_text": "#94A3B8",` |

### `#979da2`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:70` | `"#979DA2",` |
| `themes/graphite.json:233` | `"#979DA2",` |
| `themes/graphite.json:270` | `"#979DA2",` |
| `themes/graphite.json:282` | `"#979DA2",` |
| `themes/graphite.json:306` | `"#979DA2",` |
| `themes/ocean.json:70` | `"#979DA2",` |
| `themes/ocean.json:233` | `"#979DA2",` |
| `themes/ocean.json:270` | `"#979DA2",` |
| `themes/ocean.json:282` | `"#979DA2",` |
| `themes/ocean.json:306` | `"#979DA2",` |

### `#9c27b0`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:627` | `('seg-3', 'Skills - Cognitive', 'Learning and intellectual development', '#9C27B0', 3),` |

### `#abcdef`

| File:Line | Snippet |
|---|---|
| `tests/test_vps_integration.py:1634` | `valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]` |

### `#b45309`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:52` | `("APE Period View", "ape_period_view", "#D97706", "#B45309"),` |

### `#cbd5e1`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:53` | `"border": "#CBD5E1",` |

### `#d5d9de`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:124` | `"#D5D9DE"` |
| `themes/ocean.json:124` | `"#D5D9DE"` |

### `#d97706`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:52` | `("APE Period View", "ape_period_view", "#D97706", "#B45309"),` |

### `#dce4ee`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:46` | `"#DCE4EE",` |
| `themes/graphite.json:47` | `"#DCE4EE"` |
| `themes/graphite.json:98` | `"#DCE4EE",` |
| `themes/graphite.json:217` | `"#DCE4EE",` |
| `themes/graphite.json:218` | `"#DCE4EE"` |
| `themes/graphite.json:290` | `"#DCE4EE",` |
| `themes/graphite.json:291` | `"#DCE4EE"` |
| `themes/ocean.json:46` | `"#DCE4EE",` |
| `themes/ocean.json:47` | `"#DCE4EE"` |
| `themes/ocean.json:59` | `"#DCE4EE"` |
| `themes/ocean.json:75` | `"#DCE4EE"` |
| `themes/ocean.json:98` | `"#DCE4EE",` |
| `themes/ocean.json:103` | `"#DCE4EE"` |
| `themes/ocean.json:132` | `"#DCE4EE"` |
| `themes/ocean.json:157` | `"#DCE4EE"` |
| `themes/ocean.json:217` | `"#DCE4EE",` |
| `themes/ocean.json:218` | `"#DCE4EE"` |
| `themes/ocean.json:246` | `"#DCE4EE"` |
| `themes/ocean.json:290` | `"#DCE4EE",` |
| `themes/ocean.json:291` | `"#DCE4EE"` |
| `themes/ocean.json:311` | `"#DCE4EE"` |

### `#dce7ef`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:22` | `"#DCE7EF",` |

### `#dff8d8`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:371` | `return colors[0] if colors else "#DFF8D8"` |

### `#e2e8f0`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vision_planning_hub.py:97` | `btn.configure(border_width=2, border_color="#E2E8F0")` |

### `#e5243b`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:363` | `"#E5243B",  # reddish` |

### `#e5e7eb`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:52` | `"ghost_hover": "#E5E7EB",` |

### `#e6eef4`

| File:Line | Snippet |
|---|---|
| `themes/ocean.json:18` | `"#E6EEF4",` |

### `#e6eef8`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:57` | `"selected_tint": "#E6EEF8",` |

### `#e8f5ee`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:55` | `"success_tint": "#E8F5EE",` |

### `#e91e63`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:629` | `('seg-5', 'Relationships', 'Personal and professional connections', '#E91E63', 5),` |

### `#ea580c`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:21` | `"Quarter": "#EA580C",` |

### `#ef4444`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#f59e0b`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/vps_planning.py:20` | `"Annual Initiative": "#F59E0B",` |
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#f97316`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_manager.py:665` | `palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]` |

### `#f9f9fa`

| File:Line | Snippet |
|---|---|
| `themes/graphite.json:66` | `"#F9F9FA",` |
| `themes/graphite.json:229` | `"#F9F9FA",` |
| `themes/ocean.json:66` | `"#F9F9FA",` |
| `themes/ocean.json:229` | `"#F9F9FA",` |
| `themes/ocean.json:302` | `"#F9F9FA",` |

### `#fdecec`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/theme.py:56` | `"critical_tint": "#FDECEC",` |

### `#ff0000`

| File:Line | Snippet |
|---|---|
| `test_vps_data_integrity.py:29` | `color_hex="#FF0000",` |
| `tests/test_vps_integration.py:1530` | `color_hex="#FF0000",` |
| `tests/test_vps_integration.py:1634` | `valid_colors = ["#FF0000", "#00FF00", "#0000FF", "#ABCDEF", "#123456"]` |

### `#ff00ff`

| File:Line | Snippet |
|---|---|
| `test_vps_data_integrity.py:306` | `color_hex="#FF00FF",` |
| `tests/test_vps_integration.py:1653` | `color_hex="#FF00FF",` |

### `#ff5733`

| File:Line | Snippet |
|---|---|
| `tests/test_vps_integration.py:1462` | `color_hex="#FF5733",` |
| `tests/test_vps_integration.py:1474` | `assert segment['color_hex'] == "#FF5733"` |

### `#ff5a8a`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:362` | `"#FF5A8A",  # darker pink` |

### `#ff9800`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:628` | `('seg-4', 'Wealth Creation', 'Financial growth and management', '#FF9800', 4),` |

### `#ff9bc2`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:361` | `"#FF9BC2",  # light pink` |

### `#ffb347`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:360` | `"#FFB347",  # darker orange` |

### `#ffc107`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/vps_schema.py:632` | `('seg-8', 'Travel', 'Exploration and adventure', '#FFC107', 8),` |

### `#ffcdd2`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:242` | `("Long Term", f"+{long_days} days\n{long_date}", long_date, "#FFCDD2"),` |

### `#ffd54f`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:241` | `("Near Term", f"+{mid_days} days\n{mid_date}", mid_date, "#FFD54F"),` |

### `#ffd8a8`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:359` | `"#FFD8A8",  # light orange` |

### `#ffe0b2`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:244` | `("1st Next Quarter", next_quarter_date, next_quarter_date, "#FFE0B2"),` |

### `#fff9c4`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/drag_schedule.py:243` | `("1st Next Month", next_month_date, next_month_date, "#FFF9C4"),` |

### `#ffffff`

| File:Line | Snippet |
|---|---|
| `docs/USER_GUIDE.md:229` | `- **Drag Schedule date text color** — What: Hex color for date-box text (default `#FFFFFF`). Why: Improve readability across box colors.` |
| `src/getmoredone/app_settings.py:60` | `drag_schedule_date_text_color: str = "#FFFFFF"` |
| `src/getmoredone/screens/drag_schedule.py:333` | `color = str(getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF") or "#FFFFFF").strip()` |
| `src/getmoredone/screens/drag_schedule.py:337` | `return "#FFFFFF"` |
| `src/getmoredone/screens/settings.py:425` | `value=getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF")` |
| `src/getmoredone/screens/settings.py:495` | `color_value = self.drag_schedule_text_color_var.get().strip() or "#FFFFFF"` |
| `src/getmoredone/screens/settings.py:499` | `color_value = "#FFFFFF"` |
| `src/getmoredone/screens/settings.py:514` | `initial = self.drag_schedule_text_color_var.get().strip() or "#FFFFFF"` |
| `tests/test_future_dates.py:82` | `original_color = getattr(settings, "drag_schedule_date_text_color", "#FFFFFF")` |
| `tests/test_future_dates.py:85` | `settings.drag_schedule_date_text_color = "#FFFFFF"` |
| `tests/test_future_dates.py:89` | `assert reloaded.drag_schedule_date_text_color == "#FFFFFF"` |
| `tests/test_vision_planning_regressions.py:35` | `screen.settings = SimpleNamespace(drag_schedule_date_text_color="#FFFFFF")` |
| `tests/test_vision_planning_regressions.py:36` | `assert screen._get_date_text_color() == "#FFFFFF"` |
| `tests/test_vision_planning_regressions.py:42` | `assert screen._get_date_text_color() == "#FFFFFF"` |

### `black`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/item_editor.py:2812` | `return "black" if luminance > 160 else "white"` |
| `src/getmoredone/widgets/date_picker.py:130` | `selectforeground='black',` |
| `src/getmoredone/widgets/date_picker.py:134` | `normalforeground='black',` |
| `src/getmoredone/widgets/date_picker.py:136` | `weekendforeground='black',` |

### `blue`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/timer_window.py:240` | `hover_color="blue"` |
| `src/getmoredone/screens/timer_window.py:272` | `fg_color="blue",` |
| `src/getmoredone/screens/timer_window.py:435` | `status_color = "green" if self.timer_state == "running" else "blue"` |
| `src/getmoredone/screens/timer_window.py:531` | `text_color="blue"` |
| `src/getmoredone/screens/today.py:84` | `fg_color="blue",` |
| `src/getmoredone/theme.py:41` | `ctk.set_default_color_theme("blue")` |

### `cyan`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/item_editor.py:2163` | `text_color="cyan"` |

### `darkgreen`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/ape_period_view.py:100` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/calendar_dialog.py:144` | `hover_color="darkgreen",` |
| `src/getmoredone/screens/edit_contact.py:137` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/item_editor.py:2520` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/item_editor.py:2761` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/item_editor.py:2992` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/item_editor.py:3337` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/reschedule_dialog.py:102` | `btn_save = ctk.CTkButton(btn_frame, text="Push to Next Day", command=self.save, fg_color="darkgreen", hover_color="green")` |
| `src/getmoredone/screens/settings.py:207` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/settings.py:461` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/settings.py:621` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/settings.py:1076` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/settings.py:1158` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/timer_window.py:162` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/timer_window.py:248` | `fg_color="darkgreen",` |
| `src/getmoredone/screens/timer_window.py:284` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/timer_window.py:1264` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/timer_window.py:1372` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/timer_window.py:1540` | `hover_color="darkgreen"` |
| `src/getmoredone/screens/today.py:96` | `hover_color="darkgreen",` |
| `src/getmoredone/screens/today.py:225` | `self.scroll_frame, fg_color="darkgreen")` |

### `gray`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/ape_period_view.py:105` | `self.status_label = ctk.CTkLabel(actions, text="", text_color="gray")` |
| `src/getmoredone/screens/ape_period_view.py:138` | `self.status_label.configure(text=f"Loaded {len(self.ape_rows)} APE record(s).", text_color="gray")` |
| `src/getmoredone/screens/ape_period_view.py:198` | `self.status_label.configure(text=f"Selected: {row['key_field']}", text_color="gray")` |
| `src/getmoredone/screens/item_editor.py:513` | `text_color="gray"` |
| `src/getmoredone/screens/item_editor.py:573` | `text_color="gray"` |
| `src/getmoredone/screens/item_editor.py:1915` | `text_color="gray"` |
| `src/getmoredone/screens/item_editor.py:2725` | `text_color="gray"` |
| `src/getmoredone/screens/item_editor.py:3287` | `text_color="gray"` |
| `src/getmoredone/screens/item_editor.py:3316` | `text_color="gray"` |
| `src/getmoredone/screens/manage_contacts.py:90` | `text_color="gray"` |
| `src/getmoredone/screens/settings.py:151` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray").grid(` |
| `src/getmoredone/screens/settings.py:229` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:334` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:479` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:637` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:681` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:1036` | `ctk.CTkLabel(section, text=info, justify="left", text_color="gray", wraplength=700).grid(` |
| `src/getmoredone/screens/settings.py:1171` | `ctk.CTkLabel(section, text=info_text, justify="left", text_color="gray", wraplength=600).grid(` |
| `src/getmoredone/screens/settings.py:1222` | `self.gmail_status_label.configure(text="Importer is disabled (enable it first).", text_color="gray")` |
| `src/getmoredone/screens/settings.py:1240` | `text_color=("green" if n else "gray"),` |
| `src/getmoredone/screens/settings.py:1248` | `self.gmail_status_label.configure(text="Running import…", text_color="gray")` |
| `src/getmoredone/screens/settings.py:1259` | `self.gmail_status_label.configure(text="Opened logs.", text_color="gray")` |
| `src/getmoredone/screens/settings.py:1314` | `color = "green" if (stats["created"] > 0 or stats.get("updated_existing", 0) > 0) else "gray"` |
| `src/getmoredone/screens/settings.py:1327` | `self.calendar_status_label.configure(text="Running calendar import…", text_color="gray")` |
| `src/getmoredone/screens/settings.py:1355` | `text_color="gray"` |
| `src/getmoredone/screens/settings.py:1401` | `text_color="gray"` |
| `src/getmoredone/screens/settings.py:1437` | `text_color="gray",` |
| `src/getmoredone/screens/settings.py:1445` | `status_color = "green" if segment['is_active'] else "gray"` |
| `src/getmoredone/screens/settings.py:1603` | `fg_color="gray"` |
| `src/getmoredone/screens/timer_window.py:224` | `text_color="gray"` |
| `src/getmoredone/screens/vps_editors.py:112` | `ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color="gray").grid(` |
| `src/getmoredone/screens/vps_editors.py:541` | `ctk.CTkLabel(main_frame, text="(one per line)", font=ctk.CTkFont(size=10), text_color="gray").grid(` |
| `src/getmoredone/screens/vps_editors.py:1256` | `separator = ctk.CTkFrame(main_frame, height=2, fg_color="gray")` |
| `src/getmoredone/screens/vps_planning.py:225` | `fg_color="gray",` |
| `src/getmoredone/screens/vps_planning.py:315` | `text_color="gray"` |
| `src/getmoredone/screens/vps_planning.py:495` | `text_color="gray"` |
| `src/getmoredone/screens/vps_planning.py:975` | `fg_color="gray"` |
| `src/getmoredone/screens/vps_segment_editor.py:147` | `fg_color="gray",` |
| `src/getmoredone/screens/weekly_items.py:63` | `self.status_label = ctk.CTkLabel(header, text="", text_color="gray")` |
| `themes/graphite.json:176` | `"gray",` |
| `themes/graphite.json:177` | `"gray"` |
| `themes/ocean.json:176` | `"gray",` |
| `themes/ocean.json:177` | `"gray"` |

### `green`

| File:Line | Snippet |
|---|---|
| `docs/action-timer-requirements.md:570` | `color = "green"  # Warning color` |
| `src/getmoredone/screens/ape_period_view.py:101` | `hover_color="green",` |
| `src/getmoredone/screens/ape_period_view.py:222` | `text_color="green",` |
| `src/getmoredone/screens/calendar_dialog.py:143` | `fg_color="green",` |
| `src/getmoredone/screens/defaults.py:224` | `self.status_label = ctk.CTkLabel(scroll, text="", text_color="green")` |
| `src/getmoredone/screens/edit_contact.py:136` | `fg_color="green",` |
| `src/getmoredone/screens/item_editor.py:2294` | `text_color="green" if item.status == "completed" else "white"` |
| `src/getmoredone/screens/item_editor.py:2510` | `text_color="green" if item.status == "completed" else "white"` |
| `src/getmoredone/screens/item_editor.py:2521` | `hover_color="green"` |
| `src/getmoredone/screens/item_editor.py:2762` | `hover_color="green"` |
| `src/getmoredone/screens/item_editor.py:2993` | `hover_color="green",` |
| `src/getmoredone/screens/item_editor.py:3338` | `hover_color="green"` |
| `src/getmoredone/screens/reschedule_dialog.py:102` | `btn_save = ctk.CTkButton(btn_frame, text="Push to Next Day", command=self.save, fg_color="darkgreen", hover_color="green")` |
| `src/getmoredone/screens/settings.py:141` | `section, text="", text_color="green")` |
| `src/getmoredone/screens/settings.py:208` | `hover_color="green"` |
| `src/getmoredone/screens/settings.py:248` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:268` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:327` | `self.appearance_status_label = ctk.CTkLabel(section, text="", text_color="green")` |
| `src/getmoredone/screens/settings.py:352` | `text_color="green",` |
| `src/getmoredone/screens/settings.py:462` | `hover_color="green",` |
| `src/getmoredone/screens/settings.py:469` | `section, text="", text_color="green")` |
| `src/getmoredone/screens/settings.py:509` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:547` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:622` | `hover_color="green",` |
| `src/getmoredone/screens/settings.py:629` | `section, text="", text_color="green")` |
| `src/getmoredone/screens/settings.py:660` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:811` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:916` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:931` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:978` | `text_color="green"` |
| `src/getmoredone/screens/settings.py:1006` | `text_color="green",` |
| `src/getmoredone/screens/settings.py:1077` | `hover_color="green",` |
| `src/getmoredone/screens/settings.py:1159` | `hover_color="green",` |
| `src/getmoredone/screens/settings.py:1164` | `self.future_date_status_label = ctk.CTkLabel(section, text="", text_color="green")` |
| `src/getmoredone/screens/settings.py:1212` | `self.gmail_status_label.configure(text="Saved (launchd updated).", text_color="green")` |
| `src/getmoredone/screens/settings.py:1240` | `text_color=("green" if n else "gray"),` |
| `src/getmoredone/screens/settings.py:1314` | `color = "green" if (stats["created"] > 0 or stats.get("updated_existing", 0) > 0) else "gray"` |
| `src/getmoredone/screens/settings.py:1366` | `fg_color="green",` |
| `src/getmoredone/screens/settings.py:1445` | `status_color = "green" if segment['is_active'] else "gray"` |
| `src/getmoredone/screens/stats.py:139` | `variance_color = "green" if variance <= 0 else "red"` |
| `src/getmoredone/screens/timer_window.py:139` | `text_color="green"` |
| `src/getmoredone/screens/timer_window.py:161` | `fg_color="green",` |
| `src/getmoredone/screens/timer_window.py:249` | `hover_color="green"` |
| `src/getmoredone/screens/timer_window.py:283` | `fg_color="green",` |
| `src/getmoredone/screens/timer_window.py:399` | `self._update_status_label("Working...", "green")` |
| `src/getmoredone/screens/timer_window.py:435` | `status_color = "green" if self.timer_state == "running" else "blue"` |
| `src/getmoredone/screens/timer_window.py:536` | `color = "green"` |
| `src/getmoredone/screens/timer_window.py:1263` | `fg_color="green",` |
| `src/getmoredone/screens/timer_window.py:1371` | `fg_color="green",` |
| `src/getmoredone/screens/timer_window.py:1539` | `fg_color="green",` |
| `src/getmoredone/screens/today.py:95` | `fg_color="green",` |
| `src/getmoredone/screens/vps_planning.py:215` | `fg_color="green",` |
| `src/getmoredone/screens/vps_segment_editor.py:139` | `fg_color="green",` |

### `orange`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/all_items.py:284` | `text_color="orange"` |
| `src/getmoredone/screens/settings.py:816` | `text_color="orange"` |
| `src/getmoredone/screens/timer_window.py:413` | `self._update_status_label("Paused", "orange")` |
| `src/getmoredone/screens/timer_window.py:914` | `self.configure(fg_color="orange")` |
| `src/getmoredone/screens/timer_window.py:922` | `self.configure(fg_color="orange")` |
| `src/getmoredone/screens/today.py:381` | `text_color="orange"` |
| `src/getmoredone/screens/upcoming.py:329` | `text_color="orange"` |

### `red`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/calendar_dialog.py:132` | `self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=550)` |
| `src/getmoredone/screens/defaults.py:353` | `self.status_label.configure(text=f"Error: {str(e)}", text_color="red")` |
| `src/getmoredone/screens/defaults.py:355` | `self.date_status_label.configure(text=f"Error: {str(e)}", text_color="red")` |
| `src/getmoredone/screens/edit_contact.py:126` | `fg_color="red",` |
| `src/getmoredone/screens/item_editor.py:617` | `top_row, text="", text_color="red", wraplength=600)` |
| `src/getmoredone/screens/item_editor.py:632` | `hover_color="red"` |
| `src/getmoredone/screens/item_editor.py:1948` | `hover_color="red",` |
| `src/getmoredone/screens/item_editor.py:2454` | `hover_color="red"` |
| `src/getmoredone/screens/item_editor.py:3004` | `main_frame, text="", text_color="red", wraplength=400)` |
| `src/getmoredone/screens/item_editor.py:3178` | `main_frame, text="", text_color="red", wraplength=500)` |
| `src/getmoredone/screens/item_editor.py:3448` | `hover_color="red",` |
| `src/getmoredone/screens/item_editor.py:3508` | `hover_color="red",` |
| `src/getmoredone/screens/plan.py:266` | `self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")` |
| `src/getmoredone/screens/reschedule_dialog.py:95` | `self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")` |
| `src/getmoredone/screens/settings.py:259` | `text_color="red"` |
| `src/getmoredone/screens/settings.py:273` | `text_color="red"` |
| `src/getmoredone/screens/settings.py:734` | `hover_color="red",` |
| `src/getmoredone/screens/settings.py:796` | `text="Please enter a value", text_color="red")` |
| `src/getmoredone/screens/settings.py:826` | `text=f"Error: {str(e)}", text_color="red")` |
| `src/getmoredone/screens/settings.py:923` | `text="Please select a replacement value", text_color="red")` |
| `src/getmoredone/screens/settings.py:941` | `text=f"Error: {str(e)}", text_color="red")` |
| `src/getmoredone/screens/settings.py:944` | `hover_color="red", command=delete).pack(side="left", padx=5)` |
| `src/getmoredone/screens/settings.py:966` | `text="Database file not found", text_color="red")` |
| `src/getmoredone/screens/settings.py:984` | `text_color="red"` |
| `src/getmoredone/screens/settings.py:1012` | `text_color="red",` |
| `src/getmoredone/screens/settings.py:1214` | `self.gmail_status_label.configure(text=f"Save failed: {e}", text_color="red")` |
| `src/getmoredone/screens/settings.py:1245` | `text_color="red",` |
| `src/getmoredone/screens/settings.py:1261` | `self.gmail_status_label.configure(text=f"Could not open logs: {e}", text_color="red")` |
| `src/getmoredone/screens/settings.py:1323` | `text_color="red",` |
| `src/getmoredone/screens/settings.py:1469` | `hover_color="red",` |
| `src/getmoredone/screens/settings.py:1560` | `text_color="red",` |
| `src/getmoredone/screens/stats.py:139` | `variance_color = "green" if variance <= 0 else "red"` |
| `src/getmoredone/screens/timer_window.py:178` | `fg_color="red",` |
| `src/getmoredone/screens/timer_window.py:460` | `self._update_status_label("Stopped", "red")` |
| `src/getmoredone/screens/timer_window.py:510` | `self._update_status_label("⏰ BREAK OVER! ⏰", "red")` |
| `src/getmoredone/screens/timer_window.py:1528` | `self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")` |
| `src/getmoredone/screens/vps_planning.py:584` | `vision['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:618` | `vision['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:654` | `plan['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:689` | `initiative['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:724` | `initiative['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:761` | `tactic['id']), fg_color="darkred", hover_color="red")` |
| `src/getmoredone/screens/vps_planning.py:799` | `action['id']), fg_color="darkred", hover_color="red")` |

### `white`

| File:Line | Snippet |
|---|---|
| `assets/icons/music_note.svg:1` | `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">` |
| `assets/icons/pause.svg:1` | `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">` |
| `assets/icons/play.svg:1` | `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">` |
| `assets/icons/stop.svg:1` | `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">` |
| `assets/icons/volume.svg:1` | `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white">` |
| `docs/action-timer-requirements.md:572` | `color = "white"  # Normal color` |
| `src/getmoredone/screens/annual_vision_segments.py:116` | `fg="white",` |
| `src/getmoredone/screens/annual_vision_segments.py:118` | `selectforeground="white",` |
| `src/getmoredone/screens/ape_assignment.py:213` | `fg="white",` |
| `src/getmoredone/screens/ape_assignment.py:215` | `selectforeground="white",` |
| `src/getmoredone/screens/ape_period_view.py:235` | `fg="white",` |
| `src/getmoredone/screens/ape_period_view.py:237` | `selectforeground="white",` |
| `src/getmoredone/screens/drag_schedule.py:410` | `text_color="white",` |
| `src/getmoredone/screens/item_editor.py:2294` | `text_color="green" if item.status == "completed" else "white"` |
| `src/getmoredone/screens/item_editor.py:2510` | `text_color="green" if item.status == "completed" else "white"` |
| `src/getmoredone/screens/item_editor.py:2812` | `return "black" if luminance > 160 else "white"` |
| `src/getmoredone/screens/item_editor.py:2815` | `return "white"` |
| `src/getmoredone/screens/settings.py:1531` | `text_color="white",` |
| `src/getmoredone/screens/timer_window.py:538` | `color = "white"` |
| `src/getmoredone/screens/vision_elements.py:179` | `self.list_box.tag_config(tag_name, background=color, foreground="white")` |
| `src/getmoredone/widgets/date_picker.py:128` | `foreground='white',` |
| `src/getmoredone/widgets/date_picker.py:132` | `headersforeground='white',` |
| `src/getmoredone/widgets/date_picker.py:133` | `normalbackground='white',` |

### `yellow`

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/item_editor.py:2194` | `text_color="yellow"` |
| `src/getmoredone/screens/item_editor.py:2224` | `text_color="yellow"` |
| `src/getmoredone/screens/timer_window.py:495` | `self._update_status_label("⏰ BREAK TIME! ⏰", "yellow")` |

### Theme API Occurrences

| File:Line | Snippet |
|---|---|
| `AGENTS.md:77` | `customtkinter.set_default_color_theme("path/to/theme.json")` |
| `AGENTS.md:87` | `- call set_appearance_mode(settings.appearance_mode)` |
| `AGENTS.md:88` | `- call set_default_color_theme(path_for_theme_name)` |
| `src/getmoredone/theme.py:35` | `ctk.set_appearance_mode(mode)` |
| `src/getmoredone/theme.py:39` | `ctk.set_default_color_theme(str(theme_path))` |
| `src/getmoredone/theme.py:41` | `ctk.set_default_color_theme("blue")` |

### Tuple / Appearance Tuple Occurrences

| File:Line | Snippet |
|---|---|
| `src/getmoredone/screens/settings.py:1240` | `text_color=("green" if n else "gray"),` |

## 3) Replace Plan

Recommended migration targets:

- **Theme defaults (JSON-driven):**
- Base CTk widget palette defaults (`CTkButton`, `CTkFrame`, `CTkEntry`, `CTkCheckBox`, `CTkSwitch`, etc.) should stay in `/themes/*.json`.
- Remove one-off color literals that duplicate core palette choices.
- **Semantic tokens (code-level):**
- Route UI state colors through semantic names in `src/getmoredone/theme.py` (e.g., `primary`, `primary_hover`, `ghost_hover`, `selected_tint`, `critical_tint`, `success_tint`, `muted_text`, `border`).
- Convert direct `fg_color`/`hover_color`/`text_color` literals in screens to semantic token lookups.
- **Allowed data-driven colors:**
- Keep `segment_descriptions.color_hex` as the only domain data-driven color source.
- Restrict segment colors to accent/chip/stripe/icon usage; avoid full-row fills.
- **Persisted settings:**
- Keep only settings-level color fields that are user-configurable and intentional (`drag_schedule_date_text_color`) plus theme selectors (`appearance_mode`, `theme_name`).

## 4) Hard Rule

**No new hard-coded colors except data-driven segment colors (`segment_descriptions.color_hex`).**

Enforcement recommendation: run the same `rg` commands in CI and diff this inventory after refactors.
