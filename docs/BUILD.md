# BUILD.md — Build System Technical Reference

Internal document for the FocusLock build pipeline using Nuitka.

---

## Architecture

```
scripts/
├── version.py     # Single source of truth for version
├── build.py       # Nuitka compilation orchestrator
├── clean.py       # Build artifact cleanup
└── release.py     # Release packaging + zip creation
```

Each script is standalone and imports `version.py` for the canonical version string.

---

## Build Flow

```
scripts/build.py
  │
  ├── Detect compiler (MSVC / MinGW64 / none)
  │
  ├── Invoke Nuitka with:
  │   ├── --standalone           (folder output, not onefile)
  │   ├── --enable-plugin=pyside6
  │   ├── --windows-console-mode=disable
  │   ├── --lto=yes              (release only)
  │   ├── --nofollow-import-to   (exclude heavy unused modules)
  │   ├── --include-data-dir     (assets)
  │   └── --windows-file-version (metadata)
  │
  └── Output → build/nuitka_output/<entry>.dir/
                    └── FocusLock.exe + _internal/

scripts/release.py
  │
  ├── Locate build output
  ├── Copy to dist/FocusLock-3.0.0/
  ├── Add Install.bat, Uninstall.bat, README.txt, LICENSE, CHANGELOG.md
  └── Optionally create dist/FocusLock-3.0.0.zip
```

---

## Nuitka Configuration

### Mode: `--standalone`

Nuitka compiles Python to C, then to machine code via a C compiler.
`--standalone` produces a directory with the executable and all dependencies.

### Plugin: `--enable-plugin=pyside6`

Handles Qt plugin discovery, translation files, and PySide6 runtime dependencies.
Without this, the app will fail to find Qt platform plugins at runtime.

### Compiler: MinGW64 (auto-downloaded)

Nuitka auto-downloads MinGW64 from winlibs.com on first run if no compiler is detected.
This is cached in the Nuitka cache directory. No manual compiler installation required.

### Optimization: `--lto=yes`

Link-Time Optimization across the entire compiled output.
Reduces binary size and improves runtime performance by ~5-15%.
Only used in release builds.

### Excluded Modules

| Module | Reason |
|--------|--------|
| tkinter | Not used (PySide6 is the UI) |
| matplotlib, numpy, pandas | Not used |
| pytest, unittest | Test frameworks |
| xmlrpc, pydoc, doctest | Not used at runtime |
| lib2to3 | Python 2/3 compat (not needed) |

### Windows Version Metadata

Applied via Nuitka flags in release mode:

```
--windows-file-version=3,0,0,0
--windows-product-version=3.0.0
--windows-company-name=zadwen
--windows-product-name=FocusLock
--windows-file-description=Focus and productivity app
--windowscopyright=Copyright (c) 2026 zadwen
--windows-icon-from-ico=assets/icon.ico
```

These embed into the exe's VERSIONINFO resource, visible in Windows Properties.

---

## Output Structure

### Raw Nuitka output (build/nuitka_output/)

```
build/nuitka_output/focuslock_app.dir/
├── FocusLock.exe                 # Compiled executable
├── _internal/
│   ├── python312.dll             # Python runtime
│   ├── PySide6/                  # Qt libraries + plugins
│   │   ├── QtCore.dll
│   │   ├── QtGui.dll
│   │   ├── QtWidgets.dll
│   │   ├── plugins/
│   │   │   ├── platforms/
│   │   │   ├── styles/
│   │   │   └── ...
│   │   └── translations/
│   ├── sqlalchemy/               # ORM
│   ├── psutil/                   # Process management
│   ├── greenlet/                 # SQLAlchemy dependency
│   ├── assets/                   # Bundled app assets
│   └── ... (other runtime deps)
```

### Release package (dist/FocusLock-3.0.0/)

```
FocusLock-3.0.0/
├── FocusLock.exe                 # <-- User sees this first
├── _internal/                    # Runtime dependencies
├── README.txt                    # End-user instructions
├── LICENSE                       # MIT license
├── CHANGELOG.md                  # Version history
├── Install.bat                   # Creates Desktop shortcut
└── Uninstall.bat                 # Removes Desktop shortcut
```

---

## Compiler Requirements

| Compiler | Source | Notes |
|----------|--------|-------|
| MinGW64 | Auto-downloaded by Nuitka | Default on Windows. Cached after first download. |
| MSVC Build Tools | Manual install | Requires Visual Studio Build Tools. More stable for CI. |

For CI/CD, MSVC is preferred for reproducibility. For local dev, MinGW64 auto-download works.

---

## Version Management

`scripts/version.py` is the single source of truth.

```bash
python scripts/version.py                    # Print current version
python scripts/version.py --bump patch       # 3.0.0 -> 3.0.1
python scripts/version.py --bump minor       # 3.0.0 -> 3.1.0
python scripts/version.py --bump major       # 3.0.0 -> 4.0.0
```

Updates both `scripts/version.py` and `src/focuslock/constants.py` atomically.

---

## Build Commands

```bash
# Development build (fast, minimal optimization)
python scripts/build.py --development

# Release build (LTO, metadata, icon)
python scripts/build.py --release

# Debug build (symbols, debug info)
python scripts/build.py --debug

# Clean all build artifacts
python scripts/clean.py
python scripts/clean.py --all    # Also clean __pycache__

# Package for release
python scripts/release.py
python scripts/release.py --zip  # Also create zip archive
python scripts/release.py --verify  # Check build exists
```

---

## CI/CD (GitHub Actions)

**Trigger:** Push tag `v*` or manual dispatch.

**Steps:**
1. Checkout code
2. Setup Python 3.12 with pip cache
3. Install runtime + build dependencies
4. Install Nuitka
5. Read version from `scripts/version.py`
6. Build with Nuitka (release mode)
7. Package with release.py
8. Upload artifacts (folder + zip)
9. Create GitHub Release (on tag push)

**Artifacts:**
- `FocusLock-<version>-Windows` — full distribution folder
- `FocusLock-<version>-zip` — compressed archive

---

## Installer (Inno Setup)

**File:** `installer/focuslock.iss`

Requires [Inno Setup 6.x](https://jrsoftware.org/isinfo.php).

```bash
# Build the release first
python scripts/build.py --release
python scripts/release.py

# Then compile the installer
iscc installer/focuslock.iss
```

Output: `dist/FocusLock-3.0.0-Setup.exe`

Features:
- Per-user install (no admin required)
- Desktop shortcut option
- Start Menu group
- Clean uninstaller
- LZMA2 compression

---

## Differences from PyInstaller

| Aspect | PyInstaller | Nuitka |
|--------|-------------|--------|
| Compilation | Packages Python bytecode | Compiles Python to C to machine code |
| Performance | Interpreted at runtime | Native compiled (5-15% faster) |
| Startup | Extracts to temp dir (onefile) or uses bundled Python | Direct execution |
| Detection | Antivirus often flags | Lower false positive rate |
| Plugins | Manual hook specification | `--enable-plugin=pyside6` handles Qt automatically |
| Output | .exe only | .exe + `_internal/` folder |
| Binary size | ~7 MB exe + ~111 MB internal | Varies (typically similar or smaller) |
| Build time | ~35 seconds | 2-10 minutes (compilation overhead) |
