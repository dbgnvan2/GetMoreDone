"""
Obsidian integration utilities.
Handles note creation and opening notes in Obsidian.
"""

import os
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional


def create_obsidian_note(
    vault_path: str,
    subfolder: str,
    entity_type: str,
    entity_id: str,
    title: str,
    initial_content: str = "",
    who: Optional[str] = None,
    due_date: Optional[str] = None,
    priority_score: Optional[int] = None
) -> str:
    """
    Create a new Obsidian note file.

    Args:
        vault_path: Path to Obsidian vault
        subfolder: Subfolder within vault (e.g., "GetMoreDone")
        entity_type: "action_item" or "contact"
        entity_id: ID of the entity
        title: Title for the note
        initial_content: Optional initial markdown content
        who: Optional who field for action items
        due_date: Optional due date for action items
        priority_score: Optional priority score for action items

    Returns:
        Full file path to created note

    Raises:
        ValueError: If vault path doesn't exist
    """
    # Validate vault path
    vault = Path(vault_path)
    if not vault.exists():
        raise ValueError(f"Obsidian vault not found: {vault_path}")

    # Create subfolder if needed
    notes_folder = vault / subfolder
    notes_folder.mkdir(exist_ok=True)

    # Sanitize title for filename
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title.replace(' ', '_')
    if not safe_title:
        safe_title = "untitled"

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{entity_type}_{timestamp}_{safe_title[:50]}.md"
    file_path = notes_folder / filename

    # Create frontmatter
    frontmatter_lines = [
        "---",
        f"type: {entity_type}",
        f"entity_id: {entity_id}",
        f'title: "{title}"',
        f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ]

    # Add action item specific metadata
    if entity_type == "action_item":
        if who:
            frontmatter_lines.append(f'who: "{who}"')
        if due_date:
            frontmatter_lines.append(f"due_date: {due_date}")
        if priority_score is not None:
            frontmatter_lines.append(f"priority_score: {priority_score}")

    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    # Create note content
    note_content = f"""{frontmatter}

# {title}

{initial_content}
"""

    # Write file
    file_path.write_text(note_content, encoding='utf-8')

    return str(file_path)


def open_in_obsidian(file_path: str, vault_path: str):
    """
    Open a note file in Obsidian application.

    Uses Obsidian URI scheme (obsidian://open?...) for native integration.
    Falls back to system default app if Obsidian not available.

    Args:
        file_path: Full path to the markdown file
        vault_path: Path to Obsidian vault root

    Raises:
        ValueError: If file is not inside vault
    """
    file_path = Path(file_path)
    vault_path = Path(vault_path)

    # Get relative path from vault root (Obsidian needs this)
    try:
        relative_path = file_path.relative_to(vault_path)
    except ValueError:
        raise ValueError(f"Note file must be inside vault. File: {file_path}, Vault: {vault_path}")

    # Construct Obsidian URI
    # Format: obsidian://open?vault={vault_name}&file={relative_path}
    vault_name = vault_path.name
    # URL encode the file path
    file_path_encoded = str(relative_path).replace('\\', '/')
    obsidian_uri = f"obsidian://open?vault={vault_name}&file={file_path_encoded}"

    # Open URI based on platform
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.call(['open', obsidian_uri])
        elif system == "Windows":
            os.startfile(obsidian_uri)
        elif system == "Linux":
            subprocess.call(['xdg-open', obsidian_uri])
    except Exception as e:
        # Fallback: open with system default app
        print(f"Could not open in Obsidian: {e}. Trying system default app...")
        open_with_default_app(str(file_path))


def open_with_default_app(file_path: str):
    """
    Open file with system default application.

    Fallback when Obsidian is not available.

    Args:
        file_path: Full path to the file
    """
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.call(['open', file_path])
        elif system == "Windows":
            os.startfile(file_path)
        elif system == "Linux":
            subprocess.call(['xdg-open', file_path])
    except Exception as e:
        raise RuntimeError(f"Could not open file: {e}")


def validate_obsidian_setup(vault_path: str, subfolder: str) -> tuple[bool, str]:
    """
    Validate Obsidian vault configuration.

    Args:
        vault_path: Path to Obsidian vault
        subfolder: Subfolder within vault

    Returns:
        Tuple of (is_valid, message)
    """
    if not vault_path:
        return False, "Vault path not configured"

    vault = Path(vault_path)
    if not vault.exists():
        return False, f"Vault path does not exist: {vault_path}"

    if not vault.is_dir():
        return False, f"Vault path is not a directory: {vault_path}"

    # Check if .obsidian folder exists (indicates it's a real vault)
    obsidian_folder = vault / ".obsidian"
    if not obsidian_folder.exists():
        return False, f"Not a valid Obsidian vault (missing .obsidian folder): {vault_path}"

    # Try to create subfolder
    try:
        notes_folder = vault / subfolder
        notes_folder.mkdir(exist_ok=True)
    except Exception as e:
        return False, f"Cannot create notes subfolder: {e}"

    return True, "Vault configuration is valid"
