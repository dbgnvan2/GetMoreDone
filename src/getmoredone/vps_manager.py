"""
VSP (Vision Strategy Plan) Database Manager
Provides CRUD operations for all VSP entities.
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
from .link_integrity import (
    find_initiative_candidates_by_title,
    resolve_segment_id_exact,
)
from . import week_calendar
from .weekly_tactic_logging import get_weekly_tactic_logger
from . import weekly_tactic_titles
from .models import ActionItem
from .paths import app_data_dir_path
from .vps_manager_planning import VPSPlanningMixin
from .vps_manager_taxonomy import VPSTaxonomyMixin, VisionElementHasDependentsError


class ActionItemsAttachedError(Exception):
    """Raised when an Annual Plan Element still has Action Items on it.

    Purpose: an Annual Plan Element is deleted only when it has no child
             records. The delete used to null ``annual_plan_element_id`` on
             every item pointing at it, which for a Weekly Tactic produced a
             row ``update_action_item`` then refuses to save — a value no
             supported path can create, written by a supported path — and for
             an ordinary item silently detached it from the plan.
    Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1
    Tests:   tests/test_vps_hub_crud.py::test_delete_annual_records_is_refused_while_action_items_remain
    """

    def __init__(self, titles):
        self.titles = list(titles)
        shown = ", ".join(self.titles[:5])
        if len(self.titles) > 5:
            shown += f", and {len(self.titles) - 5} more"
        super().__init__(
            f"{len(self.titles)} action item(s) are still on this Annual Plan "
            f"Element: {shown}. Move or delete them first."
        )


class ProjectBoardsAttachedError(Exception):
    """Raised when an annual plan element cannot be deleted because user projects
    are still attached to it.

    Purpose: Prevent the APE-delete cascade from silently destroying multiple
             project boards now that several projects may share one APE.
    Spec:    docs/changes/2026-06-15-project-ape-linking.md
    Tests:   tests/test_vps_hub_crud.py::test_delete_annual_record_blocked_when_extra_projects_attached
    """

    def __init__(self, board_titles: List[str]):
        self.board_titles = board_titles
        joined = ", ".join(board_titles)
        super().__init__(
            f"Cannot delete: {len(board_titles)} project(s) attached ({joined})."
        )


def _get_weekly_debug_logger() -> logging.Logger:
    """The weekly-tactic logger.

    Implementation moved to weekly_tactic_logging so the migration — which runs
    before any VPSManager exists — writes to a logger that has a handler.
    """
    return get_weekly_tactic_logger()


class VPSManager(VPSPlanningMixin, VPSTaxonomyMixin):
    """Manages all VSP database operations."""

    def __init__(self, db_path: Optional[str] = None, db_manager: Optional[DatabaseManager] = None):
        """Initialize VSP manager with database connection.

        WT-M4.D — the VPS manager and its DatabaseManager share **one**
        connection. They used to open two against the same file, so a
        ``db_manager.transaction()`` could not cover a VPS write at all: the
        two would contend for the write lock and neither could roll the other
        back. Sharing is also what makes the scaffolding cascade see its own
        uncommitted rows while it builds them.
        """
        # Store db_manager for action item operations.
        # If not provided, create one using the same db_path.
        self.db_manager = db_manager if db_manager else DatabaseManager(db_path)
        self.db = self.db_manager.db
        self.db.connect()
        self.db.initialize_schema()
        self.logger = _get_weekly_debug_logger()

        # WT-M4 — hand this manager to the re-filing engine, so the engine does
        # not build a second VPSManager (which would re-run the taxonomy syncs
        # and leave two objects with different patched state under test).
        self.db_manager.attach_vps_manager(self)

        self.sync_vision_segments_with_settings()
        self.sync_vision_elements_with_taxonomy()

    def close(self):
        """Close the shared database connection."""
        self.db_manager.close()

    @staticmethod
    def shorten_pipe_prefix(text: str) -> str:
        """Shorten first two pipe-delimited segments to initials.

        Example: Purposeful Work|Living Systems|Blog -> PW|LS|Blog

        Implementation moved to weekly_tactic_titles so the re-filing engine can
        share it without importing VPSManager (WT-M7.A.2).
        """
        return weekly_tactic_titles.shorten_pipe_prefix(text)

    @staticmethod
    def normalize_week_token(text: str) -> str:
        """Convert 'Week N' to 'Wn' in titles."""
        return weekly_tactic_titles.normalize_week_token(text)

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

    def get_attached_project_boards_for_ape(self, ape_id: str) -> List[Dict[str, Any]]:
        """Return project boards linked to an APE, with their linked-item counts.

        Purpose: Surface which projects would be lost if the APE were deleted.
        Spec:    docs/changes/2026-06-15-project-ape-linking.md
        Tests:   tests/test_vps_hub_crud.py::test_delete_annual_record_blocked_when_extra_projects_attached
        """
        rows = self.db.conn.execute(
            """
            SELECT pb.id, pb.title,
                   COUNT(pbi.item_id) AS item_count
            FROM project_boards pb
            LEFT JOIN project_board_items pbi ON pbi.project_board_id = pb.id
            WHERE pb.annual_plan_element_id = ?
            GROUP BY pb.id, pb.title
            ORDER BY pb.title COLLATE NOCASE
            """,
            (ape_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_annual_records_for_vision_element(self, year: int, vision_element_id: str) -> bool:
        """Delete annual rows for one Vision Element in a specific year.

        Refuses to delete (raising ProjectBoardsAttachedError) when the user has
        parked real projects on the APE — more than the lone empty auto-created
        default board, or any board with linked action items — so the cascade can
        no longer silently destroy multiple shared-APE projects.
        """
        ape = self.db.conn.execute(
            "SELECT id FROM annual_plan_elements WHERE year = ? AND vision_element_id = ?",
            (year, vision_element_id),
        ).fetchone()
        ape_id = ape["id"] if ape else None

        if ape_id:
            attached = self.get_attached_project_boards_for_ape(ape_id)
            has_real_projects = len(attached) > 1 or any(b["item_count"] > 0 for b in attached)
            if has_real_projects:
                raise ProjectBoardsAttachedError([b["title"] for b in attached])

            # An Annual Plan Element is deleted only when it has no child
            # records. This used to null the APE on every item pointing at it,
            # which silently detached ordinary items from the plan and left
            # Weekly Tactics in a state the application's own writer rejects
            # ("A Weekly Tactic must belong to an Annual Plan Element").
            # Tests: tests/test_vps_hub_crud.py::test_delete_annual_records_is_refused_while_action_items_remain
            items = self.db.conn.execute(
                "SELECT title FROM action_items WHERE annual_plan_element_id = ? "
                "ORDER BY title COLLATE NOCASE",
                (ape_id,),
            ).fetchall()
            if items:
                raise ActionItemsAttachedError([row["title"] for row in items])

            # Only a single empty auto-created default board remains: safe to remove.
            self.db.conn.execute(
                "DELETE FROM project_boards WHERE annual_plan_element_id = ?",
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

    def create_annual_records_from_vision_element(
        self,
        year: int,
        vision_element_id: str,
        commit: bool = True,
        ensure_project_board: bool = True,
    ) -> Dict[str, str]:
        """Create Annual Vision Element + Annual Plan Element from a vision element.

        Args:
            commit: WT-M4.D — False lets the year-rollover cascade own the
                transaction, so a failure at row 6 of 8 leaves nothing behind.
            ensure_project_board: WT-M4.C / Q2 — False on the rollover path. A
                project spans any timeframe, so a new year needs no new board.
        """
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
                (id, year, vision_element_id, segment_name, subsegment_name, category_name, key_field, segment_description_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ave_id, year, vision_element_id, data["segment_name"],
                data["subsegment_name"], data["category_name"], data["key_field"],
                # RN-M2.B: stamp the id at create time. Backfilling covers rows
                # written before this change; without this, every NEW row would
                # need the migration to catch up with it on the next launch.
                resolve_segment_id_exact(self.db.conn, data["segment_name"]),
                now, now
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
                (id, year, vision_element_id, annual_vision_element_id, segment_name, subsegment_name, category_name, key_field, segment_description_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ape_id, year, vision_element_id, ave_id, data["segment_name"],
                data["subsegment_name"], data["category_name"], data["key_field"],
                # RN-M2.B — see the AVE insert above.
                resolve_segment_id_exact(self.db.conn, data["segment_name"]),
                now, now
            ))

        if commit:
            self.db.conn.commit()
        if ensure_project_board:
            try:
                self.db_manager.ensure_project_board_for_ape(ape_id)
            except Exception as exc:
                # Not fatal — the lineage is what matters — but no longer silent.
                _get_weekly_debug_logger().warning(
                    "[create_annual_records] could not ensure a project board for "
                    "APE %s: %s", ape_id, exc,
                )
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

    def get_annual_plan_elements_for_quarter(self, year: int, quarter: int) -> List[Dict[str, Any]]:
        if quarter not in (1, 2, 3, 4):
            return []
        q_col = f"q{quarter}"
        cursor = self.db.conn.execute(f"""
            SELECT * FROM annual_plan_elements
            WHERE year = ?
              AND {q_col} = 1
            ORDER BY segment_name COLLATE NOCASE ASC, subsegment_name COLLATE NOCASE ASC, category_name COLLATE NOCASE ASC
        """, (year,))
        return [dict(row) for row in cursor.fetchall()]

    def set_annual_plan_element_quarter(self, ape_id: str, quarter: int, enabled: bool,
                                        commit: bool = True) -> bool:
        if quarter not in (1, 2, 3, 4):
            return False
        col = f"q{quarter}"
        self.db.conn.execute(
            f"UPDATE annual_plan_elements SET {col} = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, datetime.now().isoformat(), ape_id)
        )
        if commit:
            self.db.conn.commit()
        return True

    def set_annual_plan_element_month(self, ape_id: str, month: int, enabled: bool,
                                      commit: bool = True) -> bool:
        if month < 1 or month > 12:
            return False
        col = f"m{month}"
        self.db.conn.execute(
            f"UPDATE annual_plan_elements SET {col} = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, datetime.now().isoformat(), ape_id)
        )
        if commit:
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

    def assign_ape_to_quarter(self, ape_id: str, quarter: int) -> bool:
        if quarter not in (1, 2, 3, 4):
            return False
        ape = self._get_annual_plan_element_row(ape_id)
        if not ape:
            return False

        self.set_annual_plan_element_quarter(ape_id, quarter, True)
        annual_initiative_id = self._get_or_create_annual_initiative_for_ape(ape)
        existing = self.get_quarter_initiatives(
            annual_initiative_id=annual_initiative_id,
            quarter=quarter,
            year=int(ape["year"]),
            active_only=False,
        )
        if not existing:
            segment_id = self._segment_id_for_ape(ape)
            if not segment_id:
                raise ValueError(f"Segment '{ape['segment_name']}' not found.")
            self.create_quarter_initiative(
                annual_initiative_id=annual_initiative_id,
                segment_description_id=segment_id,
                quarter=quarter,
                year=int(ape["year"]),
                title=f"{ape['key_field']} Q{quarter}",
                auto_create_chain=False,
            )
        return True

    def unassign_ape_from_quarter(self, ape_id: str, quarter: int) -> bool:
        if quarter not in (1, 2, 3, 4):
            return False
        ape = self._get_annual_plan_element_row(ape_id)
        if not ape:
            return False

        self.set_annual_plan_element_quarter(ape_id, quarter, False)
        self._clear_quarter_month_flags(ape_id, quarter)
        annual_initiative = self._find_annual_initiative_for_ape(ape)
        if annual_initiative:
            matches = self.get_quarter_initiatives(
                annual_initiative_id=annual_initiative["id"],
                quarter=quarter,
                year=int(ape["year"]),
                active_only=False,
            )
            for row in matches:
                self.delete_quarter_initiative(row["id"])
        return True

    def assign_ape_to_month(self, ape_id: str, quarter: int, month: int) -> bool:
        if quarter not in (1, 2, 3, 4) or month < 1 or month > 12:
            return False
        ape = self._get_annual_plan_element_row(ape_id)
        if not ape:
            return False

        self.assign_ape_to_quarter(ape_id, quarter)
        self.set_annual_plan_element_month(ape_id, month, True)

        annual_initiative = self._find_annual_initiative_for_ape(ape)
        if not annual_initiative:
            return False
        quarter_rows = self.get_quarter_initiatives(
            annual_initiative_id=annual_initiative["id"],
            quarter=quarter,
            year=int(ape["year"]),
            active_only=False,
        )
        if not quarter_rows:
            return False
        quarter_id = quarter_rows[0]["id"]
        month_rows = self.get_month_tactics(
            quarter_initiative_id=quarter_id,
            month=month,
            year=int(ape["year"]),
            active_only=False,
        )
        if not month_rows:
            segment_id = self._segment_id_for_ape(ape)
            if not segment_id:
                raise ValueError(f"Segment '{ape['segment_name']}' not found.")
            self.create_month_tactic(
                quarter_initiative_id=quarter_id,
                segment_description_id=segment_id,
                month=month,
                year=int(ape["year"]),
                priority_focus=ape["key_field"],
                description="",
                auto_create_weeks=False,
            )
        return True

    def unassign_ape_from_month(self, ape_id: str, quarter: int, month: int) -> bool:
        if quarter not in (1, 2, 3, 4) or month < 1 or month > 12:
            return False
        ape = self._get_annual_plan_element_row(ape_id)
        if not ape:
            return False

        self.set_annual_plan_element_month(ape_id, month, False)
        annual_initiative = self._find_annual_initiative_for_ape(ape)
        if annual_initiative:
            quarter_rows = self.get_quarter_initiatives(
                annual_initiative_id=annual_initiative["id"],
                quarter=quarter,
                year=int(ape["year"]),
                active_only=False,
            )
            if quarter_rows:
                month_rows = self.get_month_tactics(
                    quarter_initiative_id=quarter_rows[0]["id"],
                    month=month,
                    year=int(ape["year"]),
                    active_only=False,
                )
                for row in month_rows:
                    self.delete_month_tactic(row["id"])
        return True

    def _get_annual_plan_element_row(self, ape_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()
        return dict(row) if row else None

    def _segment_id_for_ape(self, ape: Dict[str, Any]) -> Optional[str]:
        """The APE's segment, by id (RN-M2.B).

        Purpose: renaming a segment must not break the re-filing cascade.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m2b
        Tests:   tests/test_rename_safe_links.py::test_rn_m2b_cascade_survives_a_segment_rename

        Every link caller went through ``resolve_segment_id_by_name`` and raised
        ``ValueError("Segment '<new name>' not found.")`` once the name moved —
        so an ordinary date change on a filed Action Item raised, and the item
        silently did not move (spec §2).

        The name lookup remains as a one-time heal for a row the migration
        could not resolve, and writes the id when it succeeds so it never fires
        again. ``resolve_segment_id_by_name`` itself stays for genuine NAME
        lookups — user input and import — and is no longer a link path.
        """
        # `ape` arrives as a dict on some paths and a sqlite3.Row on others,
        # and a Row has no .get(). Reading by key with a membership test works
        # for both; .get() raised AttributeError in create_week_action_items.
        def _field(name):
            try:
                return ape[name]
            except (KeyError, IndexError):
                return None

        was_open = bool(getattr(self.db.conn, "in_transaction", False))
        existing = _field("segment_description_id")
        if existing:
            return existing

        # Exact, not first-match: WRITING an id for a name that matches two
        # segments is the guess the migration deliberately refused.
        healed = resolve_segment_id_exact(self.db.conn, _field("segment_name"))
        if healed is None:
            # But refusing to write is not a reason to break the cascade.
            #
            # Returning None here made assign_ape_to_month raise
            # `ValueError: Segment '<name>' not found.` — verbatim the spec §2
            # failure this change exists to remove — for every plan element
            # created while two segment descriptions differ only by case
            # (segment_descriptions.name is UNIQUE but CASE-SENSITIVE, and
            # create_segment does not guard against it).
            #
            # So fall back to the by-name answer for the CALLER, and do not
            # persist it. The column stays NULL, RN-M5 names the row, and the
            # cascade keeps working — which is exactly how it behaved before
            # this change, rather than worse.
            return self.resolve_segment_id_by_name(_field("segment_name"))

        if healed and _field("id"):
            self.db.conn.execute(
                "UPDATE annual_plan_elements SET segment_description_id = ? "
                "WHERE id = ? AND segment_description_id IS NULL",
                (healed, ape["id"]),
            )
            self._commit_heal(was_open)
        return healed

    def _commit_heal(self, was_already_in_a_transaction: bool) -> None:
        """Persist a heal written during what callers treat as a read.

        Purpose: a lookup must not leave an open write transaction behind.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m2a
        Tests:   tests/test_rename_safe_links.py::test_rn_a_lookup_leaves_no_open_transaction

        Both heals write an id inside a getter. Without this the write is
        silently discarded when the connection closes, and in the meantime the
        connection holds a RESERVED lock — `_find_annual_initiative_for_ape` is
        used as a pure read from weekly_tactic's before-snapshot and from
        unassign_ape_from_month, either of which can return without committing.

        Inside ``DatabaseManager.transaction()`` the shared connection defers
        the commit (see _DeferredCommitConnection), so a cascade rollback still
        takes the heal with it — the behaviour RN-M2.A's risk table wanted.

        That deferral does NOT cover a raw ``conn.execute("BEGIN")``, of which
        there are four: rename_vision_segment / _subsegment / _category and
        delete_entity_cascade. A heal reached from inside one of those would
        commit the caller's work mid-transaction and make its rollback a no-op.
        No healer is reachable from them today — verified — so this is a trap
        rather than a defect, and it is one added call from becoming live.
        Recorded in BACKLOG.md.
        """
        if was_already_in_a_transaction:
            # Someone else's transaction was open before the heal wrote, so the
            # write belongs to them: committing here would publish their work
            # and make their rollback a no-op. Their commit or rollback takes
            # the heal with it, which is correct either way.
            #
            # The flag is captured BEFORE the heal's own UPDATE, because that
            # UPDATE opens a transaction itself — checking in_transaction here
            # would always be True and nothing would ever commit.
            return
        try:
            self.db.conn.commit()
        except Exception:
            # A commit that cannot happen here is the caller's transaction to
            # resolve. Never raise out of a lookup.
            pass

    def _find_annual_initiative_for_ape(self, ape: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The APE's Annual Initiative, resolved by id (RN-M2.A).

        Purpose: renaming anything must not change which initiative an APE has.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-m2a
        Tests:   tests/test_rename_safe_links.py::test_rn_m2a_initiative_found_by_id_after_rename
                 tests/test_rename_safe_links.py::test_rn_m2a1_legacy_row_heals_on_first_lookup
                 tests/test_rename_safe_links.py::test_rn_m2a2_initiative_survives_an_annual_plan_year_drift
                 tests/test_rename_safe_links.py::test_rn_m2a2_year_drift_does_not_duplicate_the_initiative

        This used to match ``LOWER(ai.title) = LOWER(ape.key_field)`` and
        resolve the segment by name. Renaming either made the lookup return
        None, so the next assignment built a SECOND Annual Initiative and a
        second Quarter Initiative for the same APE and quarter (RN-F4).

        The title match survives only as a one-time heal for a row whose id is
        still NULL — a database migrated while two initiatives matched, or a
        row written by an older build. When it fires it WRITES the id, so it
        never fires again for that row. It runs inside the caller's
        transaction, so a cascade rollback takes it with it.

        **The id is the whole predicate.** This lookup also filtered
        ``AND ap.year = ape.year`` through a join on annual_plans. An APE id
        identifies one APE and an APE carries one year, so that clause could
        never select a *different* initiative — it could only hide the right
        one. The year is stored independently on annual_plans,
        annual_plan_elements and annual_initiatives, so any path that writes
        one without the others drifts them; when it drifted, this returned
        None, ``_get_or_create_annual_initiative_for_ape`` built a second
        initiative, and RN-F4's duplicate reappeared through the function
        written to close it. Resolving by id means resolving by id alone.
        """
        row = self.db.conn.execute(
            """
            SELECT ai.*
            FROM annual_initiatives ai
            WHERE ai.annual_plan_element_id = ?
            ORDER BY ai.created_at ASC
            LIMIT 1
            """,
            (ape["id"],),
        ).fetchone()
        if row:
            return dict(row)

        healed = self._heal_annual_initiative_link(ape)
        return healed

    def _heal_annual_initiative_link(
        self, ape: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """RN-M2.A.1 — link a legacy NULL row once, by the old title match.

        Spec:  docs/spec_2026-08-19_rename_safe_links.md#rn-m2a
        Tests: tests/test_rename_safe_links.py::test_rn_m2a1_legacy_row_heals_on_first_lookup
               tests/test_rename_safe_links.py::test_rn_m2a1_heal_survives_an_annual_plan_year_drift
               tests/test_rename_safe_links.py::test_rn_m2a1_heal_prefers_the_candidate_whose_plan_year_agrees

        Deliberately narrow. It fires only when the id is NULL and exactly one
        candidate survives the preferred tier: two is the RN-F4 duplicate, and
        choosing between them here would silently pick one of a user's two
        plans (RN-INV5). Those are left for the report.

        "Exactly one **candidate**", not "exactly one initiative that matches"
        — the tier itself is a choice, and this path cannot report making it.
        Where two initiatives match and the plan year separates them, this
        heals to the preferred one silently. The migration's backfill sees the
        same pair and names both, which is where a human finds out.

        ``ai.year`` is the identifying comparison — the initiative's own year
        against the APE's. The annual plan's year is a **tie-break**, applied
        by ``find_initiative_candidates_by_title`` and shared with the
        migration's backfill so the two cannot drift.

        Requiring it outright hid an initiative whose plan year had drifted,
        and this heal finding nothing does not fail safe — the caller then
        creates the duplicate. Dropping it outright was worse: a twin on a
        drifted plan joined the candidate set, the count went from one to two,
        and the refusal above produced a **third** initiative for one plan
        element. Preferring the agreeing candidates and widening only when
        there are none does neither.
        """
        was_open = bool(getattr(self.db.conn, "in_transaction", False))
        segment_id = self._segment_id_for_ape(ape)
        if not segment_id:
            return None
        # Only the preferred tier decides. The full list is for callers with a
        # report channel; this one has none, and refusing here is not safe —
        # _get_or_create_annual_initiative_for_ape then builds another.
        matches, _all_candidates = find_initiative_candidates_by_title(
            self.db.conn, ape["year"], segment_id, ape["key_field"]
        )
        if len(matches) != 1:
            return None

        row = dict(matches[0])
        self.db.conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = ? WHERE id = ?",
            (ape["id"], row["id"]),
        )
        row["annual_plan_element_id"] = ape["id"]
        self._commit_heal(was_open)
        return row

    def _get_or_create_annual_initiative_for_ape(
        self, ape: Dict[str, Any], created_by_rollover: bool = False
    ) -> str:
        existing = self._find_annual_initiative_for_ape(ape)
        if existing:
            return existing["id"]

        annual_plan_id, segment_id = self._get_or_create_annual_plan_for_ape(
            ape, created_by_rollover=created_by_rollover
        )
        initiative_id = self.create_annual_initiative(
            annual_plan_id=annual_plan_id,
            segment_description_id=segment_id,
            year=int(ape["year"]),
            title=ape["key_field"],
            description="",
            outcome_statement="",
            auto_create_chain=False,
        )
        # RN-M2.A — stamp the link at create time. Without this the id is
        # written only lazily, by the heal in _find_annual_initiative_for_ape,
        # so a rename between creation and first lookup would find nothing to
        # heal and RN-M3.A's title refresh would skip the row.
        self.db.conn.execute(
            "UPDATE annual_initiatives SET annual_plan_element_id = ? WHERE id = ?",
            (ape["id"], initiative_id),
        )
        return initiative_id

    def _get_or_create_annual_plan_for_ape(
        self, ape: Dict[str, Any], created_by_rollover: bool = False
    ) -> tuple[str, str]:
        """Get or create the annual vision + plan behind an Annual Plan Element.

        Args:
            created_by_rollover: WT-D7a / WT-M4.C.3 — when True the editorial
                fields (``annual_visions.title`` / ``vision_statement`` /
                ``key_priorities``, ``annual_plans.theme`` / ``objective`` /
                ``description``) are left blank and the rows are flagged
                ``created_by_rollover = 1``. Editorial text is never copied
                forward and never invented.

                Default False keeps the shipped wording exactly as it was, so
                the four existing callers (``ape_assignment.py:233,387``;
                ``ape_period_view.py:242,396``) are unaffected — WT-M4.C.3c.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m4c3
        Tests: tests/test_weekly_tactic_cascade.py::test_wt_m4c3_editorial_fields_blank_and_flagged
               tests/test_weekly_tactic_cascade.py::test_wt_m4c3c_existing_ape_assignment_callers_unaffected
        """
        year = int(ape["year"])
        segment_name = ape["segment_name"]
        segment_id = self._segment_id_for_ape(ape)
        if not segment_id:
            raise ValueError(f"Segment '{segment_name}' not found.")

        existing_plan = self.db.conn.execute(
            """
            SELECT * FROM annual_plans
            WHERE year = ?
              AND segment_description_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (year, segment_id),
        ).fetchone()
        if existing_plan:
            return existing_plan["id"], segment_id

        tl_visions = self.get_tl_visions(segment_id=segment_id, active_only=False)
        tl_vision = next(
            (row for row in tl_visions if int(row.get("start_year") or year) <= year <= int(row.get("end_year") or year)),
            tl_visions[0] if tl_visions else None,
        )
        if not tl_vision:
            tl_vision_id = self.create_tl_vision(
                segment_description_id=segment_id,
                start_year=year,
                end_year=year + 5,
                title=f"{segment_name} Vision",
                vision_statement="",
                success_metrics="[]",
            )
            tl_vision = self.get_tl_vision(tl_vision_id)

        annual_visions = self.get_annual_visions(
            tl_vision_id=tl_vision["id"],
            year=year,
            active_only=False,
        )
        annual_vision = annual_visions[0] if annual_visions else None
        if not annual_vision:
            annual_vision_id = self.create_annual_vision(
                tl_vision_id=tl_vision["id"],
                segment_description_id=segment_id,
                year=year,
                title="" if created_by_rollover else f"{segment_name} {year}",
                vision_statement="",
                key_priorities="[]" if not created_by_rollover else "",
            )
            annual_vision = self.get_annual_vision(annual_vision_id)
            if created_by_rollover:
                self._mark_created_by_rollover("annual_visions", annual_vision_id)

        plan_id = self.create_annual_plan(
            annual_vision_id=annual_vision["id"],
            segment_description_id=segment_id,
            year=year,
            theme="" if created_by_rollover else f"{segment_name} {year} Plan",
            objective="",
            description="",
        )
        if created_by_rollover:
            self._mark_created_by_rollover("annual_plans", plan_id)
        return plan_id, segment_id

    def _mark_created_by_rollover(self, table: str, row_id: str) -> None:
        """WT-D13 — flag a row the year rollover created.

        An explicit flag, not an inference from empty fields: a hand-authored
        vision with a blank statement must not be reported as a stub
        (WT-M4.C.3b).
        """
        self.db.conn.execute(
            f"UPDATE {table} SET created_by_rollover = 1 WHERE id = ?", (row_id,)
        )

    def _clear_quarter_month_flags(self, ape_id: str, quarter: int,
                                   commit: bool = True) -> None:
        quarter_months = {
            1: (1, 2, 3),
            2: (4, 5, 6),
            3: (7, 8, 9),
            4: (10, 11, 12),
        }[quarter]
        now = datetime.now().isoformat()
        assignments = ", ".join(f"m{month} = 0" for month in quarter_months)
        self.db.conn.execute(
            f"UPDATE annual_plan_elements SET {assignments}, updated_at = ? WHERE id = ?",
            (now, ape_id),
        )
        if commit:
            self.db.conn.commit()

    def get_month_week_starts(self, year: int, month: int, first_day_of_week: int = 0) -> List[Dict[str, Any]]:
        """
        Return week start options for a month based on configured first weekday.

        first_day_of_week: 0=Monday .. 6=Sunday
        """
        calendar_ = week_calendar.WeekCalendar(
            first_day=first_day_of_week,
            rule=week_calendar.WeekCalendar.from_settings().rule,
        )
        options: List[Dict[str, Any]] = []
        for week_of_month, cursor in enumerate(
            week_calendar.month_week_starts(year, month, calendar_.first_day), start=1
        ):
            week_of_year = calendar_.number(cursor)
            options.append(
                {
                    "week_of_month": week_of_month,
                    "week_of_year": week_of_year,
                    "week_start_date": cursor.isoformat(),
                    "week_end_date": calendar_.end(cursor).isoformat(),
                    "day_of_month": cursor.day,
                    "label": f"Wk{week_of_month} {cursor.day} (WOY {week_of_year})",
                }
            )
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
        """Create weekly Action Items linked to an Annual Plan Element.

        Purpose: build the week rows for one APE and month.
        Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c3
        Tests:   tests/test_weekly_tactic_schema.py::test_wt_m1c3_ape_weekly_screen_reports_duplicate_instead_of_crashing

        WT-M1.C.3 — the pre-existing duplicate guard is a month-prefixed LIKE
        (``get_existing_week_item_starts_for_ape``), so it cannot see a tactic
        whose week start falls in the adjacent month. With the WT-INV5 unique
        index live that near-miss becomes an IntegrityError in a screen with no
        handler. It is caught here and reported as ``collided_count`` /
        ``collisions`` rather than crashing the screen — and never swallowed
        silently (P2).

        Returns created_count, skipped_count, collided_count, created_ids and
        collisions. The first three keys predate this change and are unmoved.
        """
        if month < 1 or month > 12:
            raise ValueError("Month must be 1-12")
        if not week_start_dates:
            return {
                "created_count": 0,
                "skipped_count": 0,
                "collided_count": 0,
                "created_ids": [],
                "collisions": [],
            }

        ape = self.db.conn.execute(
            "SELECT * FROM annual_plan_elements WHERE id = ?",
            (ape_id,),
        ).fetchone()
        if not ape:
            raise ValueError("Annual Plan Element not found")

        existing = set(self.get_existing_week_item_starts_for_ape(ape_id, year, month))
        system_defaults = self.db_manager.get_defaults("system")
        calendar_ = week_calendar.WeekCalendar.from_settings()

        created_ids: List[str] = []
        collisions: List[Dict[str, Any]] = []
        skipped_count = 0
        key_field = ape["key_field"]
        who_value = ape["segment_name"] or "VSP"
        segment_id = self._segment_id_for_ape(ape)

        for week_start in week_start_dates:
            if week_start in existing:
                skipped_count += 1
                continue

            ws = date.fromisoformat(week_start)
            week_of_year = calendar_.number(ws)
            we = calendar_.end(ws)

            item = ActionItem(
                who=who_value,
                title=weekly_tactic_titles.canonical_weekly_tactic_title(
                    key_field, ws, calendar_
                ) or f"{weekly_tactic_titles.title_prefix(key_field)} - W{week_of_year}",
                description=f"Weekly action item for {key_field} (W{week_of_year}, starts {ws.isoformat()})",
                start_date=ws.isoformat(),
                due_date=we.isoformat(),
                importance=system_defaults.importance if system_defaults else None,
                urgency=system_defaults.urgency if system_defaults else None,
                size=system_defaults.size if system_defaults else None,
                value=system_defaults.value if system_defaults else None,
                category="VSP",
                status="open",
                annual_plan_element_id=ape_id,
                item_type="week",
                segment_description_id=segment_id,
            )
            try:
                created_ids.append(
                    self.db_manager.create_action_item(item, apply_defaults=False)
                )
            except sqlite3.IntegrityError as exc:
                # A Weekly Tactic already exists for this APE and week — the
                # LIKE guard above could not see it because its start date sits
                # in the adjacent month.
                collisions.append({"week_start": week_start, "error": str(exc)})
                _get_weekly_debug_logger().warning(
                    "[create_week_action_items_for_ape] duplicate tactic for "
                    "ape=%s week_start=%s: %s",
                    ape_id, week_start, exc,
                )

        return {
            "created_count": len(created_ids),
            "skipped_count": skipped_count,
            "collided_count": len(collisions),
            "created_ids": created_ids,
            "collisions": collisions,
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
        """Create a new life segment.

        Purpose: two segments whose names differ only by case are the root of
                 every ambiguity the rename-safe-links work had to handle.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv5
        Tests:   tests/test_rename_safe_links.py::test_rn_create_segment_refuses_a_case_only_duplicate

        ``segment_descriptions.name`` is UNIQUE, but SQLite's UNIQUE is
        case-SENSITIVE — so "Health" and "health" were both legal, and every
        link resolver then had to decide which one a name meant. The migration
        reports such a row and refuses to link it; the resolvers refuse to
        write; and the cascade falls back to a by-name answer. All of that
        machinery exists to survive a state the app should not create.

        Refusing here removes the class rather than coping with it. Existing
        collisions are untouched — they are reported by the migration, and
        resolving one is a decision for the person whose data it is.
        """
        clean = (name or "").strip()
        if not clean:
            raise ValueError("A life segment needs a name.")
        self._refuse_case_collision(clean)

        name = clean
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

    def _find_case_collisions(self, name: str, exclude_id: Optional[str] = None):
        """Every other life segment whose name differs from this one only by case.

        Purpose: one definition of "these two names collide", used to refuse a
                 rename and to compare which segments a name collides with
                 before and after it.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv5
        Tests:   tests/test_rename_safe_links.py::test_rn_a_recase_that_creates_a_collision_is_still_refused
                 tests/test_rename_safe_links.py::test_rn_a_strip_that_creates_a_collision_is_still_refused

        **SQLite's ``LOWER()``, deliberately.** It folds ASCII only, so
        ``LOWER('CAFÉ')`` is ``'cafÉ'`` while Python's ``'CAFÉ'.lower()`` is
        ``'café'``. ``resolve_segment_id_exact`` — the thing that actually
        breaks when two names collide — uses SQLite's, so this must too.
        Asking the question in Python instead opened a hole in exactly the
        cases the two disagree about: a non-ASCII re-case, or a stored name
        with whitespace on it.

        **Does not strip.** Callers hand it the value they mean: an already
        cleaned candidate name, or a stored name verbatim. Stripping here
        would answer "does the stored name collide?" about a name that is not
        the one stored — ``'Kappa '`` does not collide with ``'kappa'``, and
        trimming it in Python to claim it does re-creates the very mismatch
        this method exists to remove.
        """
        # ONE string literal, deliberately. Python concatenates adjacent
        # literals at compile time, so splitting this across two lines makes it
        # invisible to RN-M4's scan — which regexes the SOURCE, where the two
        # halves are still two strings. Written that way, this query hid from
        # the guard whose whole job is to see it.
        return self.db.conn.execute(
            "SELECT id, name FROM segment_descriptions WHERE LOWER(name) = LOWER(?) AND id IS NOT ?",
            (name or "", exclude_id),
        ).fetchall()

    def _refuse_newly_collided_segments(
        self, segment_id: str, old_name: str, new_name: str
    ) -> None:
        """Refuse a rename that drags a segment into a collision it was not in.

        Purpose: let a row that already collides be edited, while never letting
                 any save break a segment that was fine before it.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv5
        Tests:   tests/test_rename_safe_links.py::test_rn_rename_verdicts_are_exhaustive

        **A comparison of two sets, not a boolean.** Which segments did the OLD
        name collide with, and which does the NEW one? An id in the second set
        and not the first is a segment being newly broken, and that is the only
        thing worth refusing.

        Every cheaper formulation failed, each in a way the previous one's test
        could not see:

        * "is there a collision" froze every row of a pre-existing pair —
          colour, description, order and the active flag all raised, because
          both editors send the unchanged name along with the real edit;
        * "did the name change", asked in Python, let a non-ASCII re-case
          create one, since ``str.lower()`` folds where SQLite's ``LOWER()``
          does not;
        * "did the OLD name collide" disabled the guard for the whole save, so
          a collided row could be renamed onto a clean third segment's name and
          break a row nobody had touched.

        A row that already collides keeps every edit, including renaming itself
        free of the collision — which is the only route out of the state.
        """
        already = {row["id"] for row in self._find_case_collisions(old_name, segment_id)}
        newly = [
            row for row in self._find_case_collisions(new_name, segment_id)
            if row["id"] not in already
        ]
        if newly:
            raise ValueError(
                f"A life segment called '{newly[0]['name']}' already exists. "
                "Two segments whose names differ only by case cannot be told "
                "apart when resolving links, so pick a different name."
            )

    def _refuse_case_collision(self, name: str, exclude_id: str = None) -> None:
        """Refuse a life-segment name that differs from another only by case.

        Purpose: keep the ambiguity out of the table rather than coping with it
                 in every resolver downstream.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv5
        Tests:   tests/test_rename_safe_links.py::test_rn_create_segment_refuses_a_case_only_duplicate
                 tests/test_rename_safe_links.py::test_rn_update_segment_refuses_a_case_only_duplicate

        ``segment_descriptions.name`` is UNIQUE, but SQLite's UNIQUE is
        case-SENSITIVE, so 'Health' and 'health' are both legal. Once both
        exist, ``resolve_segment_id_exact`` returns None for BOTH spellings —
        every link resolution refuses forever and the migration reports the
        rows as needing a human at every launch.

        This lived inside ``create_segment`` and nowhere else, so RENAMING a
        segment created the state creating one could not (P5 — a guard applied
        to one door into a class). ``exclude_id`` is what makes it usable on
        the update path: a row is never a collision with itself, so a segment
        can keep, re-case, or change its own name.
        """
        collisions = self._find_case_collisions(name, exclude_id=exclude_id)
        if collisions:
            collision = collisions[0]
            raise ValueError(
                f"A life segment called '{collision['name']}' already exists. "
                "Two segments whose names differ only by case cannot be told "
                "apart when resolving links, so pick a different name."
            )

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

        if "name" in updates:
            clean = (updates["name"] or "").strip()
            if not clean:
                raise ValueError("A life segment needs a name.")
            self._refuse_newly_collided_segments(segment_id, old_name, clean)
            # Stripped before the check AND before the write. The two used to
            # diverge: vision_segments got the stripped spelling and
            # segment_descriptions the raw one, so one segment could be held
            # in two tables under two different names.
            updates["name"] = clean

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [segment_id]

        # Both writes or neither. segment_descriptions was updated first and
        # the mirrored vision_segments row second, with the commit at the end
        # and nothing in between: when the mirror hit its own UNIQUE
        # constraint the exception escaped with the first write applied and
        # the transaction still open, and the NEXT unrelated save on this
        # connection committed the half-finished rename. Measured — the
        # segment kept the new name on disk with no vision row at all.
        try:
            self._write_segment_update(
                segment_id, set_clause, values, updates, old_name
            )
        except sqlite3.IntegrityError as exc:
            self.db.conn.rollback()
            # A duplicate reaching SQLite is one the collision guard could not
            # see — an EXACT duplicate rather than a case variant, or a clash
            # on vision_segments.name. The user gets the same sentence either
            # way rather than raw constraint text.
            raise ValueError(
                "That name is already taken by another life segment, so the "
                "rename was not applied. Pick a different name."
            ) from exc
        return True

    def _write_segment_update(
        self, segment_id, set_clause, values, updates, old_name
    ) -> None:
        """The two writes a segment update makes, inside one transaction.

        Purpose: keep the mirrored vision_segments rename in the same
                 transaction as the segment_descriptions write.
        Spec:    docs/spec_2026-08-19_rename_safe_links.md#rn-inv2
        Tests:   tests/test_rename_safe_links.py::test_rn_a_refused_rename_leaves_no_half_written_row
        """
        self.db.conn.execute(
            f"UPDATE segment_descriptions SET {set_clause} WHERE id = ?",
            values
        )

        # If the segment display name changed in Settings, rename linked vision segment.
        if "name" in updates and updates["name"] and updates["name"] != old_name:
            new_name = updates["name"].strip()
            # By id, falling back to the old name only for a row the migration
            # could not link. Looking up by the OLD name was invisible to the
            # RN-M4 scan, and when it missed, the else-branch below created a
            # SECOND vision_segments row — RN-INV2, "renaming never causes a
            # duplicate", broken by the rename path itself.
            vision_seg = self.db.conn.execute(
                "SELECT id FROM vision_segments WHERE segment_description_id = ?",
                (segment_id,),
            ).fetchone()
            if not vision_seg:
                # "a row the migration could not link" means one whose id is
                # NULL. Without that condition the fallback adopted a row that
                # belongs to a DIFFERENT segment description: on a collided
                # pair, renaming A matched B's vision row by the shared name
                # and relabelled it, so B was spelled one way in
                # segment_descriptions and another in vision_segments, and the
                # derived-field sync then pushed B's wrong name onto B's
                # vision elements. Nobody renamed B.
                vision_seg = self.db.conn.execute(
                    "SELECT id FROM vision_segments "
                    "WHERE LOWER(name) = LOWER(?) AND segment_description_id IS NULL",
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
                # Stamp the id. Two of the four INSERT INTO vision_segments
                # sites were hardened by RN-M1.C and this one was not, so a row
                # created here was unlinked until the next launch's backfill —
                # and get_vision_segments_admin's id-join returned it with no
                # colour and no order in the meantime.
                self.db.conn.execute(
                    "INSERT INTO vision_segments "
                    "(id, name, vision_text, segment_description_id, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (seg_id, new_name, "", segment_id, now, now),
                )
        self.db.conn.commit()

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
        Collect all descendant IDs that will be deleted for a given VSP entity.
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

        Checks ALL VSP tables to prevent silent data loss via cascade deletion.
        """
        # Check ALL VSP tables for related records
        counts = {}

        tables = [
            ('tl_visions', 'TL Visions'),
            ('annual_visions', 'Annual Visions'),
            ('annual_plans', 'Annual Plans'),
            ('annual_initiatives', 'Annual Initiatives'),
            ('quarter_initiatives', 'Quarter Initiatives'),
            ('month_tactics', 'Month Tactics'),
            ('week_actions', 'Week Actions'),
            # RN-M1 gave these two segment_description_id. They were NOT in
            # this list, and the new column was declared ON DELETE SET NULL —
            # so deleting a segment with plan elements under it reported "no
            # child records", nulled their links, and the next re-filing
            # cascade raised `ValueError: Segment '<name>' not found.`
            #
            # That is the exact failure this whole change exists to remove,
            # reintroduced by the change itself. A refusal is the correct
            # answer here: an Annual Plan Element under a segment IS a child.
            ('annual_plan_elements', 'Annual Plan Elements'),
            ('annual_vision_elements', 'Annual Vision Elements'),
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
