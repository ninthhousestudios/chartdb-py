# building aditya chartdb

## prerequisites (all platforms)

1. python 3.10–3.13
2. [uv](https://docs.astral.sh/uv/)
3. nuitka: `uv sync --group build`
4. a C compiler (gcc/clang on mac/linux, MSVC on windows via Visual Studio Build Tools)

## step 1: build the sample database

```bash
uv run python scripts/build-sample-db.py /path/to/charts/database --count 100
```

this creates `data/charts.db` with ~100 randomly selected charts.

## step 2: build the app

```bash
uv run python scripts/build.py
```

output lands in `dist/`.

### platform notes

**macOS:**

```bash
uv run python scripts/build.py
```

produces `dist/Aditya ChartDB.app` and `dist/aditya-chartdb` (standalone executable). sign and notarize separately — nuitka's built-in signing is unreliable. to make a dmg:

```bash
codesign --deep --force --sign "Developer ID Application: ..." dist/aditya-chartdb
hdiutil create -volname "Aditya ChartDB" -srcfolder dist/aditya-chartdb -ov -format UDZO dist/aditya-chartdb.dmg
xcrun notarytool submit dist/aditya-chartdb.dmg --apple-id ... --team-id ... --password ...
```

**windows:**

install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-studio-cpp-build-tools/) with "Desktop development with C++" workload.

```powershell
uv run python scripts/build.py
```

produces `dist/aditya-chartdb.exe`. users may see a SmartScreen warning on first run — click "More info" → "Run anyway".

**linux:**

```bash
uv run python scripts/build.py
```

produces `dist/aditya-chartdb`.

## adding an icon

- macOS: place `assets/icon.icns` (1024×1024 recommended)
- windows: place `assets/icon.ico` (256×256 multi-resolution)

the build script picks these up automatically if present.

## troubleshooting

- **"ModuleNotFoundError: libaditya"** — make sure libaditya is at `../libaditya` and `uv sync` has been run
- **ephemeris files missing at runtime** — the build bundles `libaditya/ephe/` automatically; check nuitka output for include warnings
- **PySide6 plugin errors** — ensure nuitka is up to date: `uv add --dev nuitka --upgrade`
- **large binary size** — PySide6/Qt accounts for most of it (~100-150 MB). `--onefile` compresses it but startup is slightly slower on first run.
