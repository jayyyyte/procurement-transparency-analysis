"""Build the submission zip (source code + readme + config + sample + reports), excluding
raw/interim/processed data, logs, virtualenv and caches.

Usage: python scripts/make_zip.py  ->  dist/procurement-transparency-analysis.zip
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["readme.txt", "README.md", "requirements.txt", "pytest.ini", "run_pipeline.py",
           "config", "src", "scripts", "tests", "docs", "data/sample", "reports"]
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", "_fixture", "_sample"}


def main() -> None:
    out = ROOT / "dist" / "procurement-transparency-analysis.zip"
    out.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUDE:
            p = ROOT / item
            files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
            for f in files:
                if EXCLUDE_PARTS & set(f.relative_to(ROOT).parts) or f.suffix == ".pyc":
                    continue
                z.write(f, Path("procurement-transparency-analysis") / f.relative_to(ROOT))
                n += 1
    print(f"{out} ({n} files, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
