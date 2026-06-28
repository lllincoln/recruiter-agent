"""Generic same-domain web crawler handler (default depth 3)."""

from __future__ import annotations

import asyncio
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from recruiter.settings import settings
from recruiter.explore.monitor import Status
from recruiter.handlers.base import ExploreContext, Handler
from recruiter.models import CrawledPage, LinkKind, SiteExploration

_BLOG_HINTS = ("/blog", "/post", "/posts", "/article", "/writing", "/notes")
_SKIP_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".css", ".js")


def _same_site(a: str, b: str) -> bool:
    return urlparse(a).netloc == urlparse(b).netloc


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())[:8000]


def _looks_like_post(url: str, soup: BeautifulSoup) -> bool:
    return any(h in url.lower() for h in _BLOG_HINTS) or bool(soup.find("article"))


class WebHandler(Handler):
    """Crawls within a root's domain, attaching pages to a SiteExploration.

    The root SiteExploration is created lazily and keyed by domain so multiple
    resume links into the same site share one record.
    """

    async def expand(self, url: str, depth: int, ctx: ExploreContext) -> None:
        url, _ = urldefrag(url)
        if any(url.lower().endswith(ext) for ext in _SKIP_EXT):
            ctx.monitor.set_status(url, Status.skipped, detail="non-html")
            return

        ctx.monitor.set_status(url, Status.fetching)
        res = await ctx.fetcher.get(url, headers={"User-Agent": settings.user_agent})
        if not res.ok or "html" not in res.content_type:
            ctx.monitor.set_status(
                url, Status.error, detail=res.error or f"HTTP {res.status}"
            )
            return

        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        page = CrawledPage(
            url=url,
            title=title,
            text=_clean_text(soup),
            is_blog_post=_looks_like_post(url, soup),
        )
        site = _site_for(ctx, url)
        site.pages.append(page)
        ctx.monitor.set_status(
            url, Status.done, title=title,
            detail="blog post" if page.is_blog_post else None,
        )

        if depth >= settings.crawl_depth:
            return
        # Only follow same-site links; cross-site links would explode scope.
        children: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            href = href[0] if isinstance(href, list) else href
            if not href or href.startswith(("mailto:", "tel:", "#")):
                continue
            child, _ = urldefrag(urljoin(url, href))
            if _same_site(url, child):
                children.append(child)
        # Deduped recursion happens via the dispatcher in explore/__init__.
        from recruiter.explore import dispatch  # late import to avoid cycle

        await asyncio.gather(
            *(dispatch(c, url, depth + 1, ctx) for c in children)
        )


def _site_for(ctx: ExploreContext, url: str) -> SiteExploration:
    host = urlparse(url).netloc
    for s in ctx.profile.sites:
        if urlparse(s.root_url).netloc == host:
            return s
    site = SiteExploration(root_url=url, kind=LinkKind.website)
    ctx.profile.sites.append(site)
    return site
