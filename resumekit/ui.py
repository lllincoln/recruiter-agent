"""Shared rich UX: console, banner, progress, and result rendering."""

from __future__ import annotations

from typing import Iterable

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from resumekit.models import Profile

console = Console()

# Palette
ACCENT = "bright_magenta"
OK = "bright_green"
WARN = "yellow"
BAD = "bright_red"
DIM = "grey62"


def make_progress() -> Progress:
    """A consistent progress bar used across exploration."""
    return Progress(
        SpinnerColumn(style=ACCENT),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=OK, finished_style=OK),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        TimeElapsedColumn(),
        console=console,
    )


def step(emoji: str, msg: str, style: str = "white") -> None:
    console.print(f"  {emoji} [{style}]{msg}[/{style}]")


def warn(msg: str) -> None:
    console.print(f"  [bold {WARN}]⚠[/bold {WARN}]  [{WARN}]{msg}[/{WARN}]")


def render_profile_summary(profile: Profile) -> None:
    t = Table(title="🔎 Exploration summary", title_style=f"bold {ACCENT}", expand=True)
    t.add_column("Source", style="cyan", no_wrap=True)
    t.add_column("Found", style="white")

    t.add_row("Resume text", f"{len(profile.resume_text):,} chars")
    t.add_row("Links extracted", str(len(profile.links)))
    if profile.github:
        gh = profile.github
        status = f"[{OK}]active[/{OK}]" if gh.is_active else f"[{DIM}]inactive[/{DIM}]"
        t.add_row(
            "GitHub",
            f"@{gh.username} · {gh.public_repos} repos · "
            f"⭐ {gh.total_stars} · {len(gh.contributions)} contributions · {status}",
        )
    pages = sum(len(s.pages) for s in profile.sites)
    if profile.sites:
        t.add_row("Sites crawled", f"{len(profile.sites)} sites · {pages} pages")
    if profile.youtube:
        t.add_row("YouTube", f"{len(profile.youtube)} transcripts")
    console.print(t)
    for note in profile.notes:
        warn(note)


def render_score_stream(chunks: Iterable[tuple[str, str]]) -> str:
    """Render a streamed score live: thinking dimmed/gray, answer as markdown.

    Consumes ``(kind, delta)`` tuples (kind is ``"thinking"`` or ``"response"``)
    and updates the terminal in place. The thinking transcript stays dimmed; the
    response is rendered as markdown as it streams. Returns the full response.
    """
    thinking = ""
    response = ""

    def _render() -> Group:
        parts: list = []
        if thinking:
            parts.append(
                Panel(
                    Text(thinking, style=DIM),
                    title="🧠 Thinking",
                    title_align="left",
                    border_style=DIM,
                    padding=(0, 1),
                )
            )
        if response:
            parts.append(Markdown(response))
        return Group(*parts)

    with Live(_render(), console=console, refresh_per_second=12, vertical_overflow="visible") as live:
        for kind, delta in chunks:
            if kind == "thinking":
                thinking += delta
            else:
                response += delta
            live.update(_render())

    return response
