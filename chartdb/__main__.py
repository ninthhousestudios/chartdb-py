"""CLI entry point: python -m chartdb"""

import argparse
import sys
from pathlib import Path

from .db import ChartDB
from .vectors import DEFAULT_SCHEMA


def main():
    parser = argparse.ArgumentParser(description="ChartDB — vedic chart database with similarity search")
    parser.add_argument("--db", default="charts.db", help="path to sqlite database")
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="import .chtk files")
    imp.add_argument("path", help="file or directory to import")
    imp.add_argument("--tag", action="append", default=[], help="tag(s) to apply")

    sub.add_parser("list", help="list all charts")

    search_p = sub.add_parser("search", help="full-text search")
    search_p.add_argument("query", help="search query")

    sim = sub.add_parser("similar", help="find similar charts")
    sim.add_argument("name", help="chart name (partial match)")
    sim.add_argument("-n", type=int, default=10, help="number of results")

    filt = sub.add_parser("filter", help="filter charts by properties")
    filt.add_argument("filters", nargs="+", help="filters as subject.property=value (e.g. Sun.sign_name=indra)")

    sub.add_parser("rebuild", help="rebuild vectors and properties")

    sub.add_parser("gui", help="launch the GUI")

    args = parser.parse_args()

    if args.command == "gui":
        from .gui import run_gui
        run_gui(args.db)
        return

    db = ChartDB(args.db)

    if args.command == "import":
        p = Path(args.path)
        if p.is_dir():
            ids = db.import_directory(p, tags=args.tag or None)
            print(f"imported {len(ids)} charts")
        elif p.suffix == ".chtk":
            cid = db.import_chtk(p, tags=args.tag or None)
            print(f"imported: {cid}")
        else:
            print(f"unsupported file: {p}")
            sys.exit(1)

    elif args.command == "list":
        for c in db.list_charts():
            print(f"  {c['name']:30s}  {c.get('placename') or '':20s}  jd={c['jd']:.4f}")

    elif args.command == "search":
        results = db.search(args.query)
        if not results:
            print("no results")
        for c in results:
            print(f"  {c['name']:30s}  {c.get('placename') or ''}")

    elif args.command == "similar":
        # find chart by name substring
        charts = db.list_charts()
        match = [c for c in charts if args.name.lower() in (c["name"] or "").lower()]
        if not match:
            print(f"no chart matching '{args.name}'")
            sys.exit(1)
        target = match[0]
        print(f"similar to: {target['name']}")
        results = db.similar(target["id"], n=args.n)
        for chart, dist in results:
            print(f"  {dist:.4f}  {chart['name']:30s}  {chart.get('placename') or ''}")

    elif args.command == "filter":
        filters = []
        for f in args.filters:
            left, value = f.split("=", 1)
            subject, prop = left.split(".", 1)
            filters.append((subject, prop, value))
        results = db.filter_by_properties(filters)
        if not results:
            print("no results")
        for c in results:
            print(f"  {c['name']:30s}  {c.get('placename') or ''}")
        print(f"\n{len(results)} charts")

    elif args.command == "rebuild":
        db.rebuild_all()
        print("vectors and properties rebuilt")

    else:
        parser.print_help()

    db.close()


if __name__ == "__main__":
    main()
