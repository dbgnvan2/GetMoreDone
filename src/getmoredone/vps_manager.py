"""
VPS (Visionary Planning System) Database Manager
Provides CRUD operations for all VPS entities.
"""

import sqlite3
import re
import logging
import colorsys
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
from calendar import monthrange

from .database import Database
from .db_manager import DatabaseManager
from .models import ActionItem
from .paths import app_data_dir_path


def _get_weekly_debug_logger() -> logging.Logger:
    logger = logging.getLogger("getmoredone.weekly_tactic")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = app_data_dir_path() / "weekly_tactic_debug.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class VPSManager:
    """Manages all VPS database operations."""

    def __init__(self, db_path: Optional[str] = None, db_manager: Optional[DatabaseManager] = None):
        """Initialize VPS manager with database connection."""
        self.db = Database(db_path)
        self.db.connect()
        self.db.initialize_schema()
        self.logger = _get_weekly_debug_logger()

        # Store db_manager for action item operations
        # If not provided, create one using the same db_path
        self.db_manager = db_manager if db_manager else DatabaseManager(
            db_path)
        self.sync_vision_segments_with_settings()
        self.sync_vision_elements_with_taxonomy()

    def close(self):
        """Close database connection."""
        self.db.close()

    @staticmethod
    def shorten_pipe_prefix(text: str) -> str:
        """
        Shorten first two pipe-delimited segments to initials.
        Example: Purposeful Work|Living Systems|Blog -> PW|LS|Blog
        """
        raw = (text or "").strip()
        if not raw or "|" not in raw:
            return raw

        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 3:
            return raw

        def initials(phrase: str) -> str:
            words = [w for w in phrase.split() if w]
            return "".join(w[0].upper() for w in words) if words else phrase[:1].upper()

        parts[0] = initials(parts[0])
        parts[1] = initials(parts[1])
        return "|".join(parts)

    @staticmethod
    def normalize_week_token(text: str) -> str:
        """Convert 'Week N' to 'Wn' in titles."""
        return re.sub(r"\bWeek\s+(\d+)\b", r"W\1", text or "", flags=re.IGNORECASE)

    def normalize_action_item_title_prefixes(self) -> int:
        """
        Normalize existing Action Item titles:
        - shorten Segment|SubSegment prefix
        - convert 'Week N' to 'Wn'
        Returns count of updated records.
        """
        rows = self.db.conn.execute(
            "SELECT id, title FROM action_items WHERE title IS NOT NULL"
        ).fetchall()

        updated = 0
        now = datetime.now().isoformat()
        for row in rows:
            old = row["title"] or ""
            new = self.normalize_week_token(self.shorten_pipe_prefix(old))
            if new != old:
                self.db.conn.execute(
                    "UPDATE action_items SET title = ?, updated_at = ? WHERE id = ?",
                    (new, now, row["id"]),
                )
                updated += 1
        if updated:
            self.db.conn.commit()
        return updated

    @staticmethod
    def _is_valid_hex_color(value: Optional[str]) -> bool:
        text = (value or "").strip()
        if len(text) != 7 or not text.startswith("#"):
            return False
        try:
            int(text[1:], 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def _derive_subsegment_color(segment_color: str) -> str:
        """Return a lighter related hue for subsegments."""
        base = (segment_color or "").strip()
        if not VPSManager._is_valid_hex_color(base):
            base = "#64748B"
        r = int(base[1:3], 16) / 255.0
        g = int(base[3:5], 16) / 255.0
        b = int(base[5:7], 16) / 255.0
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        h = (h + (10.0 / 360.0)) % 1.0
        s = min(1.0, max(0.0, s * 0.88))
        l = min(0.92, max(0.25, l + 0.16))
        r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
        return f"#{int(round(r2 * 255)):02X}{int(round(g2 * 255)):02X}{int(round(b2 * 255)):02X}"

    # ========================================================================
    # VISION ELEMENTS (Segment > SubSegment > Category)
    # ========================================================================

    def sync_vision_elements_with_taxonomy(self):
        """Ensure every Segment/SubSegment/Category row has a Vision Element key row."""
        rows = self.db.conn.execute(
            """
            SELECT
                s.id AS segment_id,
                s.name AS segment_name,
                ss.id AS subsegment_id,
                ss.name AS subsegment_name,
                c.id AS category_id,
                c.name AS category_name
            FROM vision_categories c
            JOIN vision_subsegments ss ON ss.id = c.subsegment_id
            JOIN vision_segments s ON s.id = ss.segment_id
            ORDER BY s.name COLLATE NOCASE ASC, ss.name COLLATE NOCASE ASC, c.name COLLATE NOCASE ASC
            """
        ).fetchall()

        now = datetime.now().isoformat()
        changed = False
        for row in rows:
            key_field = f"{row['segment_name']}|{row['subsegment_name']}|{row['category_name']}"
            existing = self.db.conn.execute(
                """
                SELECT id, key_field FROM vision_elements
                WHERE category_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (row["category_id"],),
            ).fetchone()
            if existing:
                if (existing["key_field"] or "") != key_field:
                    conflict = self.db.conn.execute(
                        "SELECT id FROM vision_elements WHERE key_field = ? AND id <> ?",
                        (key_field, existing["id"]),
                    ).fetchone()
                    if not conflict:
                        self.db.conn.execute(
                            """
                            UPDATE vision_elements
                            SET segment_id = ?, subsegment_id = ?, category_id = ?, key_field = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                row["segment_id"],
                                row["subsegment_id"],
                                row["category_id"],
                                key_field,
                                now,
                                existing["id"],
                            ),
                        )
                        self._sync_vision_element_derived_fields(existing["id"])
                        changed = True
                continue

            self.db.conn.execute(
                """
                INSERT INTO vision_elements
                (id, segment_id, subsegment_id, category_id, key_field, vision_text, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    f"ve-{uuid4().hex[:8]}",
                    row["segment_id"],
                    row["subsegment_id"],
                    row["category_id"],
                    key_field,
                    "",
                    now,
                    now,
                ),
            )
            changed = True

        if changed:
            self.db.conn.commit()

    def get_vision_segments(self) -> List[Dict[str, Any]]:
        self.sync_vision_segments_with_settings()
        cursor = self.db.conn.execute(
            "SELECT * FROM vision_segments ORDER BY name COLLATE NOCASE ASC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_vision_subsegments(self, segment_name: Optional[str] = None) -> List[Dict[str, Any]]:
        params: List[Any] = []
        query = """
            SELECT ss.*, s.name AS segment_name
            FROM vision_subsegments ss
            JOIN vision_segments s ON s.id = ss.segment_id
        """
        if segment_name:
            query += " WHERE LOWER(s.name) = LOWER(?)"
            params.append(segment_name.strip())
        query += " ORDER BY s.name COLLATE NOCASE ASC, ss.name COLLATE NOCASE ASC"
        cursor = self.db.conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        changed = False
        for row in rows:
            if self._is_valid_hex_color(row.get("color_hex")):
                continue
            parent = self.resolve_segment_color(row.get("segment_name", ""), self.get_segment_color_map())
            color = self._derive_subsegment_color(parent)
            row["color_hex"] = color
            self.db.conn.execute(
                "UPDATE vision_subsegments SET color_hex = ?, updated_at = ? WHERE id = ?",
                (color, datetime.now().isoformat(), row["id"]),
            )
            changed = True
        if changed:
            self.db.conn.commit()
        return rows

    def get_vision_categories(self, segment_name: Optional[str] = None,
                              subsegment_name: Optional[str] = None) -> List[Dict[str, Any]]:
        params: List[Any] = []
        query = """
            SELECT c.*, ss.name AS subsegment_name, s.name AS segment_name
            FROM vision_categories c
            JOIN vision_subsegments ss ON ss.id = c.subsegment_id
            JOIN vision_segments s ON s.id = ss.segment_id
            WHERE 1=1
        """
        if segment_name:
            query += " AND LOWER(s.name) = LOWER(?)"
            params.append(segment_name.strip())
        if subsegment_name:
            query += " AND LOWER(ss.name) = LOWER(?)"
            params.append(subsegment_name.strip())
        query += " ORDER BY s.name COLLATE NOCASE ASC, ss.name COLLATE NOCASE ASC, c.name COLLATE NOCASE ASC"
        cursor = self.db.conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        changed = False
        for row in rows:
            if self._is_valid_hex_color(row.get("color_hex")):
                continue
            sub_color = (row.get("color_hex") or "").strip()
            if not self._is_valid_hex_color(sub_color):
                subsegments = self.get_vision_subsegments(row.get("segment_name"))
                sub = next((s for s in subsegments if (s.get("name") or "").lower() == (row.get("subsegment_name") or "").lower()), None)
                sub_color = (sub or {}).get("color_hex") or self.default_subsegment_color_for_segment(row.get("segment_name") or "")
            color = self._derive_subsegment_color(sub_color)
            row["color_hex"] = color
            self.db.conn.execute(
                "UPDATE vision_categories SET color_hex = ?, updated_at = ? WHERE id = ?",
                (color, datetime.now().isoformat(), row["id"]),
            )
            changed = True
        if changed:
            self.db.conn.commit()
        return rows

    def _create_or_get_vision_segment(self, name: str) -> str:
        now = datetime.now().isoformat()
        norm = name.strip()
        settings_row = self.db.conn.execute(
            "SELECT name FROM segment_descriptions WHERE LOWER(name) = LOWER(?)",
            (norm,),
        ).fetchone()
        if not settings_row:
            raise ValueError(
                f"Segment '{norm}' does not exist in Vision Elements. Create it in VPS Plan -> Vision Elements first."
            )
        norm = settings_row["name"]
        row = self.db.conn.execute(
            "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)",
            (norm,)
        ).fetchone()
        if row:
            return row["id"]
        seg_id = f"vsg-{uuid4().hex[:8]}"
        self.db.conn.execute(
            "INSERT INTO vision_segments (id, name, vision_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (seg_id, norm, "", now, now)
        )
        return seg_id

    def _create_or_get_vision_subsegment(
        self,
        segment_id: str,
        name: str,
        color_hex: Optional[str] = None,
        description: str = "",
        vision_text: str = "",
    ) -> str:
        now = datetime.now().isoformat()
        norm = name.strip()
        row = self.db.conn.execute(
            "SELECT id FROM vision_subsegments WHERE segment_id = ? AND LOWER(name) = LOWER(?)",
            (segment_id, norm)
        ).fetchone()
        if row:
            return row["id"]

        seg_row = self.db.conn.execute(
            "SELECT name FROM vision_segments WHERE id = ?",
            (segment_id,),
        ).fetchone()
        seg_name = (seg_row["name"] if seg_row else "").strip()
        base_color = self.resolve_segment_color(seg_name, self.get_segment_color_map())
        default_color = self._derive_subsegment_color(base_color)
        chosen_color = color_hex.strip() if color_hex else default_color
        if not self._is_valid_hex_color(chosen_color):
            chosen_color = default_color

        sub_id = f"vss-{uuid4().hex[:8]}"
        self.db.conn.execute(
            "INSERT INTO vision_subsegments (id, segment_id, name, color_hex, description, vision_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sub_id, segment_id, norm, chosen_color, (description or "").strip(), (vision_text or "").strip(), now, now)
        )
        return sub_id

    def _resolve_vision_subsegment_id(self, segment_id: str, name: str) -> Optional[str]:
        row = self.db.conn.execute(
            "SELECT id FROM vision_subsegments WHERE segment_id = ? AND LOWER(name) = LOWER(?)",
            (segment_id, (name or "").strip()),
        ).fetchone()
        return row["id"] if row else None

    def _create_or_get_vision_category(
        self,
        subsegment_id: str,
        name: str,
        color_hex: Optional[str] = None,
        description: str = "",
        vision_text: str = "",
    ) -> str:
        now = datetime.now().isoformat()
        norm = name.strip()
        row = self.db.conn.execute(
            "SELECT id FROM vision_categories WHERE subsegment_id = ? AND LOWER(name) = LOWER(?)",
            (subsegment_id, norm)
        ).fetchone()
        if row:
            return row["id"]
        sub_row = self.db.conn.execute(
            "SELECT color_hex FROM vision_subsegments WHERE id = ?",
            (subsegment_id,),
        ).fetchone()
        sub_color = (sub_row["color_hex"] if sub_row else "") or "#64748B"
        default_color = self._derive_subsegment_color(sub_color)
        chosen_color = (color_hex or "").strip() or default_color
        if not self._is_valid_hex_color(chosen_color):
            chosen_color = default_color
        cat_id = f"vct-{uuid4().hex[:8]}"
        self.db.conn.execute(
            "INSERT INTO vision_categories (id, subsegment_id, name, color_hex, description, vision_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cat_id, subsegment_id, norm, chosen_color, (description or "").strip(), (vision_text or "").strip(), now, now)
        )
        return cat_id

    def create_or_get_vision_element(self, segment_name: str, subsegment_name: str, category_name: str) -> str:
        """Create linked Segment/SubSegment/Category and the Vision Element key record."""
        segment_name = segment_name.strip()
        subsegment_name = subsegment_name.strip()
        category_name = category_name.strip()
        if not segment_name or not subsegment_name or not category_name:
            raise ValueError("Segment, SubSegment, and Category are required")

        seg_id = self._create_or_get_vision_segment(segment_name)
        sub_id = self._resolve_vision_subsegment_id(seg_id, subsegment_name)
        if not sub_id:
            raise ValueError(
                f"SubSegment '{subsegment_name}' does not exist under '{segment_name}'. "
                "Create it in VPS Plan -> Vision Elements first."
            )
        cat_id = self._create_or_get_vision_category(sub_id, category_name)

        key_field = f"{segment_name}|{subsegment_name}|{category_name}"
        now = datetime.now().isoformat()
        row = self.db.conn.execute(
            "SELECT id FROM vision_elements WHERE key_field = ?",
            (key_field,)
        ).fetchone()
        if row:
            self.db.conn.commit()
            return row["id"]

        ve_id = f"ve-{uuid4().hex[:8]}"
        self.db.conn.execute("""
            INSERT INTO vision_elements (id, segment_id, subsegment_id, category_id, key_field, vision_text, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (ve_id, seg_id, sub_id, cat_id, key_field, "", now, now))
        self.db.conn.commit()
        return ve_id

    def update_vision_subsegment_color(self, subsegment_id: str, color_hex: str) -> bool:
        """Update a subsegment color."""
        value = (color_hex or "").strip().upper()
        if not self._is_valid_hex_color(value):
            raise ValueError("Invalid color. Use format #RRGGBB.")
        cur = self.db.conn.execute(
            "UPDATE vision_subsegments SET color_hex = ?, updated_at = ? WHERE id = ?",
            (value, datetime.now().isoformat(), subsegment_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def get_vision_elements(self) -> List[Dict[str, Any]]:
        self.sync_vision_elements_with_taxonomy()
        cursor = self.db.conn.execute("""
            SELECT
                ve.id,
                ve.key_field,
                ve.vision_text,
                s.id AS segment_id,
                s.name AS segment_name,
                s.vision_text AS segment_vision_text,
                ss.id AS subsegment_id,
                ss.name AS subsegment_name,
                ss.color_hex AS subsegment_color_hex,
                ss.vision_text AS subsegment_vision_text,
                c.id AS category_id,
                c.name AS category_name,
                c.vision_text AS category_vision_text
            FROM vision_elements ve
            JOIN vision_segments s ON s.id = ve.segment_id
            JOIN vision_subsegments ss ON ss.id = ve.subsegment_id
            JOIN vision_categories c ON c.id = ve.category_id
            WHERE ve.is_active = 1
            ORDER BY s.name COLLATE NOCASE ASC, ss.name COLLATE NOCASE ASC, c.name COLLATE NOCASE ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def update_vision_element(
        self,
        vision_element_id: str,
        segment_name: str,
        subsegment_name: str,
        category_name: str,
        vision_text: Optional[str] = None,
    ) -> bool:
        """Update a Vision Element and keep annual mirrors in sync."""
        segment_name = (segment_name or "").strip()
        subsegment_name = (subsegment_name or "").strip()
        category_name = (category_name or "").strip()
        if not segment_name or not subsegment_name or not category_name:
            raise ValueError("Segment, SubSegment, and Category are required")

        row = self.db.conn.execute(
            "SELECT id FROM vision_elements WHERE id = ?",
            (vision_element_id,),
        ).fetchone()
        if not row:
            return False

        seg_id = self._create_or_get_vision_segment(segment_name)
        sub_id = self._resolve_vision_subsegment_id(seg_id, subsegment_name)
        if not sub_id:
            raise ValueError(
                f"SubSegment '{subsegment_name}' does not exist under '{segment_name}'. "
                "Create it in VPS Plan -> Vision Elements first."
            )
        cat_id = self._create_or_get_vision_category(sub_id, category_name)
        key_field = f"{segment_name}|{subsegment_name}|{category_name}"
        now = datetime.now().isoformat()
        vision_value = (vision_text or "").strip() if vision_text is not None else None

        if vision_value is None:
            self.db.conn.execute(
                """
                UPDATE vision_elements
                SET segment_id = ?, subsegment_id = ?, category_id = ?, key_field = ?, updated_at = ?
                WHERE id = ?
                """,
                (seg_id, sub_id, cat_id, key_field, now, vision_element_id),
            )
        else:
            self.db.conn.execute(
                """
                UPDATE vision_elements
                SET segment_id = ?, subsegment_id = ?, category_id = ?, key_field = ?, vision_text = ?, updated_at = ?
                WHERE id = ?
                """,
                (seg_id, sub_id, cat_id, key_field, vision_value, now, vision_element_id),
            )

        # Keep derived annual records aligned.
        self.db.conn.execute(
            """
            UPDATE annual_vision_elements
            SET segment_name = ?, subsegment_name = ?, category_name = ?, key_field = ?, updated_at = ?
            WHERE vision_element_id = ?
            """,
            (segment_name, subsegment_name, category_name, key_field, now, vision_element_id),
        )
        self.db.conn.execute(
            """
            UPDATE annual_plan_elements
            SET segment_name = ?, subsegment_name = ?, category_name = ?, key_field = ?, updated_at = ?
            WHERE vision_element_id = ?
            """,
            (segment_name, subsegment_name, category_name, key_field, now, vision_element_id),
        )
        self.db.conn.commit()
        return True

    def _sync_vision_element_derived_fields(self, vision_element_id: str):
        """Recompute key_field and annual mirror names for one vision element."""
        row = self.db.conn.execute(
            """
            SELECT ve.id, s.name AS segment_name, ss.name AS subsegment_name, c.name AS category_name
            FROM vision_elements ve
            JOIN vision_segments s ON s.id = ve.segment_id
            JOIN vision_subsegments ss ON ss.id = ve.subsegment_id
            JOIN vision_categories c ON c.id = ve.category_id
            WHERE ve.id = ?
            """,
            (vision_element_id,),
        ).fetchone()
        if not row:
            return

        segment_name = row["segment_name"]
        subsegment_name = row["subsegment_name"]
        category_name = row["category_name"]
        key_field = f"{segment_name}|{subsegment_name}|{category_name}"
        now = datetime.now().isoformat()

        self.db.conn.execute(
            "UPDATE vision_elements SET key_field = ?, updated_at = ? WHERE id = ?",
            (key_field, now, vision_element_id),
        )
        self.db.conn.execute(
            """
            UPDATE annual_vision_elements
            SET segment_name = ?, subsegment_name = ?, category_name = ?, key_field = ?, updated_at = ?
            WHERE vision_element_id = ?
            """,
            (segment_name, subsegment_name, category_name, key_field, now, vision_element_id),
        )
        self.db.conn.execute(
            """
            UPDATE annual_plan_elements
            SET segment_name = ?, subsegment_name = ?, category_name = ?, key_field = ?, updated_at = ?
            WHERE vision_element_id = ?
            """,
            (segment_name, subsegment_name, category_name, key_field, now, vision_element_id),
        )

    def rename_vision_segment(self, segment_id: str, new_name: str) -> bool:
        new_value = (new_name or "").strip()
        if not new_value:
            raise ValueError("Segment name is required.")

        current = self.db.conn.execute(
            "SELECT id, name FROM vision_segments WHERE id = ?",
            (segment_id,),
        ).fetchone()
        if not current:
            return False

        duplicate = self.db.conn.execute(
            "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?) AND id <> ?",
            (new_value, segment_id),
        ).fetchone()
        if duplicate:
            raise ValueError(f"Segment '{new_value}' already exists.")

        try:
            self.db.conn.execute("BEGIN")
            self.db.conn.execute(
                "UPDATE vision_segments SET name = ?, updated_at = ? WHERE id = ?",
                (new_value, datetime.now().isoformat(), segment_id),
            )
            ve_rows = self.db.conn.execute(
                "SELECT id FROM vision_elements WHERE segment_id = ?",
                (segment_id,),
            ).fetchall()
            for ve in ve_rows:
                self._sync_vision_element_derived_fields(ve["id"])
            self.db.conn.commit()
            return True
        except sqlite3.IntegrityError as exc:
            self.db.conn.rollback()
            raise ValueError(str(exc)) from exc
        except Exception:
            self.db.conn.rollback()
            raise

    def rename_vision_subsegment(self, subsegment_id: str, new_name: str) -> bool:
        new_value = (new_name or "").strip()
        if not new_value:
            raise ValueError("SubSegment name is required.")

        current = self.db.conn.execute(
            "SELECT id, segment_id, name FROM vision_subsegments WHERE id = ?",
            (subsegment_id,),
        ).fetchone()
        if not current:
            return False

        duplicate = self.db.conn.execute(
            """
            SELECT id FROM vision_subsegments
            WHERE segment_id = ? AND LOWER(name) = LOWER(?) AND id <> ?
            """,
            (current["segment_id"], new_value, subsegment_id),
        ).fetchone()
        if duplicate:
            raise ValueError(f"SubSegment '{new_value}' already exists in this Segment.")

        try:
            self.db.conn.execute("BEGIN")
            self.db.conn.execute(
                "UPDATE vision_subsegments SET name = ?, updated_at = ? WHERE id = ?",
                (new_value, datetime.now().isoformat(), subsegment_id),
            )
            ve_rows = self.db.conn.execute(
                "SELECT id FROM vision_elements WHERE subsegment_id = ?",
                (subsegment_id,),
            ).fetchall()
            for ve in ve_rows:
                self._sync_vision_element_derived_fields(ve["id"])
            self.db.conn.commit()
            return True
        except sqlite3.IntegrityError as exc:
            self.db.conn.rollback()
            raise ValueError(str(exc)) from exc
        except Exception:
            self.db.conn.rollback()
            raise

    def rename_vision_category(self, category_id: str, new_name: str) -> bool:
        new_value = (new_name or "").strip()
        if not new_value:
            raise ValueError("Category name is required.")

        current = self.db.conn.execute(
            "SELECT id, subsegment_id, name FROM vision_categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if not current:
            return False

        duplicate = self.db.conn.execute(
            """
            SELECT id FROM vision_categories
            WHERE subsegment_id = ? AND LOWER(name) = LOWER(?) AND id <> ?
            """,
            (current["subsegment_id"], new_value, category_id),
        ).fetchone()
        if duplicate:
            raise ValueError(f"Category '{new_value}' already exists in this SubSegment.")

        try:
            self.db.conn.execute("BEGIN")
            self.db.conn.execute(
                "UPDATE vision_categories SET name = ?, updated_at = ? WHERE id = ?",
                (new_value, datetime.now().isoformat(), category_id),
            )
            ve_rows = self.db.conn.execute(
                "SELECT id FROM vision_elements WHERE category_id = ?",
                (category_id,),
            ).fetchall()
            for ve in ve_rows:
                self._sync_vision_element_derived_fields(ve["id"])
            self.db.conn.commit()
            return True
        except sqlite3.IntegrityError as exc:
            self.db.conn.rollback()
            raise ValueError(str(exc)) from exc
        except Exception:
            self.db.conn.rollback()
            raise

    def delete_vision_element(self, vision_element_id: str) -> bool:
        """Delete one Vision Element and derived annual rows via FK cascade."""
        cur = self.db.conn.execute(
            "DELETE FROM vision_elements WHERE id = ?",
            (vision_element_id,),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_segment_vision_text(self, segment_id: str, vision_text: str) -> bool:
        cur = self.db.conn.execute(
            "UPDATE vision_segments SET vision_text = ?, updated_at = ? WHERE id = ?",
            ((vision_text or "").strip(), datetime.now().isoformat(), segment_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def sync_vision_segments_with_settings(self):
        """Ensure every Settings life segment exists in vision_segments."""
        settings_rows = self.db.conn.execute("SELECT name FROM segment_descriptions").fetchall()
        now = datetime.now().isoformat()
        for row in settings_rows:
            name = (row["name"] or "").strip()
            if not name:
                continue
            existing = self.db.conn.execute(
                "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)",
                (name,),
            ).fetchone()
            if not existing:
                self.db.conn.execute(
                    "INSERT INTO vision_segments (id, name, vision_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (f"vsg-{uuid4().hex[:8]}", name, "", now, now),
                )
        self.db.conn.commit()

    def default_subsegment_color_for_segment(self, segment_name: str) -> str:
        segment_color = self.resolve_segment_color(segment_name, self.get_segment_color_map())
        return self._derive_subsegment_color(segment_color)

    def create_vision_subsegment(self, segment_name: str, subsegment_name: str, color_hex: Optional[str] = None) -> str:
        """Create a subsegment under an existing Settings segment."""
        seg_id = self._create_or_get_vision_segment(segment_name)
        return self._create_or_get_vision_subsegment(seg_id, subsegment_name, color_hex=color_hex)

    def create_vision_category(
        self,
        segment_name: str,
        subsegment_name: str,
        category_name: str,
        color_hex: Optional[str] = None,
        description: str = "",
        vision_text: str = "",
    ) -> str:
        seg_id = self._create_or_get_vision_segment(segment_name)
        sub_id = self._resolve_vision_subsegment_id(seg_id, subsegment_name)
        if not sub_id:
            raise ValueError(f"SubSegment '{subsegment_name}' does not exist under '{segment_name}'.")
        return self._create_or_get_vision_category(
            sub_id,
            category_name,
            color_hex=color_hex,
            description=description,
            vision_text=vision_text,
        )

    def get_vision_segments_admin(self) -> List[Dict[str, Any]]:
        self.sync_vision_segments_with_settings()
        cursor = self.db.conn.execute(
            """
            SELECT
                vs.id,
                vs.name,
                vs.vision_text,
                COALESCE(sd.description, '') AS description,
                COALESCE(sd.color_hex, '#334155') AS color_hex,
                COALESCE(sd.is_active, 1) AS is_active,
                sd.id AS settings_segment_id
            FROM vision_segments vs
            LEFT JOIN segment_descriptions sd ON LOWER(sd.name) = LOWER(vs.name)
            ORDER BY vs.name COLLATE NOCASE ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_vision_segment_admin(
        self,
        name: str,
        description: str,
        color_hex: str,
        vision_text: str,
        is_active: bool = True,
    ) -> str:
        segments = self.get_all_segments(active_only=False)
        next_order = (max((s.get("order_index") or 0 for s in segments), default=0) + 1)
        seg_settings_id = self.create_segment(
            name=name.strip(),
            description=(description or "").strip(),
            color_hex=color_hex.strip().upper(),
            order_index=next_order,
        )
        if not is_active:
            self.update_segment(seg_settings_id, is_active=False)
        vision_seg = self.db.conn.execute(
            "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)",
            (name.strip(),),
        ).fetchone()
        if vision_seg:
            self.update_segment_vision_text(vision_seg["id"], vision_text)
            return vision_seg["id"]
        raise ValueError("Failed to create vision segment.")

    def update_vision_segment_admin(
        self,
        segment_id: str,
        name: str,
        description: str,
        color_hex: str,
        vision_text: str,
        is_active: bool = True,
    ) -> bool:
        row = self.db.conn.execute(
            """
            SELECT sd.id AS settings_id
            FROM vision_segments vs
            LEFT JOIN segment_descriptions sd ON LOWER(sd.name) = LOWER(vs.name)
            WHERE vs.id = ?
            """,
            (segment_id,),
        ).fetchone()
        if not row:
            return False
        settings_id = row["settings_id"]
        if settings_id:
            self.update_segment(
                settings_id,
                name=name.strip(),
                description=(description or "").strip(),
                color_hex=color_hex.strip().upper(),
                is_active=1 if is_active else 0,
            )
        else:
            self._create_or_get_vision_segment(name.strip())
        seg_row = self.db.conn.execute("SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)", (name.strip(),)).fetchone()
        if not seg_row:
            return False
        self.update_segment_vision_text(seg_row["id"], vision_text)
        return True

    def delete_vision_segment_admin(self, segment_id: str) -> bool:
        row = self.db.conn.execute(
            """
            SELECT vs.id, vs.name, sd.id AS settings_id
            FROM vision_segments vs
            LEFT JOIN segment_descriptions sd ON LOWER(sd.name) = LOWER(vs.name)
            WHERE vs.id = ?
            """,
            (segment_id,),
        ).fetchone()
        if not row:
            return False
        if row["settings_id"]:
            success, _counts = self.delete_segment(row["settings_id"])
            return bool(success)
        cur = self.db.conn.execute("DELETE FROM vision_segments WHERE id = ?", (segment_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_vision_subsegment(
        self,
        subsegment_id: str,
        name: str,
        color_hex: str,
        description: str,
        vision_text: str,
    ) -> bool:
        new_name = (name or "").strip()
        if not new_name:
            raise ValueError("SubSegment name is required.")
        if color_hex and not self._is_valid_hex_color(color_hex):
            raise ValueError("Invalid color. Use #RRGGBB.")

        row = self.db.conn.execute(
            "SELECT id, segment_id, name FROM vision_subsegments WHERE id = ?",
            (subsegment_id,),
        ).fetchone()
        if not row:
            return False
        if new_name.lower() != (row["name"] or "").strip().lower():
            self.rename_vision_subsegment(subsegment_id, new_name)
        cur = self.db.conn.execute(
            "UPDATE vision_subsegments SET color_hex = ?, description = ?, vision_text = ?, updated_at = ? WHERE id = ?",
            ((color_hex or "").strip().upper() if color_hex else None, (description or "").strip(), (vision_text or "").strip(), datetime.now().isoformat(), subsegment_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_vision_category(
        self,
        category_id: str,
        name: str,
        color_hex: str,
        description: str,
        vision_text: str,
    ) -> bool:
        new_name = (name or "").strip()
        if not new_name:
            raise ValueError("Category name is required.")
        if color_hex and not self._is_valid_hex_color(color_hex):
            raise ValueError("Invalid color. Use #RRGGBB.")
        row = self.db.conn.execute(
            "SELECT id, name FROM vision_categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if not row:
            return False
        if new_name.lower() != (row["name"] or "").strip().lower():
            self.rename_vision_category(category_id, new_name)
        cur = self.db.conn.execute(
            "UPDATE vision_categories SET color_hex = ?, description = ?, vision_text = ?, updated_at = ? WHERE id = ?",
            ((color_hex or "").strip().upper() if color_hex else None, (description or "").strip(), (vision_text or "").strip(), datetime.now().isoformat(), category_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def delete_vision_subsegment(self, subsegment_id: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM vision_subsegments WHERE id = ?", (subsegment_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def delete_vision_category(self, category_id: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM vision_categories WHERE id = ?", (category_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_subsegment_vision_text(self, subsegment_id: str, vision_text: str) -> bool:
        cur = self.db.conn.execute(
            "UPDATE vision_subsegments SET vision_text = ?, updated_at = ? WHERE id = ?",
            ((vision_text or "").strip(), datetime.now().isoformat(), subsegment_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_category_vision_text(self, category_id: str, vision_text: str) -> bool:
        cur = self.db.conn.execute(
            "UPDATE vision_categories SET vision_text = ?, updated_at = ? WHERE id = ?",
            ((vision_text or "").strip(), datetime.now().isoformat(), category_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def delete_annual_records_for_vision_element(self, year: int, vision_element_id: str) -> bool:
        """Delete annual rows for one Vision Element in a specific year."""
        ape = self.db.conn.execute(
            "SELECT id FROM annual_plan_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id),
        ).fetchone()
        ape_id = ape["id"] if ape else None

        if ape_id:
            self.db.conn.execute(
                "UPDATE action_items SET annual_plan_element_id = NULL WHERE annual_plan_element_id = ?",
                (ape_id,),
            )

        self.db.conn.execute(
            "DELETE FROM annual_plan_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id),
        )
        cur = self.db.conn.execute(
            "DELETE FROM annual_vision_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def create_annual_records_from_vision_element(self, year: int, vision_element_id: str) -> Dict[str, str]:
        """Create Annual Vision Element + Annual Plan Element from a vision element."""
        row = self.db.conn.execute("""
            SELECT ve.id, ve.key_field, s.name AS segment_name, ss.name AS subsegment_name, c.name AS category_name
            FROM vision_elements ve
            JOIN vision_segments s ON s.id = ve.segment_id
            JOIN vision_subsegments ss ON ss.id = ve.subsegment_id
            JOIN vision_categories c ON c.id = ve.category_id
            WHERE ve.id = ?
        """, (vision_element_id,)).fetchone()
        if not row:
            raise ValueError("Vision element not found")

        data = dict(row)
        now = datetime.now().isoformat()

        ave_row = self.db.conn.execute(
            "SELECT id FROM annual_vision_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id)
        ).fetchone()
        if ave_row:
            ave_id = ave_row["id"]
        else:
            ave_id = f"ave-{uuid4().hex[:8]}"
            self.db.conn.execute("""
                INSERT INTO annual_vision_elements
                (id, year, vision_element_id, segment_name, subsegment_name, category_name, key_field, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ave_id, year, vision_element_id, data["segment_name"],
                data["subsegment_name"], data["category_name"], data["key_field"], now, now
            ))

        ape_row = self.db.conn.execute(
            "SELECT id FROM annual_plan_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id)
        ).fetchone()
        if ape_row:
            ape_id = ape_row["id"]
        else:
            ape_id = f"ape-{uuid4().hex[:8]}"
            self.db.conn.execute("""
                INSERT INTO annual_plan_elements
                (id, year, vision_element_id, annual_vision_element_id, segment_name, subsegment_name, category_name, key_field, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ape_id, year, vision_element_id, ave_id, data["segment_name"],
                data["subsegment_name"], data["category_name"], data["key_field"], now, now
            ))

        self.db.conn.commit()
        return {"annual_vision_element_id": ave_id, "annual_plan_element_id": ape_id}

    def get_annual_vision_elements(self, year: int) -> List[Dict[str, Any]]:
        self.sync_vision_elements_with_taxonomy()
        cursor = self.db.conn.execute("""
            SELECT * FROM annual_vision_elements
            WHERE year = ?
            ORDER BY segment_name COLLATE NOCASE ASC, subsegment_name COLLATE NOCASE ASC, category_name COLLATE NOCASE ASC
        """, (year,))
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_plan_elements(self, year: int) -> List[Dict[str, Any]]:
        cursor = self.db.conn.execute("""
            SELECT * FROM annual_plan_elements
            WHERE year = ?
            ORDER BY segment_name COLLATE NOCASE ASC, subsegment_name COLLATE NOCASE ASC, category_name COLLATE NOCASE ASC
        """, (year,))
        return [dict(row) for row in cursor.fetchall()]

    def set_annual_plan_element_quarter(self, ape_id: str, quarter: int, enabled: bool) -> bool:
        if quarter not in (1, 2, 3, 4):
            return False
        col = f"q{quarter}"
        self.db.conn.execute(
            f"UPDATE annual_plan_elements SET {col} = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, datetime.now().isoformat(), ape_id)
        )
        self.db.conn.commit()
        return True

    def set_annual_plan_element_month(self, ape_id: str, month: int, enabled: bool) -> bool:
        if month < 1 or month > 12:
            return False
        col = f"m{month}"
        self.db.conn.execute(
            f"UPDATE annual_plan_elements SET {col} = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, datetime.now().isoformat(), ape_id)
        )
        self.db.conn.commit()
        return True

    def get_annual_plan_elements_for_period(self, year: int, quarter: int, month: int) -> List[Dict[str, Any]]:
        if quarter not in (1, 2, 3, 4) or month < 1 or month > 12:
            return []
        q_col = f"q{quarter}"
        m_col = f"m{month}"
        cursor = self.db.conn.execute(f"""
            SELECT * FROM annual_plan_elements
            WHERE year = ?
              AND {q_col} = 1
              AND {m_col} = 1
            ORDER BY segment_name COLLATE NOCASE ASC, subsegment_name COLLATE NOCASE ASC, category_name COLLATE NOCASE ASC
        """, (year,))
        return [dict(row) for row in cursor.fetchall()]

    def get_month_week_starts(self, year: int, month: int, first_day_of_week: int = 0) -> List[Dict[str, Any]]:
        """
        Return week start options for a month based on configured first weekday.

        first_day_of_week: 0=Monday .. 6=Sunday
        """
        if month < 1 or month > 12:
            return []
        if first_day_of_week < 0 or first_day_of_week > 6:
            first_day_of_week = 0

        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])
        offset = (first_day_of_week - month_start.weekday()) % 7
        first_week_start = month_start + timedelta(days=offset)

        options: List[Dict[str, Any]] = []
        week_of_month = 1
        cursor = first_week_start
        while cursor <= month_end:
            week_of_year = cursor.isocalendar().week
            options.append(
                {
                    "week_of_month": week_of_month,
                    "week_of_year": week_of_year,
                    "week_start_date": cursor.isoformat(),
                    "week_end_date": (cursor + timedelta(days=6)).isoformat(),
                    "day_of_month": cursor.day,
                    "label": f"Wk{week_of_month} {cursor.day} (WOY {week_of_year})",
                }
            )
            week_of_month += 1
            cursor += timedelta(days=7)
        return options

    def get_existing_week_item_starts_for_ape(self, ape_id: str, year: int, month: int) -> List[str]:
        """Get existing weekly Action Item start dates for one APE and month."""
        rows = self.db_manager.db.conn.execute(
            """
            SELECT start_date
            FROM action_items
            WHERE annual_plan_element_id = ?
              AND item_type = 'week'
              AND start_date LIKE ?
            ORDER BY start_date ASC
            """,
            (ape_id, f"{year:04d}-{month:02d}-%"),
        ).fetchall()
        return [r["start_date"] for r in rows if r["start_date"]]

    def create_week_action_items_for_ape(self, ape_id: str, year: int, month: int,
                                         week_start_dates: List[str]) -> Dict[str, Any]:
        """
        Create weekly Action Items linked to an Annual Plan Element.
        Returns created_count, skipped_count, and created_ids.
        """
        if month < 1 or month > 12:
            raise ValueError("Month must be 1-12")
        if not week_start_dates:
            return {"created_count": 0, "skipped_count": 0, "created_ids": []}

        ape = self.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()
        if not ape:
            raise ValueError("Annual Plan Element not found")

        existing = set(self.get_existing_week_item_starts_for_ape(ape_id, year, month))
        system_defaults = self.db_manager.get_defaults("system")

        created_ids: List[str] = []
        skipped_count = 0
        key_field = ape["key_field"]
        who_value = ape["segment_name"] or "VPS"
        segment_id = self.resolve_segment_id_by_name(ape["segment_name"])

        for week_start in week_start_dates:
            if week_start in existing:
                skipped_count += 1
                continue

            ws = date.fromisoformat(week_start)
            week_of_year = ws.isocalendar().week
            we = ws + timedelta(days=6)

            item = ActionItem(
                who=who_value,
                title=f"{self.normalize_week_token(self.shorten_pipe_prefix(key_field))} - W{week_of_year}",
                description=f"Weekly action item for {key_field} (W{week_of_year}, starts {ws.isoformat()})",
                start_date=ws.isoformat(),
                due_date=we.isoformat(),
                importance=system_defaults.importance if system_defaults else None,
                urgency=system_defaults.urgency if system_defaults else None,
                size=system_defaults.size if system_defaults else None,
                value=system_defaults.value if system_defaults else None,
                category="VPS",
                status="open",
                annual_plan_element_id=ape_id,
                item_type="week",
                segment_description_id=segment_id,
            )
            created_ids.append(self.db_manager.create_action_item(item, apply_defaults=False))

        return {
            "created_count": len(created_ids),
            "skipped_count": skipped_count,
            "created_ids": created_ids,
        }

    def get_weekly_action_items(self, week_start_date: Optional[str] = None,
                                ape_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get Action Items flagged as weekly (item_type='week').
        Optionally filtered by exact week start date and/or APE linkage.
        """
        query = """
            SELECT ai.*,
                   ape.segment_name AS ape_segment_name,
                   ape.subsegment_name AS ape_subsegment_name,
                   ape.category_name AS ape_category_name
            FROM action_items ai
            LEFT JOIN annual_plan_elements ape
              ON ape.id = ai.annual_plan_element_id
            WHERE ai.item_type = 'week'
        """
        params: List[Any] = []

        if week_start_date:
            query += " AND ai.start_date = ?"
            params.append(week_start_date)

        if ape_only:
            query += " AND ai.annual_plan_element_id IS NOT NULL"

        query += " ORDER BY ai.start_date DESC, ai.title COLLATE NOCASE ASC"
        cursor = self.db.conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        self.logger.info(
            "[vps:get_weekly_action_items] db=%s week_start=%s ape_only=%s count=%d",
            self.db.db_path,
            week_start_date,
            ape_only,
            len(rows),
        )
        return rows

    def get_weekly_action_items_in_range(self, start_date: str, end_date: str,
                                         segment_ids: Optional[List[str]] = None,
                                         ape_only: bool = True) -> List[Dict[str, Any]]:
        """Return weekly action items whose start dates fall inside the range."""
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        query = """
            SELECT ai.*,
                   ape.segment_name AS ape_segment_name,
                   ape.subsegment_name AS ape_subsegment_name,
                   ape.category_name AS ape_category_name
            FROM action_items ai
            LEFT JOIN annual_plan_elements ape
              ON ape.id = ai.annual_plan_element_id
            WHERE ai.item_type = 'week'
              AND ai.start_date BETWEEN ? AND ?
        """
        params: List[Any] = [start_date, end_date]

        if ape_only:
            query += " AND ai.annual_plan_element_id IS NOT NULL"

        if segment_ids:
            placeholders = ",".join("?" for _ in segment_ids)
            query += f" AND ai.segment_description_id IN ({placeholders})"
            params.extend(segment_ids)

        query += " ORDER BY ai.start_date ASC, ai.title COLLATE NOCASE ASC"
        cursor = self.db.conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        self.logger.info(
            "[vps:get_weekly_action_items_in_range] db=%s range=%s..%s segment_ids=%s ape_only=%s count=%d",
            self.db.db_path,
            start_date,
            end_date,
            segment_ids,
            ape_only,
            len(rows),
        )
        return rows

    def get_weekly_action_item_months(self, ape_only: bool = True) -> List[Dict[str, int]]:
        """Return distinct months that contain weekly action items."""
        query = """
            SELECT DISTINCT
                CAST(strftime('%Y', start_date) AS INTEGER) AS year,
                CAST(strftime('%m', start_date) AS INTEGER) AS month
            FROM action_items
            WHERE item_type = 'week'
        """
        if ape_only:
            query += " AND annual_plan_element_id IS NOT NULL"
        query += " ORDER BY year DESC, month DESC"

        cursor = self.db.conn.execute(query)
        rows = [dict(row) for row in cursor.fetchall() if row["year"] and row["month"]]
        self.logger.info(
            "[vps:get_weekly_action_item_months] db=%s ape_only=%s count=%d",
            self.db.db_path,
            ape_only,
            len(rows),
        )
        return rows

    def get_weekly_action_item_bounds(self, ape_only: bool = True) -> Optional[Tuple[str, str]]:
        """Return the min/max start dates for weekly action items."""
        query = """
            SELECT MIN(start_date) AS min_start, MAX(start_date) AS max_start
            FROM action_items
            WHERE item_type = 'week'
        """
        if ape_only:
            query += " AND annual_plan_element_id IS NOT NULL"

        row = self.db.conn.execute(query).fetchone()
        if not row or not row["min_start"] or not row["max_start"]:
            self.logger.info(
                "[vps:get_weekly_action_item_bounds] db=%s ape_only=%s bounds=None",
                self.db.db_path,
                ape_only,
            )
            return None
        self.logger.info(
            "[vps:get_weekly_action_item_bounds] db=%s ape_only=%s bounds=%s..%s",
            self.db.db_path,
            ape_only,
            row["min_start"],
            row["max_start"],
        )
        return row["min_start"], row["max_start"]

    def get_related_actions_for_weekly_item(self, weekly_item_id: str) -> List[Dict[str, Any]]:
        """Get child Action Items under a weekly Action Item."""
        cursor = self.db.conn.execute(
            """
            SELECT *
            FROM action_items
            WHERE parent_id = ?
            ORDER BY start_date ASC, title COLLATE NOCASE ASC
            """,
            (weekly_item_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_weekly_action_item(self, weekly_item_id: str) -> bool:
        """Delete an APE weekly Action Item and its child actions."""
        self.db.conn.execute(
            "DELETE FROM action_items WHERE parent_id = ?",
            (weekly_item_id,),
        )
        cur = self.db.conn.execute(
            "DELETE FROM action_items WHERE id = ? AND item_type = 'week'",
            (weekly_item_id,),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    # ========================================================================
    # SEGMENT DESCRIPTIONS
    # ========================================================================

    def get_all_segments(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all life segments."""
        query = "SELECT * FROM segment_descriptions"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY order_index"

        cursor = self.db.conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_segment_color_map(self) -> Dict[str, str]:
        """Get segment color map keyed by lowercase segment name."""
        cursor = self.db.conn.execute(
            "SELECT name, color_hex FROM segment_descriptions"
        )
        color_map: Dict[str, str] = {}
        for row in cursor.fetchall():
            name = (row["name"] or "").strip().lower()
            if name:
                color_map[name] = row["color_hex"] or "#334155"
        return color_map

    def get_segment_colors_by_id(self) -> Dict[str, str]:
        """Return a mapping of segment IDs to their configured colors."""
        cursor = self.db.conn.execute(
            "SELECT id, color_hex FROM segment_descriptions"
        )
        colors: Dict[str, str] = {}
        for row in cursor.fetchall():
            color = (row["color_hex"] or "").strip() or "#334155"
            colors[row["id"]] = color
        return colors

    def resolve_segment_id_by_name(self, segment_name: Optional[str]) -> Optional[str]:
        """Resolve a segment_description_id using a case-insensitive name match."""
        if not segment_name:
            return None
        row = self.db.conn.execute(
            "SELECT id FROM segment_descriptions WHERE LOWER(name) = LOWER(?)",
            (segment_name.strip(),),
        ).fetchone()
        return row["id"] if row else None

    def resolve_segment_color(self, segment_name: str, color_map: Optional[Dict[str, str]] = None) -> str:
        """
        Resolve a segment color by exact/fuzzy match against settings segments.
        Falls back to a deterministic palette color.
        """
        if color_map is None:
            color_map = self.get_segment_color_map()

        raw = (segment_name or "").strip()
        if not raw:
            return "#64748B"

        key = raw.lower()
        if key in color_map:
            return color_map[key]

        norm = re.sub(r"[^a-z0-9]", "", key)
        if not norm:
            return "#64748B"

        # Fuzzy match: normalized equality / prefix / containment
        for existing_name, color in color_map.items():
            existing_norm = re.sub(r"[^a-z0-9]", "", existing_name.lower())
            if not existing_norm:
                continue
            if norm == existing_norm or norm.startswith(existing_norm) or existing_norm.startswith(norm):
                return color
            if norm in existing_norm or existing_norm in norm:
                return color

        # Deterministic fallback by segment name hash
        palette = ["#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#F97316"]
        return palette[sum(ord(c) for c in norm) % len(palette)]

    def get_segment(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific segment by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM segment_descriptions WHERE id = ?",
            (segment_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_segment(self, name: str, description: str, color_hex: str,
                       order_index: int) -> str:
        """Create a new life segment."""
        segment_id = f"seg-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO segment_descriptions
            (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (segment_id, name, description, color_hex, order_index, now, now))

        # Keep Vision Elements segment vocabulary in sync with Settings segments.
        self._create_or_get_vision_segment(name)
        self.db.conn.commit()
        return segment_id

    def update_segment(self, segment_id: str, **kwargs) -> bool:
        """Update a segment's fields."""
        allowed_fields = {'name', 'description',
                          'color_hex', 'order_index', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        current = self.db.conn.execute(
            "SELECT name FROM segment_descriptions WHERE id = ?",
            (segment_id,),
        ).fetchone()
        if not current:
            return False

        old_name = current["name"]
        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [segment_id]

        self.db.conn.execute(
            f"UPDATE segment_descriptions SET {set_clause} WHERE id = ?",
            values
        )

        # If the segment display name changed in Settings, rename linked vision segment.
        if "name" in updates and updates["name"] and updates["name"] != old_name:
            new_name = updates["name"].strip()
            vision_seg = self.db.conn.execute(
                "SELECT id FROM vision_segments WHERE LOWER(name) = LOWER(?)",
                (old_name,),
            ).fetchone()
            if vision_seg:
                self.db.conn.execute(
                    "UPDATE vision_segments SET name = ?, updated_at = ? WHERE id = ?",
                    (new_name, datetime.now().isoformat(), vision_seg["id"]),
                )
                ve_rows = self.db.conn.execute(
                    "SELECT id FROM vision_elements WHERE segment_id = ?",
                    (vision_seg["id"],),
                ).fetchall()
                for ve in ve_rows:
                    self._sync_vision_element_derived_fields(ve["id"])
            else:
                seg_id = f"vsg-{uuid4().hex[:8]}"
                now = datetime.now().isoformat()
                self.db.conn.execute(
                    "INSERT INTO vision_segments (id, name, vision_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (seg_id, new_name, "", now, now),
                )
        self.db.conn.commit()
        return True

    # ========================================================================
    # TL_VISIONS (Top Level Visions)
    # ========================================================================

    def get_tl_visions(self, segment_id: Optional[str] = None,
                       active_only: bool = True) -> List[Dict[str, Any]]:
        """Get TL visions, optionally filtered by segment."""
        query = "SELECT * FROM tl_visions WHERE 1=1"
        params = []

        if segment_id:
            query += " AND segment_description_id = ?"
            params.append(segment_id)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY start_year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_tl_vision(self, vision_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific TL vision by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM tl_visions WHERE id = ?",
            (vision_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_tl_vision(self, segment_description_id: str, start_year: int,
                         end_year: int, title: str, vision_statement: str = "",
                         success_metrics: str = "[]") -> str:
        """Create a new TL vision."""
        vision_id = f"tlv-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO tl_visions
            (id, segment_description_id, start_year, end_year, title, vision_statement,
             success_metrics, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (vision_id, segment_description_id, start_year, end_year, title,
              vision_statement, success_metrics, now, now))

        self.db.conn.commit()
        return vision_id

    def update_tl_vision(self, vision_id: str, **kwargs) -> bool:
        """Update a TL vision's fields."""
        allowed_fields = {'title', 'vision_statement', 'success_metrics',
                          'review_date', 'is_active', 'start_year', 'end_year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [vision_id]

        self.db.conn.execute(
            f"UPDATE tl_visions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # ANNUAL_VISIONS
    # ========================================================================

    def get_annual_visions(self, tl_vision_id: Optional[str] = None,
                           year: Optional[int] = None,
                           active_only: bool = True) -> List[Dict[str, Any]]:
        """Get annual visions, optionally filtered."""
        query = "SELECT * FROM annual_visions WHERE 1=1"
        params = []

        if tl_vision_id:
            query += " AND tl_vision_id = ?"
            params.append(tl_vision_id)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_vision(self, vision_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific annual vision by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM annual_visions WHERE id = ?",
            (vision_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_annual_vision(self, tl_vision_id: str, segment_description_id: str,
                             year: int, title: str, vision_statement: str = "",
                             key_priorities: str = "[]") -> str:
        """Create a new annual vision."""
        vision_id = f"av-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO annual_visions
            (id, tl_vision_id, segment_description_id, year, title, vision_statement,
             key_priorities, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (vision_id, tl_vision_id, segment_description_id, year, title,
              vision_statement, key_priorities, now, now))

        self.db.conn.commit()
        return vision_id

    def update_annual_vision(self, vision_id: str, **kwargs) -> bool:
        """Update an annual vision's fields."""
        allowed_fields = {'title', 'vision_statement',
                          'key_priorities', 'is_active', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [vision_id]

        self.db.conn.execute(
            f"UPDATE annual_visions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # ANNUAL_PLANS
    # ========================================================================

    def get_annual_plans(self, annual_vision_id: Optional[str] = None,
                         year: Optional[int] = None,
                         active_only: bool = True) -> List[Dict[str, Any]]:
        """Get annual plans, optionally filtered."""
        query = "SELECT * FROM annual_plans WHERE 1=1"
        params = []

        if annual_vision_id:
            query += " AND annual_vision_id = ?"
            params.append(annual_vision_id)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific annual plan by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM annual_plans WHERE id = ?",
            (plan_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_annual_plan(self, annual_vision_id: str, segment_description_id: str,
                           year: int, theme: str, objective: str = "",
                           description: str = "") -> str:
        """Create a new annual plan."""
        plan_id = f"ap-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO annual_plans
            (id, annual_vision_id, segment_description_id, year, theme, objective,
             description, status, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', 1, ?, ?)
        """, (plan_id, annual_vision_id, segment_description_id, year, theme,
              objective, description, now, now))

        self.db.conn.commit()
        return plan_id

    def update_annual_plan(self, plan_id: str, **kwargs) -> bool:
        """Update an annual plan's fields."""
        allowed_fields = {'theme', 'objective', 'description', 'status',
                          'target_date', 'is_active', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [plan_id]

        self.db.conn.execute(
            f"UPDATE annual_plans SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # ANNUAL_INITIATIVES
    # ========================================================================

    def get_annual_initiatives(self, annual_plan_id: Optional[str] = None,
                               year: Optional[int] = None,
                               active_only: bool = True) -> List[Dict[str, Any]]:
        """Get annual initiatives, optionally filtered."""
        query = "SELECT * FROM annual_initiatives WHERE 1=1"
        params = []

        if annual_plan_id:
            query += " AND annual_plan_id = ?"
            params.append(annual_plan_id)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year DESC, created_at ASC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_annual_initiative(self, initiative_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific annual initiative by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM annual_initiatives WHERE id = ?",
            (initiative_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_annual_initiative(self, annual_plan_id: str, segment_description_id: str,
                                 year: int, title: str, description: str = "",
                                 outcome_statement: str = "",
                                 auto_create_chain: bool = True) -> str:
        """Create a new annual initiative."""
        initiative_id = f"ai-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO annual_initiatives
            (id, annual_plan_id, segment_description_id, year, title, description,
             outcome_statement, status, progress_pct, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', 0, 1, ?, ?)
        """, (initiative_id, annual_plan_id, segment_description_id, year, title,
              description, outcome_statement, now, now))

        self.db.conn.commit()

        if auto_create_chain:
            self._auto_create_initial_chain_for_annual_initiative(initiative_id)

        return initiative_id

    def _auto_create_initial_chain_for_annual_initiative(self, annual_initiative_id: str) -> Dict[str, Any]:
        """
        Auto-create 1 quarter, 1 month, and 4 weeks for a new annual initiative.

        Naming format:
        - {AI title} Q1
        - {AI title} M1
        - {AI title} W1..W4
        """
        annual_initiative = self.get_annual_initiative(annual_initiative_id)
        if not annual_initiative:
            return {}

        title_prefix = (annual_initiative.get("title") or "").strip() or "Annual Initiative"
        year = int(annual_initiative["year"])
        segment_id = annual_initiative["segment_description_id"]

        quarter = 1
        quarter_id = self.create_quarter_initiative(
            annual_initiative_id=annual_initiative_id,
            segment_description_id=segment_id,
            quarter=quarter,
            year=year,
            title=f"{title_prefix} Q{quarter}",
            auto_create_chain=False,
        )

        month_num = 1
        month_id = self.create_month_tactic(
            quarter_initiative_id=quarter_id,
            segment_description_id=segment_id,
            month=month_num,
            year=year,
            priority_focus=f"{title_prefix} M{month_num}",
            description="",
        )

        month_start = date(year, month_num, 1)
        week_start = month_start - timedelta(days=month_start.weekday())
        if week_start < month_start:
            week_start += timedelta(days=7)

        week_ids: List[str] = []
        for idx in range(4):
            ws = week_start + timedelta(days=idx * 7)
            we = ws + timedelta(days=6)
            week_id = self.create_week_action(
                month_tactic_id=month_id,
                segment_description_id=segment_id,
                week_start_date=ws.isoformat(),
                week_end_date=we.isoformat(),
                title=f"{title_prefix} W{idx + 1}",
                description="",
                outcome_expected="",
            )
            week_ids.append(week_id)

        return {
            "annual_initiative_id": annual_initiative_id,
            "quarter_initiative_id": quarter_id,
            "month_tactic_id": month_id,
            "week_action_ids": week_ids,
        }

    def update_annual_initiative(self, initiative_id: str, **kwargs) -> bool:
        """Update an annual initiative's fields."""
        allowed_fields = {'title', 'description', 'outcome_statement',
                          'status', 'progress_pct', 'is_active', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [initiative_id]

        self.db.conn.execute(
            f"UPDATE annual_initiatives SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # QUARTER_INITIATIVES
    # ========================================================================

    def get_quarter_initiatives(self, annual_initiative_id: Optional[str] = None,
                                annual_plan_id: Optional[str] = None,
                                quarter: Optional[int] = None,
                                year: Optional[int] = None,
                                active_only: bool = True) -> List[Dict[str, Any]]:
        """Get quarter initiatives, optionally filtered."""
        query = "SELECT * FROM quarter_initiatives WHERE 1=1"
        params = []

        if annual_initiative_id:
            query += " AND annual_initiative_id = ?"
            params.append(annual_initiative_id)
        elif annual_plan_id:
            query += " AND annual_plan_id = ?"
            params.append(annual_plan_id)

        if quarter:
            query += " AND quarter = ?"
            params.append(quarter)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year ASC, quarter ASC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_quarter_initiative(self, initiative_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific quarter initiative by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM quarter_initiatives WHERE id = ?",
            (initiative_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_next_quarter_for_annual_initiative(self, annual_initiative_id: str) -> Dict[str, int]:
        """
        Determine next quarter/year defaults for a new quarter initiative.

        Rules:
        - No existing quarter initiatives -> use annual initiative year + Q1
        - Existing -> increment from latest by (year, quarter)
          Q4 rolls over to Q1 of next year
        """
        annual_initiative = self.get_annual_initiative(annual_initiative_id)
        if not annual_initiative:
            return {"year": datetime.now().year, "quarter": 1}

        existing = self.get_quarter_initiatives(
            annual_initiative_id=annual_initiative_id,
            active_only=False
        )
        if not existing:
            return {"year": int(annual_initiative["year"]), "quarter": 1}

        latest = max(existing, key=lambda q: (int(q["year"]), int(q["quarter"])))
        latest_year = int(latest["year"])
        latest_quarter = int(latest["quarter"])

        if latest_quarter >= 4:
            return {"year": latest_year + 1, "quarter": 1}
        return {"year": latest_year, "quarter": latest_quarter + 1}

    def create_quarter_initiative(self, segment_description_id: str,
                                  quarter: int, year: int, title: str,
                                  annual_initiative_id: Optional[str] = None,
                                  annual_plan_id: Optional[str] = None,
                                  auto_create_chain: bool = True,
                                  outcome_statement: str = "",
                                  tracking_measures: str = "[]") -> str:
        """Create a new quarter initiative."""
        initiative_id = f"qi-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        if not annual_initiative_id:
            # Backward compatibility: callers may still pass annual_plan_id only.
            if not annual_plan_id:
                raise ValueError(
                    "annual_initiative_id is required. Quarter initiatives must be linked to an annual initiative."
                )
            existing = self.get_annual_initiatives(
                annual_plan_id=annual_plan_id,
                year=year,
                active_only=False
            )
            if existing:
                annual_initiative_id = existing[0]["id"]
            else:
                plan = self.get_annual_plan(annual_plan_id)
                if not plan:
                    raise ValueError("Annual plan not found")
                ai_title = (plan.get("theme") or title or "Annual Initiative").strip()
                annual_initiative_id = self.create_annual_initiative(
                    annual_plan_id=annual_plan_id,
                    segment_description_id=segment_description_id,
                    year=year,
                    title=ai_title,
                    auto_create_chain=False,
                )

        annual_initiative = self.get_annual_initiative(annual_initiative_id)
        if not annual_initiative:
            raise ValueError("Annual initiative not found")
        annual_plan_id = annual_initiative['annual_plan_id']
        ai_title = (annual_initiative.get("title") or "").strip() or "Annual Initiative"

        # Auto title for new quarter initiatives under an annual initiative
        auto_title = f"{ai_title} Q{quarter}"
        final_title = (title or "").strip() or auto_title

        self.db.conn.execute("""
            INSERT INTO quarter_initiatives
            (id, annual_plan_id, annual_initiative_id, segment_description_id, quarter, year, title,
             outcome_statement, tracking_measures, status, progress_pct, is_active,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_started', 0, 1, ?, ?)
        """, (initiative_id, annual_plan_id, annual_initiative_id, segment_description_id, quarter, year,
              final_title, outcome_statement, tracking_measures, now, now))

        self.db.conn.commit()

        if auto_create_chain:
            self._auto_create_initial_chain_for_quarter_initiative(initiative_id)

        return initiative_id

    def _auto_create_initial_chain_for_quarter_initiative(self, quarter_initiative_id: str) -> Dict[str, Any]:
        """
        Auto-create 1 month tactic and 4 week actions for a quarter initiative.
        """
        quarter_initiative = self.get_quarter_initiative(quarter_initiative_id)
        if not quarter_initiative:
            return {}

        quarter = int(quarter_initiative["quarter"])
        year = int(quarter_initiative["year"])
        segment_id = quarter_initiative["segment_description_id"]
        qi_title = (quarter_initiative.get("title") or "").strip() or f"Q{quarter}"

        # First month of the selected quarter: Q1=1, Q2=4, Q3=7, Q4=10
        month_num = ((quarter - 1) * 3) + 1
        month_title_index = quarter
        month_id = self.create_month_tactic(
            quarter_initiative_id=quarter_initiative_id,
            segment_description_id=segment_id,
            month=month_num,
            year=year,
            priority_focus=f"{qi_title} M{month_title_index}",
            description="",
            auto_create_weeks=True,
        )

        week_actions = self.get_week_actions(month_tactic_id=month_id, active_only=False)
        week_ids = [wa["id"] for wa in week_actions]

        return {
            "quarter_initiative_id": quarter_initiative_id,
            "month_tactic_id": month_id,
            "week_action_ids": week_ids,
        }

    def update_quarter_initiative(self, initiative_id: str, **kwargs) -> bool:
        """Update a quarter initiative's fields."""
        allowed_fields = {'title', 'outcome_statement', 'tracking_measures',
                          'status', 'progress_pct', 'is_active', 'quarter', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [initiative_id]

        self.db.conn.execute(
            f"UPDATE quarter_initiatives SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # MONTH_TACTICS
    # ========================================================================

    def get_month_tactics(self, quarter_initiative_id: Optional[str] = None,
                          month: Optional[int] = None,
                          year: Optional[int] = None,
                          active_only: bool = True) -> List[Dict[str, Any]]:
        """Get month tactics, optionally filtered."""
        query = "SELECT * FROM month_tactics WHERE 1=1"
        params = []

        if quarter_initiative_id:
            query += " AND quarter_initiative_id = ?"
            params.append(quarter_initiative_id)

        if month:
            query += " AND month = ?"
            params.append(month)

        if year:
            query += " AND year = ?"
            params.append(year)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY year ASC, month ASC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_month_tactic(self, tactic_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific month tactic by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM month_tactics WHERE id = ?",
            (tactic_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_month_tactic(self, quarter_initiative_id: str, segment_description_id: str,
                            month: int, year: int, priority_focus: str,
                            description: str = "",
                            auto_create_weeks: bool = True) -> str:
        """Create a new month tactic."""
        tactic_id = f"mt-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO month_tactics
            (id, quarter_initiative_id, segment_description_id, month, year,
             priority_focus, description, status, progress_pct, is_active,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', 0, 1, ?, ?)
        """, (tactic_id, quarter_initiative_id, segment_description_id, month, year,
              priority_focus, description, now, now))

        self.db.conn.commit()

        if auto_create_weeks:
            self._auto_create_week_actions_for_month_tactic(tactic_id)

        return tactic_id

    def get_next_month_for_quarter_initiative(self, quarter_initiative_id: str) -> Dict[str, int]:
        """
        Determine next month/year defaults for a month tactic under a quarter initiative.

        Rules:
        - No month tactics: first month of quarter (Q1=Jan, Q2=Apr, Q3=Jul, Q4=Oct)
        - Existing month tactics: next month after latest by (year, month)
        """
        quarter_initiative = self.get_quarter_initiative(quarter_initiative_id)
        if not quarter_initiative:
            today = date.today()
            return {"year": today.year, "month": today.month}

        existing = self.get_month_tactics(
            quarter_initiative_id=quarter_initiative_id,
            active_only=False
        )
        if not existing:
            quarter = int(quarter_initiative["quarter"])
            year = int(quarter_initiative["year"])
            month = ((quarter - 1) * 3) + 1
            return {"year": year, "month": month}

        latest = max(existing, key=lambda m: (int(m["year"]), int(m["month"])))
        month = int(latest["month"]) + 1
        year = int(latest["year"])
        if month > 12:
            month = 1
            year += 1
        return {"year": year, "month": month}

    def _auto_create_week_actions_for_month_tactic(self, month_tactic_id: str) -> List[str]:
        """Auto-create 4 weekly tactics for a month tactic."""
        month_tactic = self.get_month_tactic(month_tactic_id)
        if not month_tactic:
            return []

        year = int(month_tactic["year"])
        month = int(month_tactic["month"])
        segment_id = month_tactic["segment_description_id"]
        quarter_initiative = self.get_quarter_initiative(month_tactic["quarter_initiative_id"])
        quarter_title = (quarter_initiative.get("title") if quarter_initiative else "") or "Quarter"

        month_start = date(year, month, 1)
        week_start = month_start - timedelta(days=month_start.weekday())
        if week_start < month_start:
            week_start += timedelta(days=7)

        created: List[str] = []
        for idx in range(4):
            ws = week_start + timedelta(days=idx * 7)
            we = ws + timedelta(days=6)
            wa_id = self.create_week_action(
                month_tactic_id=month_tactic_id,
                segment_description_id=segment_id,
                week_start_date=ws.isoformat(),
                week_end_date=we.isoformat(),
                title=f"{quarter_title} W{idx + 1}",
                description="",
                outcome_expected="",
            )
            created.append(wa_id)
        return created

    def update_month_tactic(self, tactic_id: str, **kwargs) -> bool:
        """Update a month tactic's fields."""
        allowed_fields = {'priority_focus', 'description', 'status',
                          'progress_pct', 'is_active', 'month', 'year'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [tactic_id]

        self.db.conn.execute(
            f"UPDATE month_tactics SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    # ========================================================================
    # WEEK_ACTIONS
    # ========================================================================

    def get_week_actions(self, month_tactic_id: Optional[str] = None,
                         week_start_date: Optional[str] = None,
                         active_only: bool = True) -> List[Dict[str, Any]]:
        """Get week actions, optionally filtered."""
        query = "SELECT * FROM week_actions WHERE 1=1"
        params = []

        if month_tactic_id:
            query += " AND month_tactic_id = ?"
            params.append(month_tactic_id)

        if week_start_date:
            query += " AND week_start_date = ?"
            params.append(week_start_date)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY week_start_date ASC, order_index"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_week_actions_in_range(self, start_date: str, end_date: str,
                                  segment_ids: Optional[List[str]] = None,
                                  active_only: bool = True) -> List[Dict[str, Any]]:
        """Get week actions whose week_start_date falls within the provided range."""
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        query = "SELECT * FROM week_actions WHERE week_start_date BETWEEN ? AND ?"
        params: List[Any] = [start_date, end_date]

        if active_only:
            query += " AND is_active = 1"

        if segment_ids:
            placeholders = ",".join("?" for _ in segment_ids)
            query += f" AND segment_description_id IN ({placeholders})"
            params.extend(segment_ids)

        query += " ORDER BY week_start_date ASC, title COLLATE NOCASE ASC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_week_action_months(self, active_only: bool = True) -> List[Dict[str, int]]:
        """Return distinct year/month pairs where weekly tactics exist."""
        query = """
            SELECT DISTINCT
                CAST(strftime('%Y', week_start_date) AS INTEGER) AS year,
                CAST(strftime('%m', week_start_date) AS INTEGER) AS month
            FROM week_actions
        """
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY year DESC, month DESC"

        cursor = self.db.conn.execute(query)
        return [dict(row) for row in cursor.fetchall() if row["year"] and row["month"]]

    def get_week_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific week action by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM week_actions WHERE id = ?",
            (action_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_week_action(self, month_tactic_id: str, segment_description_id: str,
                           week_start_date: str, week_end_date: str, title: str,
                           description: str = "", outcome_expected: str = "",
                           step_1: str = "", step_2: str = "", step_3: str = "",
                           step_4: str = "", step_5: str = "",
                           key_result_1: str = "", key_result_2: str = "", key_result_3: str = "",
                           key_result_4: str = "", key_result_5: str = "") -> str:
        """Create a new week action."""
        action_id = f"wa-{uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        self.db.conn.execute("""
            INSERT INTO week_actions
            (id, month_tactic_id, segment_description_id, week_start_date, week_end_date,
             title, description, outcome_expected, status, is_active, created_at, updated_at,
             step_1, step_2, step_3, step_4, step_5,
             key_result_1, key_result_2, key_result_3, key_result_4, key_result_5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (action_id, month_tactic_id, segment_description_id, week_start_date,
              week_end_date, title, description, outcome_expected, now, now,
              step_1, step_2, step_3, step_4, step_5,
              key_result_1, key_result_2, key_result_3, key_result_4, key_result_5))

        self.db.conn.commit()
        return action_id

    def update_week_action(self, action_id: str, **kwargs) -> bool:
        """Update a week action's fields."""
        allowed_fields = {'title', 'description', 'outcome_expected', 'status',
                          'order_index', 'is_active', 'week_start_date', 'week_end_date',
                          'step_1', 'step_2', 'step_3', 'step_4', 'step_5',
                          'key_result_1', 'key_result_2', 'key_result_3', 'key_result_4', 'key_result_5'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [action_id]

        self.db.conn.execute(
            f"UPDATE week_actions SET {set_clause} WHERE id = ?",
            values
        )
        self.db.conn.commit()
        return True

    def auto_create_action_items_from_steps(self, week_action_id: str) -> List[str]:
        """
        Auto-create Action Items from non-blank Step fields in a Week Action.
        This method is idempotent - it won't create duplicates if called multiple times.
        Returns list of created action item IDs.
        """
        from datetime import timedelta
        from .models import ActionItem
        import re

        # Get the week action
        week_action = self.get_week_action(week_action_id)
        if not week_action:
            return []

        week_start_date = week_action['week_start_date']
        segment_id = week_action['segment_description_id']
        created_item_ids = []

        # Get existing Action Items for this Week Action
        existing_items = self.get_action_items_for_week_action(week_action_id)

        # Determine which steps already have Action Items by checking descriptions
        existing_step_numbers = set()
        for item in existing_items:
            desc = item.get('description', '')
            # Look for "Step {i}:" pattern in description
            match = re.match(r'Step (\d+):', desc)
            if match:
                existing_step_numbers.add(int(match.group(1)))

        # Process each step field
        day_offset = 0
        for i in range(1, 6):
            step_field = f'step_{i}'
            key_result_field = f'key_result_{i}'

            step_value = week_action.get(step_field, '').strip(
            ) if week_action.get(step_field) else ''
            key_result_value = week_action.get(key_result_field, '').strip(
            ) if week_action.get(key_result_field) else ''

            # Only create Action Item if Step is non-blank AND doesn't already have an item
            if step_value and i not in existing_step_numbers:
                # Calculate start date (week_start + day_offset)
                from datetime import datetime
                start_dt = datetime.fromisoformat(week_start_date)
                item_start_date = (
                    start_dt + timedelta(days=day_offset)).date().isoformat()

                # Build description from Step and Key Result
                description = f"Step {i}: {step_value}"
                if key_result_value:
                    description += f"\nKey Result: {key_result_value}"

                # Create Action Item using db_manager
                action_item = ActionItem(
                    who="",  # Will be filled by system defaults
                    # Use step as title (limit to reasonable length)
                    title=step_value[:100],
                    description=description,
                    start_date=item_start_date,
                    week_action_id=week_action_id,
                    segment_description_id=segment_id
                )

                # Create the item (apply_defaults=True will use system defaults)
                item_id = self.db_manager.create_action_item(
                    action_item, apply_defaults=True)
                created_item_ids.append(item_id)

                # Increment day offset for next action item
                day_offset += 1

        return created_item_ids

    # ========================================================================
    # ACTION ITEMS (VPS Extensions)
    # ========================================================================

    def link_action_item_to_week_action(self, action_item_id: str,
                                        week_action_id: str,
                                        segment_description_id: str) -> bool:
        """Link an action item to a week action."""
        self.db.conn.execute("""
            UPDATE action_items
            SET week_action_id = ?, segment_description_id = ?, updated_at = ?
            WHERE id = ?
        """, (week_action_id, segment_description_id, datetime.now().isoformat(),
              action_item_id))

        self.db.conn.commit()
        return True

    def get_action_items_for_week_action(self, week_action_id: str) -> List[Dict[str, Any]]:
        """Get all action items linked to a week action."""
        cursor = self.db.conn.execute("""
            SELECT * FROM action_items
            WHERE week_action_id = ?
            ORDER BY start_date, title
        """, (week_action_id,))

        return [dict(row) for row in cursor.fetchall()]

    def create_action_items_for_week_action(self, week_action_id: str, titles: List[str]) -> List[str]:
        """Create up to 5 Action Items linked to a week action."""
        from .models import ActionItem

        week_action = self.get_week_action(week_action_id)
        if not week_action:
            return []

        clean_titles = [t.strip() for t in titles if t and t.strip()][:5]
        if not clean_titles:
            return []

        created_ids: List[str] = []
        base_start = datetime.fromisoformat(week_action["week_start_date"]).date()

        for idx, title in enumerate(clean_titles):
            start_date = (base_start + timedelta(days=idx)).isoformat()
            item = ActionItem(
                who="",
                title=title[:100],
                description=None,
                start_date=start_date,
                week_action_id=week_action_id,
                segment_description_id=week_action["segment_description_id"],
            )
            created_ids.append(self.db_manager.create_action_item(item, apply_defaults=True))

        return created_ids

    def get_action_item(self, action_item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single action item by ID."""
        cursor = self.db.conn.execute("""
            SELECT * FROM action_items
            WHERE id = ?
        """, (action_item_id,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def update_action_item(self, action_item_id: str, **kwargs) -> bool:
        """Update an action item with provided fields."""
        if not kwargs:
            return False

        # Build update query dynamically
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)

        # Add updated_at timestamp
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(action_item_id)

        query = f"""
            UPDATE action_items
            SET {', '.join(fields)}
            WHERE id = ?
        """

        self.db.conn.execute(query, values)
        self.db.conn.commit()
        return True

    # ========================================================================
    # HABIT TRACKING
    # ========================================================================

    def create_habit_tracking_days(self, action_item_id: str, start_date: str,
                                   end_date: str) -> int:
        """Create habit tracking records for each day in date range."""
        from datetime import datetime, timedelta

        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        count = 0
        current = start
        while current <= end:
            tracking_id = f"ht-{uuid4().hex[:8]}"
            now = datetime.now().isoformat()

            try:
                self.db.conn.execute("""
                    INSERT INTO habit_tracking
                    (id, action_item_id, tracking_date, is_completed, created_at)
                    VALUES (?, ?, ?, 0, ?)
                """, (tracking_id, action_item_id, current.date().isoformat(), now))
                count += 1
            except sqlite3.IntegrityError:
                # Day already exists, skip
                pass

            current += timedelta(days=1)

        self.db.conn.commit()
        return count

    def toggle_habit_day(self, action_item_id: str, tracking_date: str,
                         is_completed: bool, notes: str = "") -> bool:
        """Toggle habit completion for a specific day."""
        self.db.conn.execute("""
            UPDATE habit_tracking
            SET is_completed = ?, notes = ?
            WHERE action_item_id = ? AND tracking_date = ?
        """, (1 if is_completed else 0, notes, action_item_id, tracking_date))

        self.db.conn.commit()

        # Recalculate percent_complete
        self._update_habit_percent_complete(action_item_id)
        return True

    def get_habit_tracking(self, action_item_id: str) -> List[Dict[str, Any]]:
        """Get all habit tracking records for an action item."""
        cursor = self.db.conn.execute("""
            SELECT * FROM habit_tracking
            WHERE action_item_id = ?
            ORDER BY tracking_date
        """, (action_item_id,))

        return [dict(row) for row in cursor.fetchall()]

    def _update_habit_percent_complete(self, action_item_id: str):
        """Recalculate and update percent_complete for a habit."""
        cursor = self.db.conn.execute("""
            SELECT
                COUNT(*) as total_days,
                SUM(is_completed) as completed_days
            FROM habit_tracking
            WHERE action_item_id = ?
        """, (action_item_id,))

        row = cursor.fetchone()
        total = row['total_days']
        completed = row['completed_days'] or 0

        percent = int((completed / total) * 100) if total > 0 else 0

        self.db.conn.execute("""
            UPDATE action_items
            SET percent_complete = ?, updated_at = ?
            WHERE id = ?
        """, (percent, datetime.now().isoformat(), action_item_id))

        self.db.conn.commit()

    # ========================================================================
    # HIERARCHY NAVIGATION
    # ========================================================================

    def get_full_hierarchy_for_segment(self, segment_id: str) -> Dict[str, Any]:
        """Get complete planning hierarchy for a segment."""
        segment = self.get_segment(segment_id)
        if not segment:
            return {}

        tl_visions = self.get_tl_visions(segment_id=segment_id)

        for tl_vision in tl_visions:
            tl_vision['annual_visions'] = self.get_annual_visions(
                tl_vision_id=tl_vision['id']
            )

            for annual_vision in tl_vision['annual_visions']:
                annual_vision['annual_plans'] = self.get_annual_plans(
                    annual_vision_id=annual_vision['id']
                )

                for annual_plan in annual_vision['annual_plans']:
                    annual_plan['annual_initiatives'] = self.get_annual_initiatives(
                        annual_plan_id=annual_plan['id']
                    )

                    for annual_initiative in annual_plan['annual_initiatives']:
                        annual_initiative['quarter_initiatives'] = self.get_quarter_initiatives(
                            annual_initiative_id=annual_initiative['id']
                        )

                        for quarter_initiative in annual_initiative['quarter_initiatives']:
                            quarter_initiative['month_tactics'] = self.get_month_tactics(
                                quarter_initiative_id=quarter_initiative['id']
                            )

                            for month_tactic in quarter_initiative['month_tactics']:
                                month_tactic['week_actions'] = self.get_week_actions(
                                    month_tactic_id=month_tactic['id']
                                )

                                for week_action in month_tactic['week_actions']:
                                    week_action['action_items'] = self.get_action_items_for_week_action(
                                        week_action['id']
                                    )

        return {
            'segment': segment,
            'tl_visions': tl_visions
        }

    def get_hierarchy_breadcrumb(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """Get breadcrumb trail from segment down to specific entity."""
        breadcrumb = []

        if entity_type == 'week_action':
            week_action = self.get_week_action(entity_id)
            if week_action:
                breadcrumb.insert(
                    0, {'type': 'week_action', 'data': week_action})
                entity_type = 'month_tactic'
                entity_id = week_action['month_tactic_id']

        if entity_type == 'month_tactic':
            month_tactic = self.get_month_tactic(entity_id)
            if month_tactic:
                breadcrumb.insert(
                    0, {'type': 'month_tactic', 'data': month_tactic})
                entity_type = 'quarter_initiative'
                entity_id = month_tactic['quarter_initiative_id']

        if entity_type == 'quarter_initiative':
            quarter_initiative = self.get_quarter_initiative(entity_id)
            if quarter_initiative:
                breadcrumb.insert(
                    0, {'type': 'quarter_initiative', 'data': quarter_initiative})
                # Keep breadcrumb shape stable for existing UI/tests:
                # segment -> tl_vision -> annual_vision -> annual_plan -> quarter -> month -> week
                entity_type = 'annual_plan'
                entity_id = quarter_initiative['annual_plan_id']

        if entity_type == 'annual_initiative':
            annual_initiative = self.get_annual_initiative(entity_id)
            if annual_initiative:
                breadcrumb.insert(
                    0, {'type': 'annual_initiative', 'data': annual_initiative})
                entity_type = 'annual_plan'
                entity_id = annual_initiative['annual_plan_id']

        if entity_type == 'annual_plan':
            annual_plan = self.get_annual_plan(entity_id)
            if annual_plan:
                breadcrumb.insert(
                    0, {'type': 'annual_plan', 'data': annual_plan})
                entity_type = 'annual_vision'
                entity_id = annual_plan['annual_vision_id']

        if entity_type == 'annual_vision':
            annual_vision = self.get_annual_vision(entity_id)
            if annual_vision:
                breadcrumb.insert(
                    0, {'type': 'annual_vision', 'data': annual_vision})
                entity_type = 'tl_vision'
                entity_id = annual_vision['tl_vision_id']

        if entity_type == 'tl_vision':
            tl_vision = self.get_tl_vision(entity_id)
            if tl_vision:
                breadcrumb.insert(0, {'type': 'tl_vision', 'data': tl_vision})
                segment = self.get_segment(tl_vision['segment_description_id'])
                if segment:
                    breadcrumb.insert(0, {'type': 'segment', 'data': segment})

        return breadcrumb

    # ========================================================================
    # DELETE METHODS (CASCADE WITH PREVIEW SUPPORT)
    # ========================================================================

    def _fetch_ids(self, table: str, where_col: str, where_vals: List[str]) -> List[str]:
        """Fetch IDs from table where where_col in where_vals."""
        if not where_vals:
            return []
        placeholders = ",".join(["?"] * len(where_vals))
        cursor = self.db.conn.execute(
            f"SELECT id FROM {table} WHERE {where_col} IN ({placeholders})",
            where_vals
        )
        return [row["id"] for row in cursor.fetchall()]

    def _collect_cascade_ids(self, entity_type: str, entity_id: str) -> Dict[str, List[str]]:
        """
        Collect all descendant IDs that will be deleted for a given VPS entity.
        """
        ids: Dict[str, List[str]] = {
            "tl_visions": [],
            "annual_visions": [],
            "annual_plans": [],
            "annual_initiatives": [],
            "quarter_initiatives": [],
            "month_tactics": [],
            "week_actions": [],
            "action_items": [],
        }

        if entity_type == "tl_vision":
            ids["tl_visions"] = [entity_id]
            ids["annual_visions"] = self._fetch_ids("annual_visions", "tl_vision_id", [entity_id])
        elif entity_type == "annual_vision":
            ids["annual_visions"] = [entity_id]
        elif entity_type == "annual_plan":
            ids["annual_plans"] = [entity_id]
        elif entity_type == "annual_initiative":
            ids["annual_initiatives"] = [entity_id]
        elif entity_type == "quarter_initiative":
            ids["quarter_initiatives"] = [entity_id]
        elif entity_type == "month_tactic":
            ids["month_tactics"] = [entity_id]
        elif entity_type == "week_action":
            ids["week_actions"] = [entity_id]
        else:
            return ids

        if ids["annual_visions"]:
            ids["annual_plans"] = self._fetch_ids("annual_plans", "annual_vision_id", ids["annual_visions"])

        if ids["annual_plans"]:
            ids["annual_initiatives"] = self._fetch_ids("annual_initiatives", "annual_plan_id", ids["annual_plans"])

            # Include legacy quarter initiatives still linked directly to annual plans
            legacy_qi = self._fetch_ids("quarter_initiatives", "annual_plan_id", ids["annual_plans"])
            qi_from_ai = self._fetch_ids("quarter_initiatives", "annual_initiative_id", ids["annual_initiatives"])
            ids["quarter_initiatives"] = sorted(set(legacy_qi + qi_from_ai))
        elif ids["annual_initiatives"]:
            qi_from_ai = self._fetch_ids("quarter_initiatives", "annual_initiative_id", ids["annual_initiatives"])
            ids["quarter_initiatives"] = sorted(set(qi_from_ai))

        if ids["quarter_initiatives"]:
            ids["month_tactics"] = self._fetch_ids("month_tactics", "quarter_initiative_id", ids["quarter_initiatives"])

        if ids["month_tactics"]:
            ids["week_actions"] = self._fetch_ids("week_actions", "month_tactic_id", ids["month_tactics"])

        if ids["week_actions"]:
            ids["action_items"] = self._fetch_ids("action_items", "week_action_id", ids["week_actions"])

        return ids

    def get_cascade_delete_preview(self, entity_type: str, entity_id: str) -> Dict[str, int]:
        """Return count preview of what will be deleted for the given entity."""
        ids = self._collect_cascade_ids(entity_type, entity_id)
        return {k: len(v) for k, v in ids.items() if len(v) > 0}

    def delete_entity_cascade(self, entity_type: str, entity_id: str) -> bool:
        """
        Delete an entity and all descendants.

        Note: action_items.week_action_id is ON DELETE SET NULL, so we explicitly
        delete action items linked to descendant week actions before parent deletion.
        """
        ids = self._collect_cascade_ids(entity_type, entity_id)
        conn = self.db.conn

        root_table_map = {
            "tl_vision": "tl_visions",
            "annual_vision": "annual_visions",
            "annual_plan": "annual_plans",
            "annual_initiative": "annual_initiatives",
            "quarter_initiative": "quarter_initiatives",
            "month_tactic": "month_tactics",
            "week_action": "week_actions",
        }
        root_table = root_table_map.get(entity_type)
        if not root_table:
            return False

        try:
            conn.execute("BEGIN")

            # Explicitly delete action items that would otherwise become orphaned.
            if ids["action_items"]:
                placeholders = ",".join(["?"] * len(ids["action_items"]))
                conn.execute(
                    f"DELETE FROM action_items WHERE id IN ({placeholders})",
                    ids["action_items"]
                )

            conn.execute(f"DELETE FROM {root_table} WHERE id = ?", (entity_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def delete_tl_vision(self, vision_id: str) -> bool:
        # Keep parent-protection behavior: do not delete if annual visions exist.
        child_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM annual_visions WHERE tl_vision_id = ?",
            (vision_id,)
        ).fetchone()[0]
        if child_count > 0:
            return False
        return self.delete_entity_cascade("tl_vision", vision_id)

    def delete_annual_vision(self, vision_id: str) -> bool:
        return self.delete_entity_cascade("annual_vision", vision_id)

    def delete_annual_plan(self, plan_id: str) -> bool:
        return self.delete_entity_cascade("annual_plan", plan_id)

    def delete_annual_initiative(self, initiative_id: str) -> bool:
        return self.delete_entity_cascade("annual_initiative", initiative_id)

    def delete_quarter_initiative(self, initiative_id: str) -> bool:
        return self.delete_entity_cascade("quarter_initiative", initiative_id)

    def delete_month_tactic(self, tactic_id: str) -> bool:
        return self.delete_entity_cascade("month_tactic", tactic_id)

    def delete_week_action(self, action_id: str) -> bool:
        return self.delete_entity_cascade("week_action", action_id)

    def delete_segment(self, segment_id: str) -> tuple[bool, dict]:
        """
        Delete a Segment if it has no child records.
        Returns (success: bool, counts: dict).
        - (True, {}) if deleted successfully
        - (False, {table: count, ...}) if deletion failed due to linked records

        Checks ALL VPS tables to prevent silent data loss via cascade deletion.
        """
        # Check ALL VPS tables for related records
        counts = {}

        tables = [
            ('tl_visions', 'TL Visions'),
            ('annual_visions', 'Annual Visions'),
            ('annual_plans', 'Annual Plans'),
            ('annual_initiatives', 'Annual Initiatives'),
            ('quarter_initiatives', 'Quarter Initiatives'),
            ('month_tactics', 'Month Tactics'),
            ('week_actions', 'Week Actions'),
        ]

        total = 0
        for table, label in tables:
            cursor = self.db.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE segment_description_id = ?",
                (segment_id,)
            )
            count = cursor.fetchone()[0]
            if count > 0:
                counts[label] = count
                total += count

        # Also check action_items
        cursor = self.db.conn.execute(
            "SELECT COUNT(*) FROM action_items WHERE segment_description_id = ?",
            (segment_id,)
        )
        action_count = cursor.fetchone()[0]
        if action_count > 0:
            counts['Action Items'] = action_count
            total += action_count

        if total > 0:
            return False, counts

        # Safe to delete - no child records found
        self.db.conn.execute(
            "DELETE FROM segment_descriptions WHERE id = ?",
            (segment_id,)
        )
        self.db.conn.commit()
        return True, {}
