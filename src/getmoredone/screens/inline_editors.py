"""Small inline editor dialogs for list views."""

from __future__ import annotations

import customtkinter as ctk
from datetime import date, datetime
from typing import Optional

from ..app_settings import AppSettings
from ..date_utils import increment_date
from ..models import PriorityFactors
from ..theme import button_style

# Quick "days from today" offsets shown below the date field. Each button sets
# the date to today + N (weekend-aware). Kept here as config rather than inline
# literals so the ladder is easy to adjust.
TODAY_OFFSET_BUTTONS = [1, 2, 3, 4, 5, 6, 7, 10, 14]


class InlineDateDialog(ctk.CTkToplevel):
    """Popup date editor with quick adjust controls."""

    def __init__(self, parent, title: str, initial_date: Optional[str]):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x175")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.date_var = ctk.StringVar(value=initial_date or "")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(12, 6))

        self.entry = ctk.CTkEntry(row, textvariable=self.date_var, width=220)
        self.entry.pack(side="left", padx=(0, 8))
        self.entry.focus()

        ctk.CTkButton(row, text="Today", width=70, command=lambda: self.set_today(0)).pack(side="left", padx=3)
        ctk.CTkButton(row, text="-1", width=55, command=lambda: self.adjust(-1)).pack(side="left", padx=3)
        ctk.CTkButton(row, text="Clear", width=60, **button_style("secondary"), command=self.clear).pack(side="left", padx=3)

        # Days-from-today ladder: each button sets the date to today + N.
        offsets = ctk.CTkFrame(self, fg_color="transparent")
        offsets.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(offsets, text="From today:").pack(side="left", padx=(0, 4))
        for days in TODAY_OFFSET_BUTTONS:
            ctk.CTkButton(
                offsets, text=f"+{days}", width=34,
                command=lambda d=days: self.set_today(d),
            ).pack(side="left", padx=1)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkButton(actions, text="Save", width=80, **button_style("primary"), command=self.save).pack(side="right", padx=3)
        ctk.CTkButton(actions, text="Cancel", width=80, **button_style("secondary"), command=self.cancel).pack(side="right", padx=3)

    def _entry_raw(self) -> str:
        return (self.entry.get() or "").strip()

    def _parse_date(self, raw: str) -> Optional[date]:
        value = (raw or "").strip()
        if not value:
            return None

        # Preferred canonical form.
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass

        # Common manual inputs.
        for fmt in ("%m/%d/%Y", "%m/%d"):
            try:
                parsed = datetime.strptime(value, fmt).date()
                if fmt == "%m/%d":
                    parsed = parsed.replace(year=date.today().year)
                return parsed
            except ValueError:
                continue
        return None

    def _set_entry_value(self, value: str):
        # Keep both the Entry widget and StringVar in sync for CTk consistency.
        self.date_var.set(value)
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def _current_date(self) -> date:
        parsed = self._parse_date(self._entry_raw())
        return parsed if parsed else date.today()

    def set_today(self, offset_days: int):
        target = date.today()
        if offset_days:
            settings = AppSettings.load()
            target = increment_date(
                target, offset_days, settings.include_saturday, settings.include_sunday
            )
        self._set_entry_value(target.isoformat())

    def adjust(self, delta: int):
        settings = AppSettings.load()
        new_value = increment_date(
            self._current_date(), delta, settings.include_saturday, settings.include_sunday
        )
        self._set_entry_value(new_value.isoformat())

    def clear(self):
        self._set_entry_value("")

    def save(self):
        raw = self._entry_raw()
        if raw:
            parsed = self._parse_date(raw)
            if not parsed:
                return
            self.result = parsed.isoformat()
        else:
            self.result = None
        self.destroy()

    def cancel(self):
        self.result = "__cancel__"
        self.destroy()


class InlinePriorityDialog(ctk.CTkToplevel):
    """Popup priority editor using same factors as full item editor."""

    def __init__(self, parent, item):
        super().__init__(parent)
        self.title(f"Priority Factors (P:{item.priority_score})")
        self.geometry("430x330")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.item = item

        form = ctk.CTkFrame(self)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        importance_values = [f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]
        urgency_values = [f"{k} ({v})" for k, v in PriorityFactors.URGENCY.items()]
        size_values = [f"{k} ({v})" for k, v in PriorityFactors.SIZE.items()]
        value_values = [f"{k} ({v})" for k, v in PriorityFactors.VALUE.items()]

        self.importance_var = ctk.StringVar(value=self._label_for(PriorityFactors.IMPORTANCE, item.importance))
        self.urgency_var = ctk.StringVar(value=self._label_for(PriorityFactors.URGENCY, item.urgency))
        self.size_var = ctk.StringVar(value=self._label_for(PriorityFactors.SIZE, item.size))
        self.value_var = ctk.StringVar(value=self._label_for(PriorityFactors.VALUE, item.value))

        self._combo_row(form, 0, "Importance:", importance_values, self.importance_var)
        self._combo_row(form, 1, "Urgency:", urgency_values, self.urgency_var)
        self._combo_row(form, 2, "Effort-Cost:", size_values, self.size_var)
        self._combo_row(form, 3, "Value:", value_values, self.value_var)

        score_box = ctk.CTkFrame(form)
        score_box.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(14, 8))
        ctk.CTkLabel(score_box, text="Priority Score:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=8, pady=8)
        self.score_label = ctk.CTkLabel(score_box, text="")
        self.score_label.pack(side="left", padx=8, pady=8)
        self.update_score()

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(actions, text="Save", width=90, **button_style("primary"), command=self.save).pack(side="right", padx=4)
        ctk.CTkButton(actions, text="Cancel", width=90, **button_style("secondary"), command=self.cancel).pack(side="right", padx=4)

    def _combo_row(self, parent, row: int, label: str, values: list[str], var: ctk.StringVar):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=5)
        combo = ctk.CTkComboBox(
            parent, values=values, variable=var, width=220, command=lambda _v: self.update_score()
        )
        combo.grid(row=row, column=1, sticky="w", padx=8, pady=5)

    def _label_for(self, mapping: dict[str, int], value: Optional[int]) -> str:
        if value is None:
            return ""
        for k, v in mapping.items():
            if v == value:
                return f"{k} ({v})"
        return ""

    def _value_from(self, raw: str) -> Optional[int]:
        if not raw:
            return None
        try:
            return int(raw.split("(")[-1].replace(")", "").strip())
        except ValueError:
            return None

    def update_score(self):
        i = self._value_from(self.importance_var.get()) or 0
        u = self._value_from(self.urgency_var.get()) or 0
        s = self._value_from(self.size_var.get()) or 0
        v = self._value_from(self.value_var.get()) or 0
        score = i * u * s * v if all([i, u, s, v]) else 0
        self.score_label.configure(text=f"{score} ({i}×{u}×{s}×{v})")

    def save(self):
        self.result = {
            "importance": self._value_from(self.importance_var.get()),
            "urgency": self._value_from(self.urgency_var.get()),
            "size": self._value_from(self.size_var.get()),
            "value": self._value_from(self.value_var.get()),
        }
        self.destroy()

    def cancel(self):
        self.result = "__cancel__"
        self.destroy()
