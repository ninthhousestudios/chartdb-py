# chartdb — agent instructions

## Project

Vedic astrology chart database with SQLite backend, FTS5 search, EAV property filters, and cosine-similarity vector search. PySide6 GUI. Depends on [libaditya](https://gitlab.com/ninthhouse/libaditya).

## Commands

```bash
uv sync                                    # install deps
uv run python -m chartdb gui               # launch GUI
uv run python -m chartdb rebuild            # recompute vectors + properties after schema changes
uv run python -m chartdb import <path>      # import .chtk files
uv run python -m chartdb filter Sun.sign_name=Aries Moon.trimsamsa_being=Gandharva
```

## Architecture

- `db.py` — `ChartDB`: SQLite with WAL, FTS5, vector blobs, EAV properties. All queries here.
- `vectors.py` — `VectorSchema` dataclass, `extract_vector()`. Sin/cos encoding for circular values.
- `properties.py` — `extract_properties()` returns `(subject, property, value)` triples. Add new categorical properties here.
- `gui.py` — PySide6 GUI. `FilterRow` handles the cascading dropdowns. `ChartDBWindow` is the main window.
- `__main__.py` — CLI dispatcher.

## Key patterns

- Properties are EAV: `(chart_id, subject, property, value)`. Filters compose via SQL intersection.
- Lajjitaadi has compound property values: `lajjitaadi_by` stores `avastha:planet`, `lajjitaadi_via` stores `avastha:planet:mechanism`.
- Vectors use sin/cos encoding for all angular values (respects circular topology). Schema is content-hashed; changing it requires `rebuild`.
- libaditya's `planet.attributes` dict is the source for avasthas and dignity. Lajjitaadi sources use `planet` key for conjunction/aspect, `lord` key for sign placement.

## Adding a new property

1. Add extraction logic in `properties.py` `extract_properties()`.
2. Add the `(db_name, display_name)` tuple to `PROPERTIES` in `gui.py`.
3. Run `rebuild` to recompute for existing charts.

## Build

- `aditya-chartdb.py` — top-level entry point for Nuitka builds (GUI-only launcher).
- `scripts/build.py` — Nuitka build script, platform-aware (macOS .app bundle + signing, Windows no-console).
- `scripts/build-sample-db.py` — builds `data/charts.db` from a random sample of .chtk files.
- `data/charts.db` — bundled sample database shipped with builds.

## Dependencies

- `libaditya` is pulled from GitLab (`https://gitlab.com/ninthhouse/libaditya`) via uv.
- For local dev against a local libaditya checkout, override in pyproject.toml: `libaditya = { path = "../libaditya", editable = true }`
- Use `uv`, not pip.
