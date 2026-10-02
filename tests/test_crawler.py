import logging
from datetime import date

import pytest

import run_pipeline
from src.crawler.checkpoint import Checkpoint
from src.crawler.raw_store import RawStore, iter_raw
from src.crawler.sources import SearchSource


class FakeResponse:
    def __init__(self, data):
        self._data, self.ok, self.status_code, self.text = data, True, 200, ""

    def json(self):
        return self._data


class FakeClient:
    """Serves `per_day` records per day, `pageSize` per page; counts requests. No network."""

    def __init__(self, per_day: int):
        self.per_day, self.requests = per_day, 0
        self.stats = type("S", (), {"records": 0})()

    def post_json(self, path, payload):
        self.requests += 1
        q = payload[0]
        page, size = q["pageNumber"], q["pageSize"]
        n = max(0, min(size, self.per_day - page * size))
        return FakeResponse({"page": {"content": [{"notifyNo": f"IB{page}_{i}"} for i in range(n)],
                                      "totalElements": self.per_day}})


def make(tmp_path, client, cp):
    return SearchSource("tbmt", client, RawStore(tmp_path / "raw", "tbmt"), cp, "/x", 10, 10000,
                        logging.getLogger("t"))


def test_crawl_is_resumable(tmp_path):
    cp = Checkpoint(tmp_path / "cp.sqlite")
    c1 = FakeClient(per_day=25)
    src = make(tmp_path, c1, cp)
    assert src.crawl(date(2024, 1, 1), date(2024, 1, 2)) == 50
    src.store.close()
    assert c1.requests == 6  # 3 pages x 2 days
    c2 = FakeClient(per_day=25)
    src2 = make(tmp_path, c2, cp)
    assert src2.crawl(date(2024, 1, 1), date(2024, 1, 2)) == 0
    assert c2.requests == 0  # everything already checkpointed
    src2.store.close()
    lines = list(iter_raw(tmp_path / "raw", "tbmt"))
    assert len(lines) == 6 and lines[0]["kind"] == "list"


def test_crawl_is_locked_until_gate_approved(monkeypatch):
    # Force the gate closed: with the real config already approved, this would start a live crawl.
    real_load = run_pipeline.load_config

    def locked(path=None):
        cfg = real_load(path)
        cfg["crawl"]["approved_option"] = None
        return cfg

    monkeypatch.setattr(run_pipeline, "load_config", locked)
    with pytest.raises(SystemExit) as e:
        run_pipeline.main(["crawl"])
    assert "gate Phase 0" in str(e.value)
