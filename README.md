# Aditya ChartDB

A vedic astrology chart database with full-text search, composable property filters, and vector similarity search. Built on SQLite and [libaditya](https://gitlab.com/ninthhouse/libaditya).

## Getting started (Windows & macOS)

Download the latest build for your platform from the releases page.

**macOS:** Open the `.dmg`, drag `Aditya ChartDB` to Applications. On first launch, macOS may ask you to confirm — click Open.

**Windows:** Run `aditya-chartdb.exe`. Windows SmartScreen may show a warning on first run — click "More info" then "Run anyway".

The app ships with a sample database of ~100 charts. To add your own, click the **Import** button (upper right) and select a folder of `.chtk` files (Kala export format). Your data is stored in your user folder and persists across updates.

### Search

Type in the search bar to find charts by name, place, country, or notes.

### Property filters

Click "+ Add Filter" to add filter rows. Each row is a chain of dropdowns: Subject (planet or Lagna) > Property > Value. Multiple filters are AND-composed — adding more rows narrows the results. Available properties:

- Sign, House, Nakshatra, Dignity, Retrograde
- Avasthas: Baladi, Jagradadi, Deeptadi, Shayanadi
- Lajjitaadi (with optional "by planet" and mechanism sub-filters)
- Trimsamsa Being (Gandharva, Rakshasa, Rishi, Yaksha, Apsara)
- Trimsamsa Lord

For lajjitaadi filters, selecting an avastha (e.g. "Starved") reveals a 4th dropdown to pick the causing planet, and then a 5th dropdown for the mechanism: conjunction, sign, aspect<30, or aspect>=30. Each level is optional.

### Similar charts

Select a chart from the list, then click "Find Similar (all)" to rank all charts by vector similarity, or "Find Similar (with filters)" to first narrow by your active property filters and then rank by similarity.

**Interpreting distances:** The similarity column shows cosine distance — 0.0 is identical, 1.0 is no correlation. In practice, the most similar charts fall in the 0.01–0.3 range. The relative ranking matters more than the absolute number.

### Where is my data?

Your chart database is stored at:

- **macOS:** `~/Library/Application Support/Aditya ChartDB/charts.db`
- **Windows:** `%APPDATA%\Aditya ChartDB\charts.db`
- **Linux:** `~/.local/share/aditya-chartdb/charts.db`

---

## Development

### Setup

Requires Python 3.10–3.13 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://gitlab.com/ninthhouse/chartdb-py
cd chartdb-py
uv sync
```

libaditya is pulled automatically from GitLab. For local development against a local checkout, change `pyproject.toml`:

```toml
[tool.uv.sources]
libaditya = { path = "../libaditya", editable = true }
```

### CLI

```bash
uv run python -m chartdb gui                                     # launch GUI
uv run python -m chartdb import /path/to/charts/                 # import .chtk directory
uv run python -m chartdb import chart.chtk --tag famous          # import single file with tag
uv run python -m chartdb list                                    # list all charts
uv run python -m chartdb search "london"                         # full-text search
uv run python -m chartdb similar "Alan Turing"                   # find similar charts
uv run python -m chartdb filter Sun.sign_name=Aries Moon.house=4 # property filters
uv run python -m chartdb rebuild                                 # recompute vectors & properties
```

### Building distributable binaries

Builds use [Nuitka](https://nuitka.net/) to produce standalone executables. You must build on the target platform (no cross-compilation).

**Prerequisites:** a C compiler (Xcode CLT on macOS, Visual Studio Build Tools on Windows, gcc on Linux).

```bash
uv sync --group build

# build the sample database (ships with the app)
uv run python scripts/build-sample-db.py /path/to/charts/database --count 100

# build the app
uv run python scripts/build.py            # build
uv run python scripts/build.py --dry-run  # print the nuitka command without running
```

See `scripts/build-readme.md` for platform-specific notes, icon setup, and troubleshooting.

### Architecture

- `chartdb/db.py` — `ChartDB` class: SQLite with WAL, FTS5, EAV properties, vector storage
- `chartdb/vectors.py` — Configurable vector schema and extraction (sin/cos encoding)
- `chartdb/properties.py` — Categorical property extraction (sign, house, nakshatra, dignity, avasthas, trimsamsa)
- `chartdb/gui.py` — PySide6 GUI
- `chartdb/__main__.py` — CLI entry point
- `aditya-chartdb.py` — GUI-only entry point for Nuitka builds

### Vector schema

The similarity vector encodes 87 dimensions (ecliptic longitudes, house cusps, house placements, nakshatras, retrograde flags) using sin/cos encoding for circular topology. The schema is content-hashed — changing it requires `rebuild`.
