"""Vietnamese text helpers: accent stripping and key normalisation."""
from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")


def strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_key(s: object) -> str:
    """Lowercase, accent-free, single-spaced — for matching names/keywords."""
    if s is None:
        return ""
    s = strip_accents(str(s)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _SPACES.sub(" ", s).strip()
