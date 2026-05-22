# chartdb

A vedic astrology chart database with full-text search, composable property filters, and vector similarity search. Built on SQLite and [libaditya](../libaditya).

## Setup

chartdb depends on `libaditya`, which must be cloned as a sibling directory:

```
astrology/
  libaditya/     # git clone of libaditya
  chartdb-py/    # this repo
```

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

This resolves libaditya from `../libaditya` as an editable path dependency.

## Usage

### Import charts

Import `.chtk` files (Kala software export format):

```bash
uv run python -m chartdb import /path/to/charts/       # directory of .chtk files
uv run python -m chartdb import chart.chtk              # single file
uv run python -m chartdb import /path/to/charts/ --tag famous --tag rectified
```

### CLI commands

```bash
uv run python -m chartdb list                                    # list all charts
uv run python -m chartdb search "london"                         # full-text search
uv run python -m chartdb similar "Alan Turing"                   # find similar charts
uv run python -m chartdb filter Sun.sign_name=Aries Moon.house=4 # property filters
uv run python -m chartdb rebuild                                 # recompute vectors & properties
```

### GUI

```bash
uv run python -m chartdb gui
```

The GUI has three main areas:

**Search bar** — Full-text search across chart name, place, country, and notes.

**Property filters** — Click "+ Add Filter" to add filter rows. Each row is a chain of dropdowns: Subject (planet or Lagna) > Property > Value. Filters are AND-composed, so adding multiple rows narrows the results. Available properties:

- Sign, House, Nakshatra, Dignity, Retrograde
- Avasthas: Baladi, Jagradadi, Deeptadi, Shayanadi
- Lajjitaadi (with optional "by planet" and mechanism sub-filters)
- Trimsamsa Being (Gandharva, Rakshasa, Rishi, Yaksha, Apsara)
- Trimsamsa Lord

For lajjitaadi filters, selecting an avastha (e.g. "Starved") reveals a 4th dropdown to pick the causing planet, and then a 5th dropdown to pick the mechanism: conjunction, sign, aspect<30, or aspect>=30. Each level is optional — you can filter at any granularity.

**Similar charts** — Select a chart from the list, then click "Find Similar (all)" to rank all charts by vector similarity, or "Find Similar (with filters)" to first narrow by your active property filters and then rank by similarity.

### Interpreting similarity distances

The similarity column shows cosine distance:

- **0.0** — identical planetary positions
- **1.0** — no correlation
- **2.0** — perfectly opposite

In practice, the most similar charts will typically fall in the **0.01–0.3** range. The absolute numbers are less meaningful than the relative ranking — a chart at 0.05 is more similar than one at 0.12.

The vector encodes 87 dimensions (ecliptic longitudes, house cusps, house placements, nakshatras, retrograde flags) using sin/cos encoding for circular topology. A small distance means charts agree across many features simultaneously. For understanding *which* features match, use property filters first to lock in the categorical features you care about, then let similarity rank the remaining candidates.

### Vector schema

The similarity vector is configurable via `VectorSchema`. The default schema ("vedic-9") encodes all 9 grahas across longitudes, house cusps, house placements, nakshatras, and retrogrades. To change what goes into the vector, modify the schema and run `rebuild`.

## Architecture

- `chartdb/db.py` — `ChartDB` class: SQLite with WAL, FTS5, EAV properties, vector storage
- `chartdb/vectors.py` — Configurable vector schema and extraction
- `chartdb/properties.py` — Categorical property extraction (sign, house, nakshatra, dignity, avasthas, trimsamsa)
- `chartdb/gui.py` — PySide6 GUI
- `chartdb/__main__.py` — CLI entry point
