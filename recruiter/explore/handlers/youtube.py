"""YouTube handler: fetches the transcript of a video."""

from __future__ import annotations

import asyncio
import re

from recruiter.explore.monitor import Status
from recruiter.explore.handlers.base import ExploreContext, Handler
from recruiter.models import YouTubeVideo

_ID_RES = [
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/(?:embed|shorts)/([A-Za-z0-9_-]{11})"),
]


def _video_id(url: str) -> str | None:
    for rx in _ID_RES:
        m = rx.search(url)
        if m:
            return m.group(1)
    return None


class YouTubeHandler(Handler):
    async def expand(self, url: str, depth: int, ctx: ExploreContext) -> None:
        vid = _video_id(url)
        if not vid:
            ctx.monitor.set_status(url, Status.skipped, detail="no video id")
            return

        ctx.monitor.set_status(url, Status.fetching, detail="transcript")
        try:
            text = await asyncio.to_thread(self._transcript, vid)
        except Exception as e:  # noqa: BLE001 - transcripts are flaky
            ctx.monitor.set_status(url, Status.error, detail=f"no transcript: {type(e).__name__}")
            return

        if not text:
            ctx.monitor.set_status(url, Status.skipped, detail="no transcript")
            return

        ctx.profile.youtube.append(
            YouTubeVideo(url=url, video_id=vid, transcript=text[:8000])
        )
        ctx.monitor.set_status(
            url, Status.done, detail=f"transcript {len(text):,} chars"
        )

    @staticmethod
    def _transcript(video_id: str) -> str:
        # API shape changed across versions; support both.
        from youtube_transcript_api import YouTubeTranscriptApi

        try:  # newer instance API
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            snippets = getattr(fetched, "snippets", fetched)
            return " ".join(s.text for s in snippets)
        except (TypeError, AttributeError):  # older classmethod API
            data = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join(d["text"] for d in data)
