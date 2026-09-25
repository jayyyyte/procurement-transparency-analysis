"""Raw layer: every API response is kept as gzip JSONL so parsing can be redone without re-crawling."""
from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


class RawStore:
    """Append raw responses to data/raw/<source>/<run_ts>/batch_<n>.jsonl.gz."""

    def __init__(self, raw_dir: Path, source: str, batch_size: int = 500):
        self.run_dir = raw_dir / source / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.source = source
        self.batch_size = batch_size
        self._batch = 0
        self._n_in_batch = 0
        self._fh: gzip.GzipFile | None = None

    def write(self, kind: str, url: str, request: Any, status: int, payload: Any) -> None:
        if self._fh is None or self._n_in_batch >= self.batch_size:
            self._rotate()
        line = {
            "source": self.source,
            "kind": kind,                  # "list" | "detail"
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "url": url,
            "request": request,
            "status": status,
            "payload": payload,
        }
        self._fh.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
        self._n_in_batch += 1

    def _rotate(self) -> None:
        self.close()
        self._batch += 1
        self._n_in_batch = 0
        self._fh = gzip.open(self.run_dir / f"batch_{self._batch:05d}.jsonl.gz", "ab")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def iter_raw(raw_dir: Path, source: str) -> Iterator[dict]:
    """Yield every raw line for a source, oldest run first."""
    for path in sorted((raw_dir / source).glob("*/batch_*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
