"""Pydantic data models shared across exploration and scoring."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LinkKind(str, Enum):
    github = "github"
    linkedin = "linkedin"
    gitlab = "gitlab"
    stackoverflow = "stackoverflow"
    blog = "blog"  # dev.to / medium / hashnode / substack
    twitter = "twitter"
    bluesky = "bluesky"
    kaggle = "kaggle"
    huggingface = "huggingface"
    youtube = "youtube"
    package = "package"  # npm / pypi
    website = "website"  # personal site / unknown -> generic crawl
    email = "email"
    other = "other"


class Link(BaseModel):
    url: str
    kind: LinkKind = LinkKind.other


# --- GitHub ---------------------------------------------------------------


class GitHubRepository(BaseModel):
    name: str
    full_name: str
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    is_fork: bool = False
    topics: list[str] = Field(default_factory=list)
    pushed_at: str | None = None
    url: str

    # Populated by the deep per-repo fetch:
    languages: dict[str, int] = Field(default_factory=dict)  # lang -> bytes
    readme_excerpt: str | None = None
    open_issues: int = 0
    watchers: int = 0


class ContributionKind(str, Enum):
    commit = "commit"
    pull_request = "pull_request"
    issue = "issue"


class GitHubContribution(BaseModel):
    """A single contribution to a repo the user does not own.

    One record per commit, pull request, or issue. Fields beyond the common
    ones are populated only where the kind provides them (e.g. ``merged`` and
    ``comments`` are PR/issue concepts), giving the scorer richer signal than a
    bare commit count.
    """

    kind: ContributionKind
    repo_full_name: str
    repo_stars: int = 0
    url: str

    # The commit message (first line) or the PR/issue title.
    title: str = ""
    created_at: str | None = None

    # Pull request / issue metadata (absent for commits):
    state: str | None = None  # "open" / "closed"
    merged: bool | None = None  # pull requests only
    comments: int = 0  # discussion comment count


class GitHubProfile(BaseModel):
    username: str
    name: str | None = None
    bio: str | None = None
    followers: int = 0
    public_repos: int = 0
    total_stars: int = 0
    account_created: str | None = None
    last_active: str | None = None
    is_active: bool = False  # pushed to something in the last ~year
    top_languages: list[str] = Field(default_factory=list)
    owned_repos: list[GitHubRepository] = Field(default_factory=list)
    contributions: list[GitHubContribution] = Field(default_factory=list)


# --- Crawled pages --------------------------------------------------------


class CrawledPage(BaseModel):
    url: str
    title: str | None = None
    text: str = ""  # cleaned, truncated text content
    is_blog_post: bool = False


class SiteExploration(BaseModel):
    root_url: str
    kind: LinkKind
    pages: list[CrawledPage] = Field(default_factory=list)


class YouTubeVideo(BaseModel):
    url: str
    video_id: str
    title: str | None = None
    transcript: str = ""  # truncated


# --- Aggregate profile passed to the scorer -------------------------------


class Profile(BaseModel):
    resume_text: str = ""
    links: list[Link] = Field(default_factory=list)
    github: GitHubProfile | None = None
    sites: list[SiteExploration] = Field(default_factory=list)
    youtube: list[YouTubeVideo] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # explorer warnings/errors
