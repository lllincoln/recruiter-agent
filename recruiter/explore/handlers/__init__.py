"""Per-source handlers for the exploration tree.

Each node in the crawl tree is processed by a :class:`Handler` chosen by URL.
Web links are crawled; GitHub links are expanded via the REST API; YouTube
links yield a transcript; others (HuggingFace, npm, …) are stubs for now.

All handlers fetch through the shared :class:`~recruiter.fetcher.Fetcher`, so
duplicate URLs are coalesced into one request and cached, and every host is
rate-limited independently.
"""

from __future__ import annotations

from recruiter.explore.handlers.base import ExploreContext, Handler
from recruiter.explore.handlers.github import GitHubHandler
from recruiter.explore.handlers.stub import StubHandler
from recruiter.explore.handlers.web import WebHandler
from recruiter.explore.handlers.youtube import YouTubeHandler
from recruiter.models import LinkKind

# Kind -> handler instance. Stub handlers record the link but do nothing deep.
_HANDLERS: dict[LinkKind, Handler] = {
    LinkKind.github: GitHubHandler(),
    LinkKind.youtube: YouTubeHandler(),
    LinkKind.website: WebHandler(),
    LinkKind.blog: WebHandler(),
    LinkKind.gitlab: WebHandler(),
    LinkKind.stackoverflow: WebHandler(),
    LinkKind.kaggle: WebHandler(),
    LinkKind.huggingface: StubHandler(LinkKind.huggingface),
    LinkKind.package: StubHandler(LinkKind.package),
}

_DEFAULT = WebHandler()


def handler_for(kind: LinkKind) -> Handler:
    return _HANDLERS.get(kind, _DEFAULT)


__all__ = [
    "ExploreContext",
    "Handler",
    "GitHubHandler",
    "WebHandler",
    "YouTubeHandler",
    "StubHandler",
    "handler_for",
]
