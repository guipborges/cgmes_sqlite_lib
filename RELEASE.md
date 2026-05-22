# Release Checklist

This checklist is for maintainers publishing `cgmes-sqlite-lib`.

## 1. Pre-release checks

```bash
python -m pip install -e .[dev]
pytest
python -m build
python -m twine check dist/*
```

## 2. Tag and version

1. Update `version` in `pyproject.toml`.
2. Commit changes.
3. Create a git tag, for example `v0.1.1`.

## 3. Publish to TestPyPI (recommended)

```bash
python -m twine upload --repository testpypi dist/*
```

Validate install from TestPyPI:

```bash
python -m venv .venv-test
.venv-test\Scripts\python -m pip install -U pip
.venv-test\Scripts\python -m pip install -i https://test.pypi.org/simple/ cgmes-sqlite-lib==0.1.1
.venv-test\Scripts\python -c "from cgmes_sqlite_lib import CgmesParser, CgmesSqliteRepository; print('ok')"
```

## 4. Publish to PyPI

```bash
python -m twine upload dist/*
```

## 5. Post-release checks

1. Verify package page on PyPI.
2. Verify `pip install cgmes-sqlite-lib==<version>` in a clean environment.
3. Optionally create a GitHub release with changelog notes.

## Authentication note

Use a PyPI API token for Twine authentication (`__token__` username). Never commit tokens to source control.
