"""Extract text and links from a resume PDF."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from resumekit.models import Link, LinkKind

# Bare URLs and www. links found in the visible text.
_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s\)\]\}<>\"']+",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# host substring -> kind
_HOST_KINDS: list[tuple[str, LinkKind]] = [
    ("github.com", LinkKind.github),
    ("gitlab.com", LinkKind.gitlab),
    ("linkedin.com", LinkKind.linkedin),
    ("stackoverflow.com", LinkKind.stackoverflow),
    ("dev.to", LinkKind.blog),
    ("medium.com", LinkKind.blog),
    ("hashnode", LinkKind.blog),
    ("substack.com", LinkKind.blog),
    ("twitter.com", LinkKind.twitter),
    ("x.com", LinkKind.twitter),
    ("bsky.app", LinkKind.bluesky),
    ("kaggle.com", LinkKind.kaggle),
    ("huggingface.co", LinkKind.huggingface),
    ("youtube.com", LinkKind.youtube),
    ("youtu.be", LinkKind.youtube),
    ("npmjs.com", LinkKind.package),
    ("pypi.org", LinkKind.package),
]


def classify(url: str) -> LinkKind:
    host = url.lower()
    for needle, kind in _HOST_KINDS:
        if needle in host:
            return kind
    return LinkKind.website


def _normalize(url: str) -> str:
    url = url.rstrip(".,);]}'\"")
    if url.lower().startswith("www."):
        url = "https://" + url
    return url


def extract(pdf_path: Path) -> tuple[str, list[Link]]:
    """Return (full_text, deduped links) from a resume PDF.

    Captures both embedded hyperlink annotations and URLs/emails in the text,
    since PDFs often hide the real URL behind display text.
    """
    reader = PdfReader(str(pdf_path))
    text_parts: list[str] = []
    raw_urls: set[str] = set()

    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
        # Embedded link annotations (/Annots -> /A -> /URI)
        for annot in page.get("/Annots") or []:
            try:
                obj = annot.get_object()
                action = obj.get("/A")
                if action and action.get("/URI"):
                    raw_urls.add(str(action["/URI"]))
            except Exception:  # noqa: BLE001 - annotations are best-effort
                continue

    full_text = "\n".join(text_parts)
    raw_urls.update(_URL_RE.findall(full_text))

    links: dict[str, Link] = {}
    for raw in raw_urls:
        url = _normalize(raw)
        if url not in links:
            links[url] = Link(url=url, kind=classify(url))

    for email in _EMAIL_RE.findall(full_text):
        key = f"mailto:{email}"
        links.setdefault(key, Link(url=email, kind=LinkKind.email))

    return full_text, list(links.values())
