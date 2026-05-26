"""Nuitka build script for Aditya ChartDB.

Usage:
    uv run python scripts/build.py [--sign]

Produces a standalone distributable in dist/
"""

import argparse
import importlib
import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_ephe_dir() -> Path:
    """Find libaditya's ephemeris directory from the installed package."""
    try:
        libaditya = importlib.import_module("libaditya")
        return Path(libaditya.__file__).parent / "ephe"
    except ImportError:
        return Path("NOT_FOUND")


def check_prerequisites():
    errors = []
    ephe = find_ephe_dir()
    if not ephe.exists():
        errors.append(f"libaditya ephemeris data not found (looked at {ephe}) — run: uv sync")
    if not (PROJECT_ROOT / "data" / "charts.db").exists():
        errors.append("data/charts.db not found — run scripts/build-sample-db.py first")

    try:
        subprocess.run([sys.executable, "-m", "nuitka", "--version"],
                       capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        errors.append("nuitka not installed — run: uv sync --group build")

    if errors:
        print("prerequisites not met:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


def build_command() -> list[str]:
    system = platform.system()
    entry = str(PROJECT_ROOT / "aditya-chartdb.py")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        f"--output-filename=aditya-chartdb{'.exe' if system == 'Windows' else ''}",
        f"--output-dir={PROJECT_ROOT / 'dist'}",

        # plugins
        "--enable-plugin=pyside6",

        f"--include-package=chartdb",
        f"--include-package=libaditya",

        # bundle ephemeris data into libaditya's expected location
        f"--include-data-dir={find_ephe_dir()}=libaditya/ephe",

        # bundle sample database
        f"--include-data-files={PROJECT_ROOT / 'data' / 'charts.db'}=data/charts.db",

        # product metadata
        "--product-name=Aditya ChartDB",
        "--product-version=0.1.0",
        "--file-description=Vedic astrology chart database",
        "--copyright=2024-2026",
    ]

    if system == "Windows":
        cmd.extend([
            "--windows-console-mode=disable",
            "--windows-icon-from-ico=assets/icon.ico",
        ])
        # only add icon flag if the file exists
        if not (PROJECT_ROOT / "assets" / "icon.ico").exists():
            cmd = [c for c in cmd if "windows-icon" not in c]

    elif system == "Darwin":
        cmd.extend([
            "--macos-create-app-bundle",
            "--macos-app-name=Aditya ChartDB",
            "--macos-app-version=0.1.0",
        ])
        icon_path = PROJECT_ROOT / "assets" / "icon.icns"
        if icon_path.exists():
            cmd.append(f"--macos-app-icon={icon_path}")

    # the entry point script
    cmd.append(entry)

    return cmd


def main():
    parser = argparse.ArgumentParser(description="Build Aditya ChartDB with Nuitka")
    parser.add_argument("--dry-run", action="store_true", help="print the command without running")
    args = parser.parse_args()

    check_prerequisites()

    cmd = build_command()

    print("build command:", flush=True)
    print("  " + " \\\n    ".join(cmd), flush=True)
    print(flush=True)

    if args.dry_run:
        return

    (PROJECT_ROOT / "dist").mkdir(exist_ok=True)
    print("starting nuitka (this takes several minutes)...", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\nbuild failed (exit {result.returncode})", flush=True)
        sys.exit(result.returncode)

    print("\nbuild complete — output in dist/", flush=True)


if __name__ == "__main__":
    main()
