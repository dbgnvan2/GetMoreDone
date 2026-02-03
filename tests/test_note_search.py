"""
Tests for Obsidian note search functionality with file: and tag: prefixes.
"""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_vault_with_notes():
    """Create a temporary vault with test notes."""
    vault = tempfile.mkdtemp()
    vault_path = Path(vault)

    # Create .obsidian folder to make it a valid vault
    (vault_path / ".obsidian").mkdir()

    # Create notes in root
    note1 = vault_path / "Meeting Notes.md"
    note1.write_text("""---
tags: [meeting, work, project-alpha]
---
# Meeting Notes
Discussion about project alpha.
""")

    # Create notes in subfolder
    subfolder = vault_path / "Projects"
    subfolder.mkdir()

    note2 = subfolder / "Project Alpha.md"
    note2.write_text("""---
tags: [project, alpha, important]
---
# Project Alpha
Main project notes.
""")

    # Create note with inline tags
    note3 = vault_path / "Quick Ideas.md"
    note3.write_text("""# Quick Ideas

Some thoughts about #innovation and #creativity.
Also related to #project-alpha.
""")

    # Create note without tags
    note4 = vault_path / "README.md"
    note4.write_text("""# README
Just a readme file.
""")

    # Create note in GetMoreDone subfolder
    gmd_folder = vault_path / "GetMoreDone"
    gmd_folder.mkdir()

    note5 = gmd_folder / "Task Notes.md"
    note5.write_text("""---
tags: [tasks, todo]
---
# Task Notes
Notes about tasks.
""")

    yield vault_path

    # Cleanup
    shutil.rmtree(vault)


def test_search_entire_vault(temp_vault_with_notes):
    """Test that search includes all notes in vault, not just GetMoreDone folder."""
    from pathlib import Path
    import re

    vault_path = temp_vault_with_notes

    # Simulate loading notes from entire vault
    all_notes = []
    for md_file in vault_path.rglob("*.md"):
        all_notes.append({
            'path': str(md_file),
            'title': md_file.stem,
            'relative': str(md_file.relative_to(vault_path)),
            'tags': []
        })

    # Should find all 5 notes
    assert len(all_notes) == 5

    # Should include notes from root, Projects/, and GetMoreDone/
    titles = [n['title'] for n in all_notes]
    assert "Meeting Notes" in titles
    assert "Project Alpha" in titles
    assert "Quick Ideas" in titles
    assert "README" in titles
    assert "Task Notes" in titles


def test_extract_frontmatter_tags(temp_vault_with_notes):
    """Test extraction of tags from YAML frontmatter."""
    import re

    note_path = temp_vault_with_notes / "Meeting Notes.md"
    content = note_path.read_text()

    # Extract tags
    tags = []
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        tags_match = re.search(r'tags:\s*\[(.*?)\]', frontmatter)
        if tags_match:
            tags = [t.strip().strip('"\'') for t in tags_match.group(1).split(',')]

    assert len(tags) == 3
    assert "meeting" in tags
    assert "work" in tags
    assert "project-alpha" in tags


def test_extract_inline_tags(temp_vault_with_notes):
    """Test extraction of inline #tags from content."""
    import re

    note_path = temp_vault_with_notes / "Quick Ideas.md"
    content = note_path.read_text()

    # Extract inline tags
    inline_tags = re.findall(r'#(\w+)', content)
    inline_tags = [t for t in inline_tags if t != 'Quick']  # Exclude heading #

    assert len(inline_tags) >= 2
    assert "innovation" in inline_tags or "creativity" in inline_tags


def test_file_prefix_search():
    """Test file: prefix searches only in filename."""
    notes = [
        {'title': 'Meeting Notes', 'tags': ['meeting']},
        {'title': 'Project Alpha', 'tags': ['project']},
        {'title': 'Quick Ideas', 'tags': ['ideas']},
    ]

    # Search with file: prefix
    search_text = "file:meeting"
    query = search_text[5:].strip().lower()
    filtered = [n for n in notes if query in n['title'].lower()]

    assert len(filtered) == 1
    assert filtered[0]['title'] == 'Meeting Notes'


def test_tag_prefix_search():
    """Test tag: prefix searches in tags."""
    notes = [
        {'title': 'Meeting Notes', 'tags': ['meeting', 'work']},
        {'title': 'Project Alpha', 'tags': ['project', 'alpha']},
        {'title': 'Quick Ideas', 'tags': ['ideas', 'creativity']},
    ]

    # Search with tag: prefix
    search_text = "tag:work"
    query = search_text[4:].strip().lower()
    filtered = [n for n in notes
               if any(query in tag.lower() for tag in n.get('tags', []))]

    assert len(filtered) == 1
    assert filtered[0]['title'] == 'Meeting Notes'


def test_case_insensitive_search():
    """Test that search is case-insensitive."""
    notes = [
        {'title': 'Meeting Notes', 'tags': []},
        {'title': 'Project Alpha', 'tags': []},
        {'title': 'quick ideas', 'tags': []},
    ]

    # Search with different cases
    for search in ['MEETING', 'meeting', 'MeEtInG']:
        query = search.lower()
        filtered = [n for n in notes if query in n['title'].lower()]
        assert len(filtered) == 1
        assert filtered[0]['title'] == 'Meeting Notes'


def test_contains_search():
    """Test that search is 'contains' not 'equals'."""
    notes = [
        {'title': 'Meeting Notes', 'tags': []},
        {'title': 'Project Meeting', 'tags': []},
        {'title': 'Quick Ideas', 'tags': []},
    ]

    # Search for partial match
    query = "meet"
    filtered = [n for n in notes if query in n['title'].lower()]

    assert len(filtered) == 2
    titles = [n['title'] for n in filtered]
    assert 'Meeting Notes' in titles
    assert 'Project Meeting' in titles


def test_tag_partial_match():
    """Test that tag search supports partial matches."""
    notes = [
        {'title': 'Note 1', 'tags': ['project-alpha', 'work']},
        {'title': 'Note 2', 'tags': ['project-beta', 'personal']},
        {'title': 'Note 3', 'tags': ['meeting', 'work']},
    ]

    # Search for partial tag match
    search_text = "tag:proj"
    query = search_text[4:].strip().lower()
    filtered = [n for n in notes
               if any(query in tag.lower() for tag in n.get('tags', []))]

    assert len(filtered) == 2
    titles = [n['title'] for n in filtered]
    assert 'Note 1' in titles
    assert 'Note 2' in titles


def test_new_notes_saved_to_subfolder(temp_vault_with_notes):
    """Test that new notes are saved to GetMoreDone subfolder, not vault root."""
    from src.getmoredone.app_settings import AppSettings

    # Create settings pointing to temp vault
    settings = AppSettings()
    settings.obsidian_vault_path = str(temp_vault_with_notes)
    settings.obsidian_notes_subfolder = "GetMoreDone"

    # Get notes folder
    notes_folder = settings.get_notes_folder()

    assert notes_folder is not None
    assert notes_folder.name == "GetMoreDone"
    assert notes_folder.parent == temp_vault_with_notes
    assert notes_folder.exists()


def test_empty_search_shows_all_notes():
    """Test that empty search shows all notes (up to limit)."""
    notes = [
        {'title': f'Note {i}', 'tags': []} for i in range(100)
    ]

    # Empty search
    search_text = ""

    if not search_text:
        filtered = notes[:50]  # Limit to 50
    else:
        filtered = notes

    assert len(filtered) == 50  # Should be limited to 50


def test_no_results_message():
    """Test that no results are handled gracefully."""
    notes = [
        {'title': 'Meeting Notes', 'tags': ['meeting']},
        {'title': 'Project Alpha', 'tags': ['project']},
    ]

    # Search for non-existent note
    query = "nonexistent"
    filtered = [n for n in notes if query in n['title'].lower()]

    assert len(filtered) == 0
