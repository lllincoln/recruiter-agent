"""Live tree visualization for the crawl, with global dedup and collapsing.

A single :class:`CrawlMonitor` owns every node across every root, keyed by URL,
so a URL discovered under two different parents is fetched once and its status
is shown once (later discoveries are recorded as extra back-references). The
monitor renders a ``rich.tree.Tree`` inside a ``Live`` and collapses branches
that would overflow the terminal height (useful at large crawl depths).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from recruiter import ui


class Status(str, Enum):
    queued = "queued"
    fetching = "fetching"
    done = "done"
    skipped = "skipped"
    error = "error"


_STATUS_STYLE = {
    Status.queued: ("·", ui.DIM),
    Status.fetching: ("◌", "bright_yellow"),
    Status.done: ("✓", ui.OK),
    Status.skipped: ("⊘", ui.DIM),
    Status.error: ("✗", ui.BAD),
}


@dataclass
class Node:
    url: str
    depth: int
    parent: str | None
    status: Status = Status.queued
    title: str | None = None
    detail: str = ""  # e.g. page count, error reason
    children: list[str] = field(default_factory=list)
    also_from: list[str] = field(default_factory=list)  # other parents (deduped)
    is_root: bool = False


def _short(url: str, width: int = 70) -> str:
    p = urlparse(url)
    shown = (p.netloc + p.path).rstrip("/") or url
    if p.query:
        shown += "?…"
    if len(shown) > width:
        shown = shown[: width - 1] + "…"
    return shown


class CrawlMonitor:
    """Owns the global URL graph and renders it live as a tree."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._roots: list[str] = []
        self._live: Live | None = None

    # --- graph mutation (called by the crawler) -----------------------

    def add_root(self, url: str, label: str) -> None:
        if url in self._nodes:
            return
        self._nodes[url] = Node(url=url, depth=0, parent=None, is_root=True, title=label)
        self._roots.append(url)
        self.refresh()

    def discover(self, url: str, parent: str, depth: int) -> bool:
        """Register ``url`` as found under ``parent``.

        Returns True if this is the first time we've seen ``url`` (i.e. the
        caller should fetch it). On a duplicate, records the extra parent so
        the existing node's status stays the single source of truth.
        """
        existing = self._nodes.get(url)
        if existing is not None:
            if parent != existing.parent and parent not in existing.also_from:
                existing.also_from.append(parent)
            self._link_child(parent, url)
            self.refresh()
            return False
        self._nodes[url] = Node(url=url, depth=depth, parent=parent)
        self._link_child(parent, url)
        self.refresh()
        return True

    def _link_child(self, parent: str | None, child: str) -> None:
        if parent is None:
            return
        pnode = self._nodes.get(parent)
        if pnode and child not in pnode.children:
            pnode.children.append(child)

    def set_status(
        self,
        url: str,
        status: Status,
        *,
        title: str | None = None,
        detail: str | None = None,
    ) -> None:
        node = self._nodes.get(url)
        if not node:
            return
        node.status = status
        if title is not None:
            node.title = title
        if detail is not None:
            node.detail = detail
        self.refresh()

    # --- rendering -----------------------------------------------------

    def _node_label(self, node: Node) -> Text:
        glyph, style = _STATUS_STYLE[node.status]
        text = Text()
        text.append(f"{glyph} ", style=style)
        if node.is_root:
            text.append(_short(node.url), style=f"bold {ui.ACCENT}")
        else:
            text.append(_short(node.url), style="white" if node.status is Status.done else ui.DIM)
        if node.title and node.title != node.url and not node.is_root:
            text.append(f"  {node.title[:50]}", style=ui.DIM)
        if node.detail:
            text.append(f"  ({node.detail})", style=style)
        if node.also_from:
            text.append(f"  ↳ also linked ×{len(node.also_from)}", style=ui.DIM)
        return text

    def _deepest(self) -> int:
        return max((n.depth for n in self._nodes.values()), default=0)

    def _budget(self) -> int:
        """Number of tree lines we can show before collapsing kicks in.

        Only a real interactive terminal imposes a height limit; piped /
        non-tty output (reports a bogus height) gets no limit so nothing is
        needlessly collapsed.
        """
        if not ui.console.is_terminal:
            return 1_000_000  # effectively unlimited
        # Reserve room for the header line + the summary table that follows.
        return max(8, ui.console.size.height - 8)

    def _build_tree(self) -> Tree:
        # Start with the full tree; only collapse the deepest levels while it
        # would overflow the available height. The first level under each root
        # is always shown.
        budget = self._budget()
        max_depth = self._deepest()
        while max_depth > 1:
            if self._render_lines(max_depth) <= budget:
                break
            max_depth -= 1
        return self._tree_at(max_depth)

    def _tree_at(self, max_depth: int) -> Tree:
        root = Tree(Text("🌐 Crawl", style=f"bold {ui.ACCENT}"), guide_style=ui.DIM)
        for r in self._roots:
            self._attach(root, self._nodes[r], max_depth)
        return root

    def _render_lines(self, max_depth: int) -> int:
        """Count rendered lines of the tree at a given max depth (cheap-ish)."""
        lines = 1  # the "🌐 Crawl" header
        for r in self._roots:
            lines += self._lines_for(self._nodes[r], max_depth)
        return lines

    def _lines_for(self, node: Node, max_depth: int) -> int:
        lines = 1
        if node.depth >= max_depth and node.children:
            return lines + 1  # the "… collapsed" line
        for child_url in node.children:
            child = self._nodes.get(child_url)
            if child and child.parent == node.url:
                lines += self._lines_for(child, max_depth)
        return lines

    def _attach(self, parent_branch: Tree, node: Node, max_depth: int) -> None:
        branch = parent_branch.add(self._node_label(node))
        if node.depth >= max_depth and node.children:
            hidden = self._count_subtree(node)
            branch.add(Text(f"… {hidden} more (collapsed)", style=ui.DIM))
            return
        for child_url in node.children:
            child = self._nodes.get(child_url)
            # Only render a child under its first-discovered parent to avoid
            # duplicating a deduped node in multiple places.
            if child and child.parent == node.url:
                self._attach(branch, child, max_depth)

    def _count_subtree(self, node: Node) -> int:
        total = 0
        for child_url in node.children:
            child = self._nodes.get(child_url)
            if child and child.parent == node.url:
                total += 1 + self._count_subtree(child)
        return total

    def refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._build_tree())

    # --- context manager ----------------------------------------------

    def __enter__(self) -> "CrawlMonitor":
        self._live = Live(
            self._build_tree(),
            console=ui.console,
            refresh_per_second=12,
            vertical_overflow="crop",
        )
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._live is not None:
            self._live.update(self._build_tree())
            self._live.__exit__(*exc)
            self._live = None
