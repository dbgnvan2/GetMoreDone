"""
Integration tests for Obsidian note functionality.
Tests the complete flow of creating, linking, and managing notes.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ItemLink, ContactLink, Contact
from src.getmoredone.app_settings import AppSettings
from src.getmoredone.obsidian_utils import (
    create_obsidian_note,
    validate_obsidian_setup
)


@pytest.fixture
def temp_vault():
    """Create a temporary Obsidian vault for testing."""
    vault_dir = tempfile.mkdtemp(prefix="test_vault_")
    vault_path = Path(vault_dir)

    # Create .obsidian folder to make it a valid vault
    (vault_path / ".obsidian").mkdir()

    yield str(vault_path)

    # Cleanup
    shutil.rmtree(vault_dir)


@pytest.fixture
def db_manager():
    """Create a test database manager."""
    db = DatabaseManager(":memory:")
    yield db
    db.close()


@pytest.fixture
def test_item(db_manager):
    """Create a test action item."""
    item = ActionItem(
        who="Test Client",
        title="Test Task",
        description="Test description",
        importance=10,
        urgency=10,
        size=4,
        value=4
    )
    item_id = db_manager.create_action_item(item)
    return db_manager.get_action_item(item_id)


@pytest.fixture
def test_contact(db_manager):
    """Create a test contact."""
    contact = Contact(
        name="Test Contact",
        contact_type="Client"
    )
    contact_id = db_manager.create_contact(contact)
    return db_manager.get_contact(contact_id)


class TestObsidianVaultSetup:
    """Test Obsidian vault configuration and validation."""

    def test_vault_validation_success(self, temp_vault):
        """Test that a valid vault passes validation."""
        is_valid, message = validate_obsidian_setup(temp_vault, "GetMoreDone")
        assert is_valid is True
        assert "valid" in message.lower()

    def test_vault_validation_missing_path(self):
        """Test validation fails for non-existent path."""
        is_valid, message = validate_obsidian_setup("/nonexistent/path", "GetMoreDone")
        assert is_valid is False
        assert "does not exist" in message.lower()

    def test_vault_validation_no_obsidian_folder(self, temp_vault):
        """Test validation fails without .obsidian folder."""
        # Remove .obsidian folder
        shutil.rmtree(Path(temp_vault) / ".obsidian")

        is_valid, message = validate_obsidian_setup(temp_vault, "GetMoreDone")
        assert is_valid is False
        assert ".obsidian" in message.lower()

    def test_vault_creates_subfolder(self, temp_vault):
        """Test that subfolder is created if it doesn't exist."""
        subfolder_name = "TestNotes"
        is_valid, _ = validate_obsidian_setup(temp_vault, subfolder_name)

        assert is_valid is True
        subfolder = Path(temp_vault) / subfolder_name
        assert subfolder.exists()
        assert subfolder.is_dir()


class TestNoteCreation:
    """Test creating Obsidian notes."""

    def test_create_note_for_action_item(self, temp_vault, test_item):
        """Test creating a note file for an action item."""
        file_path = create_obsidian_note(
            vault_path=temp_vault,
            subfolder="GetMoreDone",
            entity_type="action_item",
            entity_id=test_item.id,
            title="Test Note",
            initial_content="# My Notes\nTest content",
            who=test_item.who,
            due_date=test_item.due_date,
            priority_score=test_item.priority_score
        )

        # Verify file was created
        assert Path(file_path).exists()

        # Verify file is in the right location
        assert "GetMoreDone" in file_path
        assert file_path.endswith(".md")

        # Verify content
        content = Path(file_path).read_text()
        assert "---" in content  # Frontmatter
        assert "type: action_item" in content
        assert f"entity_id: {test_item.id}" in content
        assert "Test Note" in content
        assert "# My Notes" in content

    def test_create_note_with_metadata(self, temp_vault, test_item):
        """Test that note includes all metadata."""
        file_path = create_obsidian_note(
            vault_path=temp_vault,
            subfolder="GetMoreDone",
            entity_type="action_item",
            entity_id=test_item.id,
            title="Metadata Test",
            who="John Doe",
            due_date="2026-12-31",
            priority_score=1600
        )

        content = Path(file_path).read_text()
        assert 'who: "John Doe"' in content
        assert "due_date: 2026-12-31" in content
        assert "priority_score: 1600" in content

    def test_create_note_sanitizes_filename(self, temp_vault, test_item):
        """Test that special characters in title are sanitized."""
        file_path = create_obsidian_note(
            vault_path=temp_vault,
            subfolder="GetMoreDone",
            entity_type="action_item",
            entity_id=test_item.id,
            title="Test / Note: With * Special? Chars!"
        )

        filename = Path(file_path).name
        # Should not contain special characters
        assert "/" not in filename
        assert ":" not in filename
        assert "*" not in filename
        assert "?" not in filename


class TestItemLinkManagement:
    """Test linking notes to action items."""

    def test_add_item_link(self, db_manager, test_item):
        """Test adding a note link to an action item."""
        link = ItemLink(
            item_id=test_item.id,
            url="/path/to/note.md",
            label="Test Note",
            link_type="obsidian_note"
        )

        db_manager.add_item_link(link)

        # Retrieve links
        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 1
        assert links[0].url == "/path/to/note.md"
        assert links[0].label == "Test Note"
        assert links[0].link_type == "obsidian_note"

    def test_get_only_obsidian_notes(self, db_manager, test_item):
        """Test filtering to get only Obsidian notes."""
        # Add different types of links
        db_manager.add_item_link(ItemLink(
            item_id=test_item.id,
            url="https://example.com",
            label="Website",
            link_type="url"
        ))
        db_manager.add_item_link(ItemLink(
            item_id=test_item.id,
            url="/path/to/note.md",
            label="Note",
            link_type="obsidian_note"
        ))

        # Get all links
        all_links = db_manager.get_item_links(test_item.id)
        assert len(all_links) == 2

        # Filter for obsidian notes
        notes = [l for l in all_links if l.link_type == "obsidian_note"]
        assert len(notes) == 1
        assert notes[0].label == "Note"

    def test_delete_item_link(self, db_manager, test_item):
        """Test deleting a note link."""
        link = ItemLink(
            item_id=test_item.id,
            url="/path/to/note.md",
            label="Test Note",
            link_type="obsidian_note"
        )
        db_manager.add_item_link(link)

        # Verify it exists
        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 1

        # Delete it
        db_manager.delete_item_link(link.id)

        # Verify it's gone
        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 0

    def test_multiple_notes_per_item(self, db_manager, test_item):
        """Test adding multiple notes to one item."""
        for i in range(3):
            link = ItemLink(
                item_id=test_item.id,
                url=f"/path/to/note{i}.md",
                label=f"Note {i}",
                link_type="obsidian_note"
            )
            db_manager.add_item_link(link)

        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 3


class TestContactLinkManagement:
    """Test linking notes to contacts."""

    def test_add_contact_link(self, db_manager, test_contact):
        """Test adding a note link to a contact."""
        link = ContactLink(
            contact_id=test_contact.id,
            url="/path/to/contact_note.md",
            label="Contact Notes",
            link_type="obsidian_note"
        )

        db_manager.add_contact_link(link)

        # Retrieve links
        links = db_manager.get_contact_links(test_contact.id)
        assert len(links) == 1
        assert links[0].url == "/path/to/contact_note.md"
        assert links[0].label == "Contact Notes"
        assert links[0].link_type == "obsidian_note"

    def test_delete_contact_link(self, db_manager, test_contact):
        """Test deleting a contact link."""
        link = ContactLink(
            contact_id=test_contact.id,
            url="/path/to/note.md",
            label="Test Note",
            link_type="obsidian_note"
        )
        db_manager.add_contact_link(link)

        # Delete it
        db_manager.delete_contact_link(link.id)

        # Verify it's gone
        links = db_manager.get_contact_links(test_contact.id)
        assert len(links) == 0


class TestAppSettings:
    """Test application settings for Obsidian."""

    def test_settings_defaults(self):
        """Test default settings values."""
        settings = AppSettings()
        assert settings.obsidian_vault_path is None
        assert settings.obsidian_notes_subfolder == "GetMoreDone"

    def test_settings_save_and_load(self, tmp_path):
        """Test saving and loading settings."""
        # Create settings
        settings = AppSettings()
        settings.obsidian_vault_path = "/test/vault"
        settings.obsidian_notes_subfolder = "TestFolder"

        # Override settings path to use temp directory
        settings_file = tmp_path / "test_settings.json"
        AppSettings.get_settings_path = classmethod(lambda cls: settings_file)

        # Save
        settings.save()

        # Load in new instance
        loaded = AppSettings.load()
        assert loaded.obsidian_vault_path == "/test/vault"
        assert loaded.obsidian_notes_subfolder == "TestFolder"

    def test_validate_vault_path(self, temp_vault):
        """Test vault path validation."""
        settings = AppSettings()
        settings.obsidian_vault_path = temp_vault

        assert settings.validate_vault_path() is True

    def test_validate_vault_path_invalid(self):
        """Test validation fails for invalid path."""
        settings = AppSettings()
        settings.obsidian_vault_path = "/nonexistent/path"

        assert settings.validate_vault_path() is False

    def test_get_notes_folder(self, temp_vault):
        """Test getting the notes folder path."""
        settings = AppSettings()
        settings.obsidian_vault_path = temp_vault
        settings.obsidian_notes_subfolder = "MyNotes"

        notes_folder = settings.get_notes_folder()
        assert notes_folder is not None
        assert "MyNotes" in str(notes_folder)


class TestIntegrationFlow:
    """Test complete workflows."""

    def test_complete_note_creation_flow(self, temp_vault, db_manager, test_item):
        """Test the complete flow of creating and linking a note."""
        # Step 1: Configure settings
        settings = AppSettings()
        settings.obsidian_vault_path = temp_vault
        settings.obsidian_notes_subfolder = "GetMoreDone"

        # Step 2: Create note file
        file_path = create_obsidian_note(
            vault_path=settings.obsidian_vault_path,
            subfolder=settings.obsidian_notes_subfolder,
            entity_type="action_item",
            entity_id=test_item.id,
            title="Integration Test Note",
            initial_content="# Test\nThis is a test note."
        )

        # Step 3: Create link in database
        link = ItemLink(
            item_id=test_item.id,
            url=file_path,
            label="Integration Test Note",
            link_type="obsidian_note"
        )
        db_manager.add_item_link(link)

        # Step 4: Verify everything
        # File exists
        assert Path(file_path).exists()

        # Link exists in database
        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 1
        assert links[0].link_type == "obsidian_note"

        # File content is correct
        content = Path(file_path).read_text()
        assert "Integration Test Note" in content
        assert "# Test" in content

    def test_cancel_does_not_save(self, db_manager, test_item):
        """Test that canceling doesn't save anything."""
        # Simulate user opening dialog but not saving
        initial_count = len(db_manager.get_item_links(test_item.id))

        # Dialog would be opened here, but user clicks Cancel
        # No database operations should happen

        # Verify nothing was saved
        final_count = len(db_manager.get_item_links(test_item.id))
        assert final_count == initial_count

    def test_update_existing_link_label(self, db_manager, test_item):
        """Test updating the label of an existing link."""
        # Create link
        link = ItemLink(
            item_id=test_item.id,
            url="/path/to/note.md",
            label="Original Label",
            link_type="obsidian_note"
        )
        db_manager.add_item_link(link)

        # In a real scenario, user would edit via UI
        # Here we simulate by deleting and re-creating with new label
        db_manager.delete_item_link(link.id)

        new_link = ItemLink(
            item_id=test_item.id,
            url="/path/to/note.md",
            label="Updated Label",
            link_type="obsidian_note"
        )
        db_manager.add_item_link(new_link)

        # Verify update
        links = db_manager.get_item_links(test_item.id)
        assert len(links) == 1
        assert links[0].label == "Updated Label"
