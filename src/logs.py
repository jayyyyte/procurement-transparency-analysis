"""Logging setup shared by crawler, cleaning and model training."""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(name: str, logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Log to console and to logs/<name>_<timestamp>.log."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"ptvn.{name}")
    logger.setLevel(level)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(logs_dir / f"{name}_{ts}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.propagate = False
    return logger
