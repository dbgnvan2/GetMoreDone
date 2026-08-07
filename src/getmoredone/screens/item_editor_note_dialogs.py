"""Obsidian-related dialogs extracted from item_editor_dialogs.py."""

from __future__ import annotations

import re
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog

from ..app_settings import AppSettings
from ..models import ItemLink
from ..theme import button_style, status_text_color


def _extract_frontmatter_tags(content: str) -> list:
    """Extract Obsidian frontmatter tags from a note's raw text.

    Supports the inline form ``tags: [a, b]`` and the block form::

        tags:
          - a
          - b

    The block form is scoped to the ``tags:`` key only, so sibling list-typed
    properties (e.g. Prev/Next, which the Create-Note export now writes) do not
    leak their list items into tag results. Inline ``#tags`` in the body are
    handled separately by the caller.
    """
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        return []
    frontmatter = fm_match.group(1)

    # Inline form: tags: [a, b]
    inline = re.search(r'^[ \t]*tags:[ \t]*\[(.*?)\]', frontmatter, re.MULTILINE)
    if inline:
        return [t.strip().strip('"\'') for t in inline.group(1).split(',') if t.strip()]

    # Block form — collect list items only within the tags: block. The block
    # starts at a bare `tags:` line and ends at the next top-level key (or any
    # other non-list line).
    tags = []
    in_block = False
    for line in frontmatter.splitlines():
        if re.match(r'^[ \t]*tags:[ \t]*$', line):
            in_block = True
            continue
        if not in_block:
            continue
        item = re.match(r'^[ \t]*-[ \t]*(.+?)[ \t]*$', line)
        if item:
            val = item.group(1).strip().strip('"\'')
            if val:
                tags.append(val)
        elif line.strip() == '':
            continue  # tolerate blank lines within the block
        else:
            break  # a new key (or any non-list line) ends the tags block
    return tags

class CreateNoteDialog(ctk.CTkToplevel):
    """Dialog for creating a new Obsidian note."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str,
                 entity_title: str, initial_content: str = ""):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_title = entity_title
        self.initial_content = initial_content or ""
        self.parent_window = parent

        self.title(f"Create Note for: {entity_title}")
        self.geometry("560x460")

        self.create_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Ensure dialog is visible and on top
        self.lift()
        self.focus_force()

        # Center on parent
        self.center_on_parent()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Note title
        ctk.CTkLabel(main_frame, text="Note Title:").pack(pady=(0, 5))
        self.title_var = ctk.StringVar(value=f"{self.entity_title} Notes")
        self.title_entry = ctk.CTkEntry(
            main_frame, textvariable=self.title_var, width=400)
        self.title_entry.pack(pady=(0, 15))

        # Initial content — pre-filled from the item's Description / Next Action
        # when creating a note from an Action Item (editable before saving).
        ctk.CTkLabel(main_frame, text="Initial Content:").pack(pady=(0, 5))
        self.content_text = ctk.CTkTextbox(main_frame, width=460, height=220)
        self.content_text.pack(fill="both", expand=True, pady=(0, 15))
        if self.initial_content:
            self.content_text.insert("1.0", self.initial_content)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_create = ctk.CTkButton(
            btn_frame,
            text="Create & Open",
            command=self.create_note,
            **button_style("primary"),
            width=120
        )
        btn_create.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100, **button_style("secondary"))
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(
            main_frame, text="", text_color=status_text_color("error"), wraplength=400)
        self.error_label.pack(pady=(10, 0))

    def create_note(self):
        """Create the note file and link it."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import create_obsidian_note, open_in_obsidian
        from ..models import ItemLink, ContactLink, ProjectBoardLink

        title = self.title_var.get().strip()
        if not title:
            self.error_label.configure(text="Error: Note title is required")
            return

        content = self.content_text.get("1.0", "end-1c").strip()

        # Load settings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        try:
            # M7.A.5 — Project notes go to the configured Project Notes Folder
            # (falls back to obsidian_notes_subfolder when blank). Other entity
            # types continue to use obsidian_notes_subfolder.
            # Spec: docs/implementation_plan_2026-06-06_project_notes.md#M7.A.5
            # Tests: tests/test_project_notes.py::TestM7Settings::test_create_note_for_project_writes_to_project_folder
            if self.entity_type == "project_board":
                target_subfolder = settings.get_project_notes_subfolder_or_default()
            else:
                target_subfolder = settings.obsidian_notes_subfolder

            # Create note file
            file_path = create_obsidian_note(
                vault_path=settings.obsidian_vault_path,
                subfolder=target_subfolder,
                entity_id=self.entity_id,
                title=title,
                initial_content=content,
            )

            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)
            elif self.entity_type == "project_board":
                link = ProjectBoardLink(
                    project_board_id=self.entity_id,
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_project_board_link(link)

            # Open in Obsidian
            open_in_obsidian(file_path, settings.obsidian_vault_path)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 560
        dialog_height = 460

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class LinkNoteDialog(ctk.CTkToplevel):
    """Dialog for linking an existing note file."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.parent_window = parent
        self.available_notes = []

        self.title("Link Existing Note")
        self.geometry("600x500")

        self.create_form()
        self.load_available_notes()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Search/filter by note title
        ctk.CTkLabel(main_frame, text="Search Notes:", font=ctk.CTkFont(
            size=12, weight="bold")).pack(pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_notes())
        self.search_entry = ctk.CTkEntry(main_frame, textvariable=self.search_var, width=500,
                                         placeholder_text="Search by title, or use file:name or tag:tagname")
        self.search_entry.pack(pady=(0, 10))

        # Display label
        ctk.CTkLabel(main_frame, text="Display Label (optional):").pack(
            pady=(0, 5))
        self.label_var = ctk.StringVar()
        self.label_entry = ctk.CTkEntry(
            main_frame, textvariable=self.label_var, width=500)
        self.label_entry.pack(pady=(0, 15))

        # Available notes list
        ctk.CTkLabel(main_frame, text="Available Notes:", font=ctk.CTkFont(
            size=12, weight="bold")).pack(pady=(0, 5))

        self.notes_frame = ctk.CTkScrollableFrame(main_frame, height=200)
        self.notes_frame.pack(fill="both", expand=True, pady=(0, 15))
        self.notes_frame.grid_columnconfigure(0, weight=1)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_browse = ctk.CTkButton(
            btn_frame,
            text="Browse Files...",
            command=self.browse_file,
            width=120
        )
        btn_browse.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancel", command=self.destroy, width=100, **button_style("secondary"))
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(
            main_frame, text="", text_color=status_text_color("error"), wraplength=500)
        self.error_label.pack(pady=(10, 0))

    def load_available_notes(self):
        """Load all markdown files from vault (searches entire vault)."""
        from ..app_settings import AppSettings
        from pathlib import Path
        import re

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        vault_path = Path(settings.obsidian_vault_path)
        if not vault_path.exists():
            self.error_label.configure(text="Error: Vault path does not exist")
            return

        # Search entire vault, not just GetMoreDone subfolder
        search_path = vault_path

        # Find all .md files
        try:
            self.available_notes = []
            for md_file in search_path.rglob("*.md"):
                # Extract frontmatter tags (scoped to the tags: key) plus
                # inline #tags from the body.
                tags = []
                try:
                    content = md_file.read_text(encoding='utf-8')
                    tags = _extract_frontmatter_tags(content)
                    # Also look for inline tags (#tag format)
                    inline_tags = re.findall(r'#(\w+)', content)
                    tags.extend(inline_tags)
                    tags = list(set(tags))  # Remove duplicates
                except Exception:
                    pass  # If we can't read tags, continue anyway

                self.available_notes.append({
                    'path': str(md_file),
                    'title': md_file.stem,
                    'relative': str(md_file.relative_to(vault_path)),
                    'tags': tags
                })

            # Sort by title
            self.available_notes.sort(key=lambda x: x['title'].lower())

            # Display notes
            self.filter_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error loading notes: {str(e)}")

    def filter_notes(self):
        """Filter notes based on search text with support for file: and tag: prefixes."""
        # Clear current list
        for widget in self.notes_frame.winfo_children():
            widget.destroy()

        search_text = self.search_var.get().strip()

        if not search_text:
            # No search text - show all notes (up to 50)
            filtered = self.available_notes[:50]
        else:
            # Parse search prefixes (Obsidian-style)
            search_lower = search_text.lower()

            if search_lower.startswith("file:"):
                # Search by filename only
                query = search_text[5:].strip().lower()
                filtered = [
                    n for n in self.available_notes if query in n['title'].lower()]
            elif search_lower.startswith("tag:"):
                # Search by tags
                query = search_text[4:].strip().lower()
                filtered = [n for n in self.available_notes
                            if any(query in tag.lower() for tag in n.get('tags', []))]
            else:
                # Default: search in title (case-insensitive contains)
                query = search_text.lower()
                filtered = [
                    n for n in self.available_notes if query in n['title'].lower()]

        if not filtered:
            ctk.CTkLabel(
                self.notes_frame,
                text="No notes found" if search_text else "No notes in vault",
                text_color=status_text_color("muted")
            ).pack(pady=20)
            return

        # Display filtered notes
        for note in filtered[:50]:  # Limit to 50 results
            self.create_note_row(note)

    def create_note_row(self, note: dict):
        """Create a row for a note."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Select button — packed first (side="right") so a long note title can
        # never push it off the edge of the panel.
        btn_select = ctk.CTkButton(
            frame,
            text="Link This",
            width=80,
            command=lambda: self.link_note_file(note['path'], note['title']),
            **button_style("primary"),
        )
        btn_select.pack(side="right", padx=5)

        # Note info
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            info_frame,
            text=note['title'],
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=5)

        ctk.CTkLabel(
            info_frame,
            text=note['relative'],
            anchor="w",
            font=ctk.CTkFont(size=10),
            text_color=status_text_color("muted")
        ).pack(anchor="w", padx=5)

        # Display tags if present
        if note.get('tags'):
            # Show first 5 tags
            tags_text = " ".join([f"#{tag}" for tag in note['tags'][:5]])
            ctk.CTkLabel(
                info_frame,
                text=tags_text,
                anchor="w",
                font=ctk.CTkFont(size=9),
                text_color=status_text_color("muted")
            ).pack(anchor="w", padx=5)

    def link_note_file(self, file_path: str, default_label: str):
        """Link the selected note file."""
        from ..models import ItemLink, ContactLink, ProjectBoardLink
        from pathlib import Path

        # Get label (use custom if provided, otherwise use note title)
        label = self.label_var.get().strip() or default_label

        try:
            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)
            elif self.entity_type == "project_board":
                link = ProjectBoardLink(
                    project_board_id=self.entity_id,
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_project_board_link(link)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def browse_file(self):
        """Browse for a markdown file (fallback option)."""
        from tkinter import filedialog
        from ..app_settings import AppSettings
        from pathlib import Path

        settings = AppSettings.load()

        # Start in vault folder if configured
        initial_dir = None
        if settings.obsidian_vault_path:
            notes_folder = settings.get_notes_folder()
            if notes_folder and notes_folder.exists():
                initial_dir = str(notes_folder)
            else:
                initial_dir = settings.obsidian_vault_path

        file_path = filedialog.askopenfilename(
            title="Select Markdown Note",
            initialdir=initial_dir,
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )

        if file_path:
            # Get title from filename
            title = Path(file_path).stem

            # Link the file
            self.link_note_file(file_path, title)


