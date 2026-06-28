"""Handler base class and the shared exploration context."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from resumekit.explore.monitor import CrawlMonitor
from resumekit.fetcher import Fetcher
from resumekit.models import Profile


@dataclass
class ExploreContext:
    """Everything a handler needs, shared across the whole exploration run."""

    fetcher: Fetcher
    monitor: CrawlMonitor
    profile: Profile
    # Global claim set: returns True only to the first caller for a URL, so a
    # URL reachable from several parents is *expanded* once (the Fetcher also
    # coalesces the underlying HTTP, this guards handler-level work).
    _claimed: set[str] = field(default_factory=set)
    _claim_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def claim(self, url: str) -> bool:
        async with self._claim_lock:
            if url in self._claimed:
                return False
            self._claimed.add(url)
            return True

    def note(self, msg: str) -> None:
        self.profile.notes.append(msg)


class Handler(ABC):
    """Processes one node: fetches it, records data, and emits child nodes.

    Implementations must be safe to share across concurrent ``expand`` calls;
    all mutable run state lives in :class:`ExploreContext`.
    """

    @abstractmethod
    async def expand(self, url: str, depth: int, ctx: ExploreContext) -> None:
        """Fetch ``url`` and populate the profile / tree. Best-effort; should
        set a terminal status on the node in the monitor."""
        raise NotImplementedError
