"""Exploration phase: turn a resume PDF into a complete Profile.

Non-AI. Extracts links, then explores them through per-source handlers
(web crawl, GitHub REST API, YouTube transcript, …) into a single live,
deduplicated tree. A shared rate-limited Fetcher coalesces duplicate requests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from resumekit.handlers import ExploreContext

from resumekit import ui
from resumekit.settings import settings
from resumekit.explore.monitor import CrawlMonitor
from resumekit.extract import extract
from resumekit.fetcher import Fetcher
from resumekit.models import LinkKind, Profile

# NOTE: handlers are imported lazily inside the functions below to avoid an
# import cycle (handlers import resumekit.explore.dispatch).

# Kinds worth exploring (everything else is just recorded as a resume link).
_EXPLORE_KINDS = {
    LinkKind.github,
    LinkKind.youtube,
    LinkKind.website,
    LinkKind.blog,
    LinkKind.gitlab,
    LinkKind.stackoverflow,
    LinkKind.kaggle,
    LinkKind.huggingface,
    LinkKind.package,
}


def build_profile(pdf_path: Path) -> Profile:
    """Synchronous entry point for the CLI."""
    return asyncio.run(_build_profile(pdf_path))


async def dispatch(url: str, parent: str | None, depth: int, ctx: "ExploreContext") -> None:
    """Register ``url`` in the tree and route it to the right handler.

    Global dedup happens here: the monitor coalesces the tree node and
    ``ctx.claim`` ensures only the first caller actually expands it. The
    Fetcher independently coalesces the underlying HTTP request.
    """
    if parent is not None:
        is_new_in_tree = ctx.monitor.discover(url, parent, depth)
        if not is_new_in_tree:
            return  # already shown elsewhere; its status is the source of truth
    if not await ctx.claim(url):
        return
    from resumekit.handlers import handler_for  # lazy: breaks import cycle

    kind = _classify_runtime(url)
    await handler_for(kind).expand(url, depth, ctx)


def _classify_runtime(url: str) -> LinkKind:
    # Reuse the extractor's classifier so crawled-up links route correctly.
    from resumekit.extract import classify

    return classify(url)


async def _build_profile(pdf_path: Path) -> Profile:
    ui.step("📑", f"Reading [bold]{pdf_path.name}[/bold] …")
    resume_text, links = extract(pdf_path)
    ui.step("🔗", f"Extracted [bold]{len(links)}[/bold] links from the resume", ui.OK)

    profile = Profile(resume_text=resume_text, links=links)
    roots = [link for link in links if link.kind in _EXPLORE_KINDS]
    if not roots:
        ui.warn("No explorable links found — scoring will rely on resume text only.")
        return profile

    if not settings.github_token and any(r.kind == LinkKind.github for r in roots):
        profile.notes.append(
            "No GITHUB_TOKEN set — GitHub data limited (60 req/hr, no private repos)."
        )

    monitor = CrawlMonitor()
    for link in roots:
        monitor.add_root(link.url, link.kind.value)

    from resumekit.handlers import ExploreContext  # lazy: breaks import cycle

    async with httpx.AsyncClient(
        timeout=settings.request_timeout, follow_redirects=True
    ) as client:
        ctx = ExploreContext(fetcher=Fetcher(client=client), monitor=monitor, profile=profile)
        with monitor:
            await asyncio.gather(
                *(dispatch(link.url, None, 0, ctx) for link in roots)
            )

    # Drop empty site shells produced by failed crawls.
    profile.sites = [s for s in profile.sites if s.pages]
    return profile
