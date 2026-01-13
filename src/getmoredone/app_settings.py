"""
Application settings management.
Stores user preferences like Obsidian vault path.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class AppSettings:
    """Application settings."""

    obsidian_vault_path: Optional[str] = None
    obsidian_notes_subfolder: str = "GetMoreDone"

    @classmethod
    def get_settings_path(cls) -> Path:
        """Get the path to the settings file."""
        return Path(__file__).parent.parent.parent / "data" / "settings.json"

    @classmethod
    def load(cls) -> 'AppSettings':
        """Load settings from file."""
        settings_path = cls.get_settings_path()

        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return cls()

        return cls()

    def save(self):
        """Save settings to file."""
        settings_path = self.get_settings_path()

        # Ensure data directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(settings_path, 'w') as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def validate_vault_path(self) -> bool:
        """Check if vault path exists."""
        if not self.obsidian_vault_path:
            return False
        return Path(self.obsidian_vault_path).exists()

    def get_notes_folder(self) -> Optional[Path]:
        """Get the full path to the notes subfolder."""
        if not self.obsidian_vault_path:
            return None

        vault = Path(self.obsidian_vault_path)
        if not vault.exists():
            return None

        notes_folder = vault / self.obsidian_notes_subfolder
        return notes_folder
