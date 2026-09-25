"""Crawl one source (tbmt / kqlcnt / khlcnt) over a date window via the portal's smart/search endpoint.

Windows are single days: the endpoint caps `totalElements` at 10,000 and page size at 10, and the
busiest source (KQLCNT) peaks around 3,300 records/day in Phase 0 sampling. A day that still exceeds
the cap is split further by `investField`.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterator

from src.crawler.checkpoint import Checkpoint
from src.crawler.client import PoliteClient
from src.crawler.es_query import build_search_payload
from src.crawler.raw_store import RawStore

INVEST_FIELDS = ["HH", "XL", "TV", "PTV", "HON_HOP"]


def days(start: date, end: date) -> Iterator[date]:
    d = end
    while d >= start:  # newest first, so a partial crawl still has the most recent data
        yield d
        d -= timedelta(days=1)


class SearchSource:
    def __init__(self, name: str, client: PoliteClient, store: RawStore, checkpoint: Checkpoint,
                 endpoint: str, page_size: int, max_result_window: int, logger: logging.Logger,
                 extra_filters: list[dict] | None = None):
        self.name = name
        self.client = client
        self.store = store
        self.cp = checkpoint
        self.endpoint = endpoint
        self.page_size = page_size
        self.max_result_window = max_result_window
        self.log = logger
        self.extra_filters = extra_filters or []

    def _payload(self, day: date, page: int, invest_field: str | None) -> dict:
        payload = build_search_payload(self.name, page=page, page_size=self.page_size, start=day, end=day,
                                       extra_filters=self.extra_filters)
        if invest_field:
            payload["query"][0]["filters"].append(
                {"fieldName": "investField", "searchType": "in", "fieldValues": [invest_field]})
        return payload

    def _fetch(self, day: date, page: int, invest_field: str | None) -> tuple[list[dict], int]:
        payload = self._payload(day, page, invest_field)
        resp = self.client.post_json(self.endpoint, [payload])
        data = resp.json() if resp.ok else {"error": resp.status_code, "body": resp.text[:500]}
        self.store.write("list", self.endpoint, payload, resp.status_code, data)
        if not resp.ok:
            raise RuntimeError(f"{self.name} {day} p{page}: HTTP {resp.status_code} {resp.text[:200]}")
        page_obj = data.get("page", {})
        return page_obj.get("content", []), int(page_obj.get("totalElements") or 0)

    def crawl_window(self, day: date, invest_field: str | None = None) -> int:
        """Crawl every page of one day (optionally one investField). Returns records fetched now."""
        key = day.isoformat() + (f"|{invest_field}" if invest_field else "")
        if self.cp.page_done(self.name, key, key, -1):  # page -1 = whole window finished
            return 0
        records, total = ([], None)
        if not self.cp.page_done(self.name, key, key, 0):
            records, total = self._fetch(day, 0, invest_field)
            if total >= self.max_result_window and invest_field is None:
                self.log.info("%s %s: total %d hits the %d cap — splitting by investField",
                              self.name, day, total, self.max_result_window)
                n = sum(self.crawl_window(day, f) for f in INVEST_FIELDS)
                self.cp.mark_page(self.name, key, key, -1, "done", n, total)
                return n
            if total >= self.max_result_window:
                self.log.warning("%s %s %s: %d records exceed the pagination cap; only the first %d are reachable",
                                 self.name, day, invest_field, total, self.max_result_window)
            self.cp.mark_page(self.name, key, key, 0, "done", len(records), total)
        else:
            # page 0 done in an earlier run; recover total from the checkpoint
            total = self.cp.conn.execute(
                "SELECT total FROM pages WHERE source=? AND window_start=? AND page=0", (self.name, key)
            ).fetchone()[0] or 0
        fetched = len(records)
        n_pages = min(-(-total // self.page_size), self.max_result_window // self.page_size)
        for page in range(1, n_pages):
            if self.cp.page_done(self.name, key, key, page):
                continue
            recs, _ = self._fetch(day, page, invest_field)
            self.cp.mark_page(self.name, key, key, page, "done", len(recs), total)
            fetched += len(recs)
            if not recs:
                break
        self.cp.mark_page(self.name, key, key, -1, "done", fetched, total)
        self.client.stats.records += fetched
        self.log.info("%s %s%s: %d records (total reported %d)", self.name, day,
                      f" [{invest_field}]" if invest_field else "", fetched, total)
        return fetched

    def crawl(self, start: date, end: date) -> int:
        return sum(self.crawl_window(d) for d in days(start, end))
