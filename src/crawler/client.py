"""Polite HTTP client: rate limit + jitter, retry/backoff, robots.txt, circuit breaker, stats."""
from __future__ import annotations

import json
import logging
import random
import ssl
import time
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter

RETRY_STATUSES = {429, 500, 502, 503, 504}
# Response markers that mean "the site is challenging us" — we stop instead of working around it.
CHALLENGE_MARKERS = ("g-recaptcha", "grecaptcha", "captcha", "access denied", "cf-chl")


class CrawlBlocked(RuntimeError):
    """403 / CAPTCHA challenge / robots disallow. Crawling must stop and be reported."""


class CircuitOpen(RuntimeError):
    """Too many consecutive errors — stop so the site structure/limits can be investigated."""


class LegacyTLSAdapter(HTTPAdapter):
    """muasamcong negotiates DHE with a 1024-bit key, which OpenSSL 3 rejects at its default
    security level (DH_KEY_TOO_SMALL). Lower only the security level; certificates are still verified."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


@dataclass
class CrawlStats:
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    requests: int = 0
    ok: int = 0
    errors: int = 0
    retries: int = 0
    bytes: int = 0
    records: int = 0
    elapsed_s: float = 0.0
    status_counts: dict[str, int] = field(default_factory=dict)

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


class PoliteClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        min_delay_s: float = 1.5,
        jitter_s: float = 0.5,
        timeout_s: float = 30,
        max_retries: int = 5,
        backoff_base_s: float = 2.0,
        max_consecutive_errors: int = 10,
        logger: logging.Logger | None = None,
        respect_robots: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.min_delay_s = min_delay_s
        self.jitter_s = jitter_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.max_consecutive_errors = max_consecutive_errors
        self.log = logger or logging.getLogger("ptvn.crawler")
        self.stats = CrawlStats()
        self._t0 = time.monotonic()
        self._last_request = 0.0
        self._consecutive_errors = 0
        self.session = requests.Session()
        self.session.mount(self.base_url, LegacyTLSAdapter())
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.5",
        })
        self.robots: urllib.robotparser.RobotFileParser | None = None
        self.user_agent = user_agent
        if respect_robots:
            self._load_robots()

    @classmethod
    def from_config(cls, crawl_cfg: dict, logger: logging.Logger | None = None) -> "PoliteClient":
        keys = ("min_delay_s", "jitter_s", "timeout_s", "max_retries", "backoff_base_s", "max_consecutive_errors")
        return cls(crawl_cfg["base_url"], crawl_cfg["user_agent"], logger=logger, **{k: crawl_cfg[k] for k in keys})

    def _load_robots(self) -> None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            resp = self.session.get(self.base_url + "/robots.txt", timeout=self.timeout_s)
            self._last_request = time.monotonic()
            rp.parse(resp.text.splitlines() if resp.ok else [])
        except requests.RequestException as e:
            self.log.warning("robots.txt unavailable (%s) — treating as allow-all", e)
            rp.parse([])
        self.robots = rp

    def allowed(self, url: str) -> bool:
        return self.robots is None or self.robots.can_fetch(self.user_agent, url)

    def _throttle(self) -> None:
        wait = self._last_request + self.min_delay_s + random.uniform(0, self.jitter_s) - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else urljoin(self.base_url + "/", path.lstrip("/"))
        if not self.allowed(url):
            raise CrawlBlocked(f"robots.txt disallows {url}")
        kwargs.setdefault("timeout", self.timeout_s)
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self._last_request = time.monotonic()
            self.stats.requests += 1
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.exceptions.SSLError:
                self.stats.errors += 1
                raise  # handshake/certificate problems are not transient — retrying won't help
            except requests.RequestException as e:
                self._on_error(f"{type(e).__name__}: {e}", url)
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt, None)
                    continue
                raise
            self.stats.status_counts[str(resp.status_code)] = self.stats.status_counts.get(str(resp.status_code), 0) + 1
            self.stats.bytes += len(resp.content)
            if resp.status_code == 403 or self._looks_like_challenge(resp):
                self.stats.errors += 1
                raise CrawlBlocked(f"HTTP {resp.status_code} / challenge page at {url} — stopping (do not bypass)")
            if resp.status_code in RETRY_STATUSES:
                self._on_error(f"HTTP {resp.status_code}", url)
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt, resp.headers.get("Retry-After"))
                    continue
                resp.raise_for_status()
            self._consecutive_errors = 0
            self.stats.ok += resp.ok
            self.stats.elapsed_s = round(time.monotonic() - self._t0, 1)
            return resp
        raise AssertionError("unreachable")

    def get(self, path: str, **kw) -> requests.Response:
        return self.request("GET", path, **kw)

    def post_json(self, path: str, payload, **kw) -> requests.Response:
        return self.request("POST", path, json=payload, **kw)

    def _on_error(self, msg: str, url: str) -> None:
        self.stats.errors += 1
        self._consecutive_errors += 1
        self.log.warning("request error (%d consecutive): %s — %s", self._consecutive_errors, msg, url)
        if self._consecutive_errors >= self.max_consecutive_errors:
            raise CircuitOpen(f"{self._consecutive_errors} consecutive errors, last: {msg}")

    def _sleep_backoff(self, attempt: int, retry_after: str | None) -> None:
        self.stats.retries += 1
        delay = self.backoff_base_s * (2 ** attempt)
        if retry_after and retry_after.isdigit():
            delay = max(delay, float(retry_after))
        self.log.info("retry in %.1fs", delay)
        time.sleep(delay)

    @staticmethod
    def _looks_like_challenge(resp: requests.Response) -> bool:
        ctype = resp.headers.get("Content-Type", "")
        if "json" in ctype or resp.status_code != 200:
            return False
        head = resp.text[:5000].lower()
        # A challenge page is a short interstitial; normal portal pages are large and also load the
        # reCAPTCHA script for their search forms, so only flag small pages.
        return len(resp.content) < 20000 and any(m in head for m in CHALLENGE_MARKERS)
