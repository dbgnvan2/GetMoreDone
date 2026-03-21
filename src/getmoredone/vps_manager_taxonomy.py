"""Vision taxonomy and vision-element support for `VPSManager`."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class VPSTaxonomyMixin:
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
                f"Segment '{norm}' does not exist in Vision Elements. Create it in VSP Plan -> Vision Elements first."
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
                "Create it in VSP Plan -> Vision Elements first."
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
                "Create it in VSP Plan -> Vision Elements first."
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

