"""Shared HTTP fetcher: per-host rate limiting, single-flight, result cache.

Every distinct (method, url, params) is fetched at most once. Concurrent
callers for the same key await the *same* in-flight request and all receive the
result; later callers get it straight from the cache. Each host is paced by its
own token-bucket-ish limiter so we never hammer a single domain, and
``api.github.com`` additionally honors GitHub's ``X-RateLimit`` headers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from resumekit.settings import settings


@dataclass
class FetchResult:
    url: str
    status: int
    headers: dict[str, str]
    text: str
    ok: bool
    error: str | None = None
    content_type: str = ""


class _HostLimiter:
    """Minimum-interval pacer for one host (serializes the gap, not the work)."""

    def __init__(self, rate_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_allowed = time.monotonic() + self._min_interval


@dataclass
class Fetcher:
    """Async HTTP client wrapper with dedup, caching, and per-host pacing."""

    client: httpx.AsyncClient
    _cache: dict[str, FetchResult] = field(default_factory=dict)
    _inflight: dict[str, asyncio.Future] = field(default_factory=dict)
    _limiters: dict[str, _HostLimiter] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _limiter_for(self, host: str) -> _HostLimiter:
        limiter = self._limiters.get(host)
        if limiter is None:
            rate = (
                settings.github_rate_per_sec
                if host == "api.github.com"
                else settings.host_rate_per_sec
            )
            limiter = _HostLimiter(rate)
            self._limiters[host] = limiter
        return limiter

    @staticmethod
    def _key(method: str, url: str, params: dict | None) -> str:
        if not params:
            return f"{method} {url}"
        flat = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{method} {url}?{flat}"

    async def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> FetchResult:
        key = self._key("GET", url, params)

        # Fast path: already cached.
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Coalesce concurrent identical requests onto a single future.
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            fut = self._inflight.get(key)
            if fut is None:
                fut = asyncio.get_event_loop().create_future()
                self._inflight[key] = fut
                owner = True
            else:
                owner = False

        if not owner:
            return await fut

        try:
            result = await self._do_get(url, params, headers)
            self._cache[key] = result
            fut.set_result(result)
            return result
        except Exception as e:  # noqa: BLE001 - propagate to all awaiters
            fut.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    async def _do_get(self, url, params, headers) -> FetchResult:
        host = urlparse(url).netloc
        await self._limiter_for(host).acquire()
        try:
            r = await self.client.get(url, params=params, headers=headers)
        except Exception as e:  # noqa: BLE001
            return FetchResult(
                url=url, status=0, headers={}, text="", ok=False, error=str(e)
            )

        # Respect GitHub's secondary rate limit signal for subsequent calls.
        if host == "api.github.com" and r.headers.get("X-RateLimit-Remaining") == "0":
            reset = r.headers.get("X-RateLimit-Reset")
            if reset:
                delay = max(0.0, float(reset) - time.time())
                if 0 < delay <= 60:  # only short, sane waits
                    await asyncio.sleep(delay)

        return FetchResult(
            url=url,
            status=r.status_code,
            headers=dict(r.headers),
            text=r.text,
            ok=200 <= r.status_code < 300,
            content_type=r.headers.get("content-type", ""),
        )
