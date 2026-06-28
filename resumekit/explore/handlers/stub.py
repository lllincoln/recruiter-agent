"""Stub handler for sources not yet implemented (HuggingFace, npm, …).

Records the link in the tree as skipped so the user sees it was recognized but
not deeply explored. Replace with real handlers later.
"""

from __future__ import annotations

from resumekit.explore.monitor import Status
from resumekit.explore.handlers.base import ExploreContext, Handler
from resumekit.models import LinkKind


class StubHandler(Handler):
    def __init__(self, kind: LinkKind) -> None:
        self.kind = kind

    async def expand(self, url: str, depth: int, ctx: ExploreContext) -> None:
        ctx.monitor.set_status(
            url, Status.skipped, detail=f"{self.kind.value} handler not implemented"
        )
