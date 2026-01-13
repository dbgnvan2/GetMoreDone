"""
Comprehensive tests for contact integration with action items.
Tests the WHO field autocomplete, contact lookup, and contact_id linking.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from getmoredone.db_manager import DatabaseManager
from getmoredone.models import Contact, ActionItem


class TestContactIntegration:
    """Test contact integration with action items."""

    @pytest.fixture
    def db(self):
        """Create in-memory database for testing."""
        db = DatabaseManager(':memory:')
        yield db
        db.close()

    @pytest.fixture
    def sample_contacts(self, db):
        """Create sample contacts for testing."""
        contacts = [
            Contact(name="John Doe", contact_type="Client", email="john@example.com"),
            Contact(name="Jane Smith", contact_type="Personal", email="jane@example.com"),
            Contact(name="Acme Company", contact_type="Client", email="info@acme.com"),
            Contact(name="Bob Johnson", contact_type="Contact", phone="555-1234"),
        ]
        contact_ids = []
        for contact in contacts:
            contact_id = db.create_contact(contact)
            contact_ids.append(contact_id)
        return contact_ids

    # ==================== FR: Contact CRUD Operations ====================

    def test_create_contact(self, db):
        """FR: System can create new contacts."""
        contact = Contact(
            name="Test Contact",
            contact_type="Client",
            email="test@example.com",
            phone="555-0000"
        )
        contact_id = db.create_contact(contact)

        assert contact_id is not None
        assert contact_id > 0

        # Verify contact was created
        retrieved = db.get_contact(contact_id)
        assert retrieved is not None
        assert retrieved.name == "Test Contact"
        assert retrieved.contact_type == "Client"
        assert retrieved.email == "test@example.com"
        assert retrieved.phone == "555-0000"

    def test_get_contact_by_name(self, db, sample_contacts):
        """FR: System can retrieve contact by exact name match."""
        contact = db.get_contact_by_name("John Doe")

        assert contact is not None
        assert contact.name == "John Doe"
        assert contact.contact_type == "Client"
        assert contact.email == "john@example.com"

    def test_search_contacts(self, db, sample_contacts):
        """FR: Typing in Who field searches contacts table."""
        # Search by partial name
        results = db.search_contacts("john", active_only=True)
        assert len(results) >= 2  # "John Doe" and "Bob Johnson"
        names = [c.name for c in results]
        assert "John Doe" in names
        assert "Bob Johnson" in names

        # Search by email
        results = db.search_contacts("acme", active_only=True)
        assert len(results) == 1
        assert results[0].name == "Acme Company"

        # Search by phone
        results = db.search_contacts("555-1234", active_only=True)
        assert len(results) == 1
        assert results[0].name == "Bob Johnson"

    def test_update_contact(self, db, sample_contacts):
        """FR: System can update existing contacts."""
        contact_id = sample_contacts[0]
        contact = db.get_contact(contact_id)

        contact.phone = "555-9999"
        contact.notes = "Updated notes"
        db.update_contact(contact)

        # Verify update
        updated = db.get_contact(contact_id)
        assert updated.phone == "555-9999"
        assert updated.notes == "Updated notes"

    def test_delete_contact(self, db):
        """FR: System can delete contacts (when not referenced)."""
        contact = Contact(name="Temp Contact", contact_type="Contact")
        contact_id = db.create_contact(contact)

        # Delete contact
        db.delete_contact(contact_id)

        # Verify deletion
        deleted = db.get_contact(contact_id)
        assert deleted is None

    def test_deactivate_contact(self, db, sample_contacts):
        """FR: System can deactivate contacts (soft delete)."""
        contact_id = sample_contacts[0]

        # Deactivate contact
        db.deactivate_contact(contact_id)

        # Contact should not appear in active contacts
        active_contacts = db.get_all_contacts(active_only=True)
        contact_ids = [c.id for c in active_contacts]
        assert contact_id not in contact_ids

        # But should appear in all contacts
        all_contacts = db.get_all_contacts(active_only=False)
        contact_ids = [c.id for c in all_contacts]
        assert contact_id in contact_ids

    # ==================== FR: Contact-ActionItem Linking ====================

    def test_action_item_with_contact_id(self, db, sample_contacts):
        """FR: contact_id is stored on ActionItem for proper linking."""
        contact_id = sample_contacts[0]
        contact = db.get_contact(contact_id)

        # Create action item with contact
        item = ActionItem(
            who=contact.name,
            contact_id=contact_id,
            title="Follow up with John",
            importance=10,
            urgency=10,
            size=2,
            value=4
        )
        item_id = db.create_action_item(item, apply_defaults=False)

        # Verify contact_id was saved
        retrieved = db.get_action_item(item_id)
        assert retrieved.contact_id == contact_id
        assert retrieved.who == contact.name

    def test_action_item_without_contact(self, db):
        """FR: ActionItems can exist without contact_id (for non-contact entries)."""
        item = ActionItem(
            who="Self",
            contact_id=None,
            title="Personal task",
            importance=5,
            urgency=5,
            size=2,
            value=2
        )
        item_id = db.create_action_item(item, apply_defaults=False)

        retrieved = db.get_action_item(item_id)
        assert retrieved.contact_id is None
        assert retrieved.who == "Self"

    def test_update_action_item_contact(self, db, sample_contacts):
        """FR: contact_id can be updated on existing ActionItems."""
        # Create item without contact
        item = ActionItem(
            who="Someone",
            contact_id=None,
            title="Test task",
            importance=5,
            urgency=5,
            size=2,
            value=2
        )
        item_id = db.create_action_item(item, apply_defaults=False)

        # Update to link to contact
        contact_id = sample_contacts[0]
        contact = db.get_contact(contact_id)

        item = db.get_action_item(item_id)
        item.who = contact.name
        item.contact_id = contact_id
        db.update_action_item(item)

        # Verify update
        updated = db.get_action_item(item_id)
        assert updated.contact_id == contact_id
        assert updated.who == contact.name

    def test_duplicate_preserves_contact_id(self, db, sample_contacts):
        """FR: Duplicating ActionItem preserves contact_id link."""
        contact_id = sample_contacts[0]
        contact = db.get_contact(contact_id)

        item = ActionItem(
            who=contact.name,
            contact_id=contact_id,
            title="Original task",
            importance=10,
            urgency=10,
            size=2,
            value=4
        )
        item_id = db.create_action_item(item, apply_defaults=False)

        # Duplicate item
        duplicated_id = db.duplicate_action_item(item_id)

        # Verify duplicate has same contact_id
        duplicated = db.get_action_item(duplicated_id)
        assert duplicated.contact_id == contact_id
        assert duplicated.who == contact.name

    def test_contact_foreign_key_constraint(self, db, sample_contacts):
        """FR: Contact deletion fails when referenced by ActionItems."""
        contact_id = sample_contacts[0]
        contact = db.get_contact(contact_id)

        # Create action item referencing contact
        item = ActionItem(
            who=contact.name,
            contact_id=contact_id,
            title="Task for John",
            importance=5,
            urgency=5,
            size=2,
            value=2
        )
        db.create_action_item(item, apply_defaults=False)

        # Try to delete contact - should fail
        with pytest.raises(Exception):
            db.delete_contact(contact_id)

    # ==================== FR: Contact Name Uniqueness ====================

    def test_duplicate_contact_name_fails(self, db, sample_contacts):
        """FR: Contact names must be unique."""
        # Try to create contact with duplicate name
        duplicate = Contact(name="John Doe", contact_type="Client")

        # This should fail in the UI validation, but let's test DB level
        # SQLite UNIQUE constraint will raise an error
        with pytest.raises(Exception):
            db.create_contact(duplicate)

    # ==================== FR: Contact Search Functionality ====================

    def test_search_empty_string_returns_no_results(self, db, sample_contacts):
        """FR: Empty search returns no results."""
        results = db.search_contacts("", active_only=True)
        # Empty search should return no results (not all contacts)
        assert len(results) == 0

    def test_search_case_insensitive(self, db, sample_contacts):
        """FR: Contact search is case-insensitive."""
        results_upper = db.search_contacts("JOHN", active_only=True)
        results_lower = db.search_contacts("john", active_only=True)
        results_mixed = db.search_contacts("JoHn", active_only=True)

        assert len(results_upper) >= 2
        assert len(results_lower) >= 2
        assert len(results_mixed) >= 2

    def test_search_multiple_fields(self, db):
        """FR: Search works across name, email, and notes fields."""
        # Create contact with notes
        contact = Contact(
            name="Test Person",
            email="test@example.com",
            notes="VIP client from California"
        )
        contact_id = db.create_contact(contact)

        # Search by name
        results = db.search_contacts("Test Person", active_only=True)
        assert len(results) >= 1

        # Search by email
        results = db.search_contacts("test@example", active_only=True)
        assert len(results) >= 1

        # Search by notes
        results = db.search_contacts("California", active_only=True)
        assert len(results) >= 1

    # ==================== FR: Contact Types ====================

    def test_contact_types(self, db):
        """FR: Contacts support Client, Contact, and Personal types."""
        types = ["Client", "Contact", "Personal"]

        for contact_type in types:
            contact = Contact(
                name=f"Test {contact_type}",
                contact_type=contact_type
            )
            contact_id = db.create_contact(contact)
            retrieved = db.get_contact(contact_id)
            assert retrieved.contact_type == contact_type

    # ==================== NFR: Data Integrity ====================

    def test_contact_id_nullable(self, db):
        """NFR: contact_id is optional (nullable) on ActionItems."""
        item = ActionItem(
            who="Someone",
            contact_id=None,  # Explicitly None
            title="Task",
            importance=5,
            urgency=5,
            size=2,
            value=2
        )
        item_id = db.create_action_item(item, apply_defaults=False)
        retrieved = db.get_action_item(item_id)

        assert retrieved.contact_id is None

    def test_get_all_contacts_sorted_by_name(self, db, sample_contacts):
        """NFR: Contacts are returned sorted by name."""
        contacts = db.get_all_contacts(active_only=True)
        names = [c.name for c in contacts]

        # Verify sorted
        assert names == sorted(names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
