"""Create deterministic asset names and SHA-256 checksums for release downloads."""
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
release = ROOT / "release"
release.mkdir(exist_ok=True)
windows = sys.platform == "win32"
name = "FocusLock.exe" if windows else "FocusLock-linux-x86_64"
shutil.copy2(ROOT / "dist" / name, release / name)
assets = [release / name]
if not windows:
    archive = release / "FocusLock-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for folder in ("src", "scripts", "assets", "tests", "docs", ".github"):
            for p in sorted((ROOT / folder).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, Path("FocusLock") / p.relative_to(ROOT))
        for name in ("README.md", "LICENSE", "CHANGELOG.md", "build.bat", "build.sh", "requirements.txt", "requirements-build.txt", ".gitignore", ".gitattributes"):
            z.write(ROOT / name, "FocusLock/" + name)
    assets.append(archive)
checksum = release / ("SHA256SUMS-Windows.txt" if windows else "SHA256SUMS-Linux.txt")
checksum.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in assets))
print("Packaged:", ", ".join(p.name for p in assets))
