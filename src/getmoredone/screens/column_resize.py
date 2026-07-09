"""Reusable spreadsheet-style column resizing for list screens.

One `ColumnResizer` instance per screen owns its column widths, persistence,
the draggable divider handles, and live text re-clamping. Screens keep their
own row/header rendering but delegate widths, clamp counts, and drag handling
here so the behaviour is identical across screens (Today, Scheduler, ...).

Used by `screens/today.py` and `screens/drag_schedule.py`.
"""

from dataclasses import dataclass

import customtkinter as ctk

from .title_format import format_column_text

# Approximate pixels per character at the size-14 list font. Used to translate a
# column's pixel width into a character budget for `format_column_text`.
CHAR_PX = 8


def chars_for_width(width_px: int, char_px: int = CHAR_PX) -> int:
    """How many characters fit in a column of the given pixel width (>= 1)."""
    return max(1, int(width_px) // max(1, char_px))


@dataclass
class ColumnSpec:
    """One managed column.

    key:          stable id, also the persistence sub-key and cell tag.
    grid_col:     grid column index used in BOTH the header and each row frame.
    default_width/min_width/max_width: pixel bounds.
    resizable:    when False, the column has a fixed width and no divider handle.
    """

    key: str
    grid_col: int
    default_width: int
    min_width: int = 80
    max_width: int = 800
    resizable: bool = True


class ColumnResizer:
    """Owns column widths + persistence + divider drag + live re-clamp.

    text_pad wraps clamped cell text (the Scheduler pills use `" text "`).
    """

    def __init__(self, owner, settings, prefix, specs, char_px=CHAR_PX, text_pad="",
                 set_cell_width=True):
        self.owner = owner
        self.settings = settings
        self.prefix = prefix
        self.specs = {s.key: s for s in specs}
        self.order = [s.key for s in specs]
        self.char_px = char_px
        self.text_pad = text_pad
        # When True, a row cell's own width is set to the column width (needed for
        # solid-colour pill labels). When False, the column width is carried by the
        # grid minsize alone and only the cell text is re-clamped (e.g. Today, whose
        # title label sits inside a sub-frame).
        self.set_cell_width = set_cell_width
        self._widths = self._load_widths()
        self._rows = []          # list[(frame, cells)] ; cells: [(key, label, full, reserve)]
        self._header = None      # (header_frame, {key: label})
        self._drag = None        # (key, x_root_start, width_start)

    # ------------------------------------------------------------------ widths
    def _setting_attr(self) -> str:
        return f"{self.prefix}_col_widths"

    def _load_widths(self) -> dict:
        stored = getattr(self.settings, self._setting_attr(), None) or {}
        widths = {}
        for key, spec in self.specs.items():
            raw = stored.get(key)
            if raw is None and key == "title":
                # Legacy single-title scalar from before this module existed.
                raw = getattr(self.settings, f"{self.prefix}_title_col_width", None)
            widths[key] = self._clamp(spec, raw if raw else spec.default_width)
        return widths

    @staticmethod
    def _clamp(spec: ColumnSpec, width) -> int:
        return max(spec.min_width, min(spec.max_width, int(width)))

    def width(self, key: str) -> int:
        return self._widths[key]

    def chars(self, key: str, reserve: int = 0) -> int:
        return max(1, chars_for_width(self._widths[key], self.char_px) - reserve)

    def cell_text(self, key: str, full_text, reserve: int = 0) -> str:
        """Clamped, padded text for a cell at the column's current width."""
        clamped = format_column_text(full_text, self.chars(key, reserve))
        return f"{self.text_pad}{clamped}{self.text_pad}"

    def _persist(self) -> None:
        stored = dict(getattr(self.settings, self._setting_attr(), None) or {})
        stored.update(self._widths)
        setattr(self.settings, self._setting_attr(), stored)
        self.settings.save()

    # -------------------------------------------------------------------- grid
    def apply_grid(self, frame) -> None:
        """Set each managed column's grid minsize on a header or row frame."""
        for key in self.order:
            frame.grid_columnconfigure(self.specs[key].grid_col, minsize=self._widths[key])

    # ------------------------------------------------------------------ header
    def build_dividers(self, header_frame, header_labels, height=22, fg_color=None) -> None:
        """Add a draggable divider at each resizable column's right edge.

        header_labels maps column key -> the header CTkLabel (so its width can be
        kept in sync during a drag).
        """
        self._header = (header_frame, dict(header_labels))
        for key in self.order:
            spec = self.specs[key]
            if not spec.resizable:
                continue
            handle = ctk.CTkFrame(
                header_frame,
                width=4,
                height=height,
                corner_radius=0,
                fg_color=fg_color if fg_color is not None else ("gray70", "gray30"),
                cursor="sb_h_double_arrow",
            )
            handle.grid(row=0, column=spec.grid_col, sticky="nse", padx=0, pady=2)
            handle.bind("<Button-1>", lambda e, k=key: self._on_start(e, k))
            handle.bind("<B1-Motion>", lambda e, k=key: self._on_drag(e, k))
            handle.bind("<ButtonRelease-1>", lambda e, k=key: self._on_stop(e, k))

    # -------------------------------------------------------------------- rows
    def register_row(self, frame, cells) -> None:
        """Register a row for live resize.

        cells: iterable of (key, label) or (key, label, full_text) or
        (key, label, full_text, reserve). full_text/reserve enable re-clamping.
        """
        self.apply_grid(frame)
        norm = []
        for cell in cells:
            key, label = cell[0], cell[1]
            full = cell[2] if len(cell) > 2 else None
            reserve = cell[3] if len(cell) > 3 else 0
            norm.append((key, label, full, reserve))
        self._rows.append((frame, norm))

    def clear_rows(self) -> None:
        self._rows = []

    # -------------------------------------------------------------------- drag
    def _on_start(self, event, key) -> None:
        self._drag = (key, event.x_root, self._widths[key])

    def _on_drag(self, event, key) -> None:
        if not self._drag:
            return
        k, x0, w0 = self._drag
        new_width = self._clamp(self.specs[k], w0 + (event.x_root - x0))
        if new_width != self._widths[k]:
            self._widths[k] = new_width
            self._apply_live(k)

    def _on_stop(self, event, key) -> None:
        self._drag = None
        self._persist()

    def _apply_live(self, key) -> None:
        """Push the dragged column's new width to the header and every row."""
        spec = self.specs[key]
        width = self._widths[key]

        if self._header is not None:
            header_frame, header_labels = self._header
            if header_frame.winfo_exists():
                header_frame.grid_columnconfigure(spec.grid_col, minsize=width)
            label = header_labels.get(key)
            if label is not None and label.winfo_exists():
                label.configure(width=width)

        for frame, cells in self._rows:
            if not frame.winfo_exists():
                continue
            frame.grid_columnconfigure(spec.grid_col, minsize=width)
            for ckey, label, full, reserve in cells:
                if ckey != key or not label.winfo_exists():
                    continue
                if self.set_cell_width:
                    label.configure(width=width)
                if full is not None:
                    label.configure(text=self.cell_text(key, full, reserve))
