"""Build a sample charts.db from a random selection of .chtk files.

Usage:
    uv run python scripts/build-sample-db.py /path/to/charts/database [--count 100]

Writes data/charts.db (bundled with the app).
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chartdb.db import ChartDB


def main():
    parser = argparse.ArgumentParser(description="Build sample charts.db for distribution")
    parser.add_argument("source", help="directory containing .chtk files (searched recursively)")
    parser.add_argument("--count", type=int, default=100, help="number of charts to include")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    parser.add_argument("--output", default=None, help="output path (default: data/charts.db)")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        print(f"error: {source} is not a directory")
        sys.exit(1)

    all_chtk = sorted(source.rglob("*.chtk"))
    print(f"found {len(all_chtk)} .chtk files in {source}")

    if len(all_chtk) <= args.count:
        selected = all_chtk
    else:
        rng = random.Random(args.seed)
        selected = rng.sample(all_chtk, args.count)

    output = Path(args.output) if args.output else Path(__file__).resolve().parent.parent / "data" / "charts.db"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    db = ChartDB(str(output))
    imported = 0
    failed = 0
    for chtk in sorted(selected):
        try:
            category = chtk.parent.name
            db.import_chtk(chtk, tags=[category])
            imported += 1
        except Exception as e:
            print(f"  skip: {chtk.name}: {e}")
            failed += 1

    db.close()
    print(f"\nimported {imported} charts ({failed} failed) -> {output}")
    print(f"size: {output.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
