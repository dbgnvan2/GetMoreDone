# Dev vs Prod workflow (GetMoreDone)

Goal:
- Keep a **dev** instance you run from the repo and update freely
- Have a **prod** instance that behaves like a normal install (shareable app)

## DB selection

GetMoreDone chooses its SQLite database in this order:
1) Explicit db path passed by the caller (rare)
2) Environment variable: `GETMOREDONE_DB`
3) Default (production):
   `~/Library/Application Support/GetMoreDone/getmoredone.db`

## Recommended setup

### Dev (repo)

Use the repo-local database:
- `/Users/davemini2/ProjectsLocal/GetMoreDone/data/getmoredone.db`

`start.sh` and `start.bat` default to this DB automatically unless you override `GETMOREDONE_DB`.

### Prod (installed)

Use the Application Support database:
- `~/Library/Application Support/GetMoreDone/getmoredone.db`

Do **not** set `GETMOREDONE_DB` for the prod app.

## Gmail importer

The Gmail importer uses the same DB selection rule.

- Dev importer: set `GETMOREDONE_DB` to the repo-local DB (or pass `--db`)
- Prod importer: do not set `GETMOREDONE_DB` (it will write into Application Support)
