"""Load config/config.yaml, resolve paths and the crawl date window."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"


@dataclass
class Config:
    data: dict[str, Any]
    root: Path = PROJECT_ROOT

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def path(self, key: str) -> Path:
        """Absolute path for an entry under `paths:`."""
        return (self.root / self.data["paths"][key]).resolve()

    def with_paths(self, **overrides: str) -> "Config":
        """Copy with some `paths:` entries replaced (used by --sample / --fixture runs)."""
        data = copy.deepcopy(self.data)
        data["paths"].update(overrides)
        return Config(data, self.root)


def load_config(path: str | Path | None = None) -> Config:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return Config(yaml.safe_load(f))


def subtract_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + (d.month - 1) - months, 12)
    m += 1
    # clamp day (e.g. 31 -> 30/28)
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def crawl_window(cfg: Config, today: date | None = None) -> tuple[date, date]:
    """(start, end) of the crawl window; default = `months_back` months ending today."""
    c = cfg["crawl"]
    end = date.fromisoformat(c["end_date"]) if c.get("end_date") else (today or date.today())
    if c.get("start_date"):
        start = date.fromisoformat(c["start_date"])
    else:
        start = subtract_months(end, int(c["months_back"]))
    if start > end:
        raise ValueError(f"start_date {start} > end_date {end}")
    return start, end
