"""GitHub handler: expands a github.com/<user> node via the REST API.

The user node gets one child per owned repo (shown in the tree). Each repo is
deep-fetched concurrently for languages, README excerpt, and counts. External
contributions (commits to repos the user doesn't own) are discovered via the
commit-search API. All requests go through the shared rate-limited Fetcher.
"""

from __future__ import annotations

import asyncio
import base64
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from resumekit.settings import settings
from resumekit.explore.monitor import Status
from resumekit.explore.handlers.base import ExploreContext, Handler
from resumekit.models import GitHubContribution, GitHubProfile, GitHubRepository

API = "https://api.github.com"
_USER_RE = re.compile(r"github\.com/([^/?#]+)", re.IGNORECASE)
_NON_USER = {"orgs", "sponsors", "topics", "marketplace", "features", "about"}


def extract_username(url: str) -> str | None:
    m = _USER_RE.search(url)
    if not m:
        return None
    user = m.group(1).strip()
    return None if not user or user.lower() in _NON_USER else user


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": settings.user_agent,
    }
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


class GitHubHandler(Handler):
    async def expand(self, url: str, depth: int, ctx: ExploreContext) -> None:
        username = extract_username(url)
        if not username:
            ctx.monitor.set_status(url, Status.skipped, detail="not a user URL")
            return

        ctx.monitor.set_status(url, Status.fetching)
        user = await self._json(ctx, f"{API}/users/{username}")
        if not user:
            ctx.monitor.set_status(url, Status.error, detail="user not found")
            return

        raw_repos = await self._fetch_repo_list(ctx, username)

        # Each repo becomes a child node in the tree, deep-fetched concurrently.
        async def do_repo(raw: dict) -> GitHubRepository:
            repo_url = raw.get("html_url", "")
            ctx.monitor.discover(repo_url, parent=url, depth=depth + 1)
            ctx.monitor.set_status(repo_url, Status.fetching)
            repo = _base_repo(raw)
            if settings.github_deep_all_repos and not raw.get("fork"):
                await self._deepen(ctx, repo, raw)
            stars = f"⭐{repo.stars}" if repo.stars else ""
            lang = repo.language or ""
            ctx.monitor.set_status(
                repo_url, Status.done, title=repo.name,
                detail=" ".join(x for x in (lang, stars) if x) or None,
            )
            return repo

        repos = await asyncio.gather(*(do_repo(r) for r in raw_repos))

        contributions = await self._fetch_contributions(ctx, username, repos)
        last_active = _most_recent_push(repos)

        ctx.profile.github = GitHubProfile(
            username=username,
            name=user.get("name"),
            bio=user.get("bio"),
            followers=user.get("followers", 0),
            public_repos=user.get("public_repos", 0),
            total_stars=sum(r.stars for r in repos),
            account_created=user.get("created_at"),
            last_active=last_active,
            is_active=_is_active(last_active),
            top_languages=_top_languages(repos),
            owned_repos=sorted(repos, key=lambda r: r.stars, reverse=True),
            contributions=contributions,
        )
        ctx.monitor.set_status(
            url, Status.done, title=f"@{username}",
            detail=f"{len(repos)} repos · ⭐{sum(r.stars for r in repos)}",
        )

    # --- helpers -------------------------------------------------------

    async def _json(self, ctx: ExploreContext, url: str, params: dict | None = None):
        res = await ctx.fetcher.get(url, params=params, headers=_headers())
        if res.status == 404 or not res.ok:
            return None
        import json

        try:
            return json.loads(res.text)
        except ValueError:
            return None

    async def _fetch_repo_list(self, ctx, username) -> list[dict]:
        repos: list[dict] = []
        page = 1
        while len(repos) < settings.github_max_repos:
            batch = await self._json(
                ctx,
                f"{API}/users/{username}/repos",
                {"per_page": 100, "page": page, "sort": "pushed"},
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos[: settings.github_max_repos]

    async def _deepen(self, ctx, repo: GitHubRepository, raw: dict) -> None:
        full = repo.full_name
        langs, readme = await asyncio.gather(
            self._json(ctx, f"{API}/repos/{full}/languages"),
            self._json(ctx, f"{API}/repos/{full}/readme"),
        )
        if isinstance(langs, dict):
            repo.languages = langs
        if isinstance(readme, dict) and readme.get("content"):
            try:
                decoded = base64.b64decode(readme["content"]).decode("utf-8", "ignore")
                repo.readme_excerpt = decoded[:2000]
            except Exception:  # noqa: BLE001
                pass
        repo.open_issues = raw.get("open_issues_count", 0)
        repo.watchers = raw.get("subscribers_count", raw.get("watchers_count", 0))

    async def _fetch_contributions(
        self, ctx, username, owned: list[GitHubRepository]
    ) -> list[GitHubContribution]:
        owned_names = {r.full_name.lower() for r in owned}
        data = await self._json(
            ctx,
            f"{API}/search/commits",
            {"q": f"author:{username}", "per_page": 100,
             "sort": "author-date", "order": "desc"},
        )
        if not data:
            return []
        counts: Counter[str] = Counter()
        stars: dict[str, int] = {}
        urls: dict[str, str] = {}
        for item in data.get("items", []):
            repo = item.get("repository") or {}
            full = repo.get("full_name")
            if not full or full.lower() in owned_names:
                continue
            counts[full] += 1
            stars[full] = repo.get("stargazers_count", 0)
            urls[full] = repo.get("html_url", "")
        return [
            GitHubContribution(
                repo_full_name=f, commits=n,
                repo_stars=stars.get(f, 0), url=urls.get(f, ""),
            )
            for f, n in counts.most_common(25)
        ]


def _base_repo(r: dict) -> GitHubRepository:
    return GitHubRepository(
        name=r["name"],
        full_name=r["full_name"],
        description=r.get("description"),
        language=r.get("language"),
        stars=r.get("stargazers_count", 0),
        forks=r.get("forks_count", 0),
        is_fork=r.get("fork", False),
        topics=r.get("topics", []) or [],
        pushed_at=r.get("pushed_at"),
        url=r.get("html_url", ""),
    )


def _top_languages(repos: list[GitHubRepository], n: int = 6) -> list[str]:
    c = Counter(r.language for r in repos if r.language and not r.is_fork)
    return [lang for lang, _ in c.most_common(n)]


def _most_recent_push(repos: list[GitHubRepository]) -> str | None:
    pushes = [r.pushed_at for r in repos if r.pushed_at]
    return max(pushes) if pushes else None


def _is_active(last_active: str | None) -> bool:
    if not last_active:
        return False
    try:
        dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt > datetime.now(timezone.utc) - timedelta(days=365)
