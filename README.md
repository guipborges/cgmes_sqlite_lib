# cgmes-sqlite-lib

Python library to:

- parse CGMES XML files (EQ/TP and CommonData)
- persist normalized data into relational SQLite
- reload raw datasets per IGM

The scope is intentionally simple: this library handles ingestion and persistence. From the database forward, each user can model queries and downstream processing however they prefer.

## Installation

```bash
pip install cgmes-sqlite-lib
```

## SQLite Setup

No separate SQLite server is required.

- `sqlite3` is included in Python standard library and used automatically by this package.
- In most environments, you do not need to install anything extra.
- Optional: install SQLite CLI tools if you want to inspect `.db` files manually.

Quick check:

```bash
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

Notes:

- The repository enables foreign keys on every connection (`PRAGMA foreign_keys = ON`).
- The database file is created automatically when you instantiate `CgmesSqliteRepository` with a new path.

## Quick Start

```python
from pathlib import Path
from cgmes_sqlite_lib import CgmesParser, CgmesSqliteRepository

parser = CgmesParser()
repo = CgmesSqliteRepository("./cgmes.db")

# 1) common data
common = parser.parse_common_data_file("./CommonAndBoundaryData/Grid_CommonData_CGM-CD.xml")
repo.save_dataset("_CommonData", common)

# 2) one IGM
data = parser.parse_igm("./IGM_Belgovia")
repo.save_dataset("IGM_Belgovia", data)

# 3) reload raw data from SQLite
reloaded = repo.load_dataset("IGM_Belgovia")
print(reloaded.source_folder)
print(reloaded.objects["Substation"][:2])
```

## Project Structure

- `src/cgmes_sqlite_lib/parser.py`: CGMES parser
- `src/cgmes_sqlite_lib/repository.py`: SQLite persistence
- `docs/db.md`: schema documentation and query examples
- `examples/xml`: sample XML files

## Database

The database format is documented in `docs/db.md`.

## Publishing

```bash
python -m pip install -U build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

For a safer first release, publish to TestPyPI before production:

```bash
python -m twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ cgmes-sqlite-lib==0.1.1
```

Detailed release checklist: `RELEASE.md`.

## Running Tests

```bash
python -m pip install -e .[dev]
pytest
```

## License

MIT
