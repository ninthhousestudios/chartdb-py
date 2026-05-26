"""Entry point for Nuitka builds — launches the GUI."""

import os
import shutil
import sys
from pathlib import Path


def get_data_dir() -> Path:
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "Aditya ChartDB"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        d = Path(base) / "Aditya ChartDB"
    else:
        d = Path.home() / ".local" / "share" / "aditya-chartdb"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_bundled_dir() -> Path:
    if "__compiled__" in dir():
        return Path(sys.argv[0]).resolve().parent / "data"
    return Path(__file__).resolve().parent / "data"


def ensure_db(data_dir: Path) -> Path:
    db_path = data_dir / "charts.db"
    if db_path.exists():
        return db_path

    bundled_db = get_bundled_dir() / "charts.db"
    if bundled_db.exists():
        shutil.copy2(bundled_db, db_path)
    return db_path


def main():
    data_dir = get_data_dir()
    db_path = ensure_db(data_dir)

    from chartdb.gui import run_gui
    run_gui(str(db_path))


if __name__ == "__main__":
    main()
