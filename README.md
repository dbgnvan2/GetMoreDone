# GetMoreDone

A Python task management application with a GUI interface and SQLite database.

## Setup

1. Create and activate the virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure

```
GetMoreDone/
├── src/
│   └── getmoredone/    # Main application package
├── tests/              # Test files
├── data/               # Database files (gitignored)
├── docs/               # Documentation
└── requirements.txt    # Python dependencies
```

## Development

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=src/getmoredone
```

## Technologies

- Python 3.11+
- SQLite (built-in)
- CustomTkinter (GUI)
- pytest (testing)
