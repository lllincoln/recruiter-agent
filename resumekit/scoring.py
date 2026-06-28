"""Scoring phase: feed the full profile to a (configurable) LLM via litellm.

The model is called directly through ``litellm.completion`` so any provider
(Anthropic, Gemini, Ollama, OpenRouter, …) works from a single config string.
The scoring *prompt* is one of the role files in ``roles/`` — the user picks
which role they want to be graded against.

The model is asked to think extensively. The call is streamed: reasoning
("thinking") tokens and the final answer tokens are yielded separately so the
UI can show the thinking dimmed and render the answer as markdown.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

import litellm
import pymupdf

from resumekit.settings import settings
from resumekit.models import Profile


@dataclass(frozen=True)
class Role:
    """A scoring rubric/prompt loaded from a markdown file in ``roles/``."""

    name: str  # human-readable, derived from the filename
    path: Path

    def prompt(self) -> str:
        return self.path.read_text(encoding="utf-8")


def list_roles() -> list[Role]:
    """All available roles, sorted by name. Empty if the directory is missing."""
    roles_dir = settings.roles_dir
    if not roles_dir.is_dir():
        return []
    roles = [Role(name=p.stem, path=p) for p in roles_dir.glob("*.md")]
    return sorted(roles, key=lambda r: r.name.lower())


def _render_profile(profile: Profile) -> str:
    """Serialize the whole profile into one context blob for the scorer."""
    parts: list[str] = []
    parts.append("# RESUME TEXT\n" + (profile.resume_text or "(none)"))

    if profile.links:
        links = "\n".join(f"- [{lk.kind.value}] {lk.url}" for lk in profile.links)
        parts.append("# LINKS FOUND\n" + links)

    if profile.github:
        parts.append("# GITHUB PROFILE\n" + profile.github.model_dump_json(indent=2))

    for site in profile.sites:
        header = f"# SITE ({site.kind.value}): {site.root_url}"
        pages = []
        for p in site.pages:
            tag = " [BLOG POST]" if p.is_blog_post else ""
            pages.append(f"## {p.title or p.url}{tag}\n{p.url}\n{p.text}")
        parts.append(header + "\n\n" + "\n\n".join(pages))

    for vid in profile.youtube:
        parts.append(f"# YOUTUBE: {vid.url}\n(transcript)\n{vid.transcript}")

    if profile.notes:
        parts.append(
            "# EXPLORATION NOTES\n" + "\n".join(f"- {n}" for n in profile.notes)
        )

    return "\n\n".join(parts)


def _render_pdf_images(pdf_path: Path, dpi: int = 150) -> list[str]:
    """Rasterize each page of the resume PDF to a base64 PNG data URL.

    Giving the model the rendered pages (not just extracted text) lets it judge
    layout, formatting, fonts, and anything the text extractor drops.
    """
    images: list[str] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
            images.append(f"data:image/png;base64,{b64}")
    return images


@dataclass(frozen=True)
class Capabilities:
    """What the configured model supports, per litellm's model metadata."""

    vision: bool
    reasoning: bool

    def warnings(self) -> list[str]:
        msgs: list[str] = []
        if not self.vision:
            msgs.append(
                f"{settings.model!r} does not support image input — "
                "scoring on resume text only, no rendered pages."
            )
        if not self.reasoning:
            msgs.append(
                f"{settings.model!r} does not support reasoning/thinking — "
                "scoring without extended thinking."
            )
        return msgs


def capabilities() -> Capabilities:
    """Query litellm for whether the configured model supports vision/reasoning.

    litellm's checks raise on unknown models; treat unknowns as unsupported.
    """
    try:
        vision = litellm.supports_vision(model=settings.model)
    except Exception:  # noqa: BLE001
        vision = False
    try:
        reasoning = litellm.supports_reasoning(model=settings.model)
    except Exception:  # noqa: BLE001
        reasoning = False
    return Capabilities(vision=vision, reasoning=reasoning)


ChunkKind = Literal["thinking", "response"]


def score_stream(
    profile: Profile, role: Role, resume_path: Path
) -> Iterator[tuple[ChunkKind, str]]:
    """Stream the scoring model, yielding ``(kind, delta)`` tuples.

    The rendered resume page images are sent alongside the text prompt so the
    model can assess layout and formatting, not just extracted text — but only
    if the model supports image input. Extended thinking is requested only if
    the model supports reasoning.

    ``kind`` is ``"thinking"`` for reasoning tokens and ``"response"`` for the
    final answer tokens. The answer is markdown (the role prompt asks for it).
    """
    caps = capabilities()
    context = _render_profile(profile)
    user_content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Score the following candidate profile against the rubric above. "
                "Use only the evidence provided. The rendered resume page image(s) "
                "are attached so you can judge layout and formatting.\n\n"
                "===== CANDIDATE PROFILE =====\n" + context
            ),
        }
    ]
    if caps.vision:
        for url in _render_pdf_images(resume_path):
            user_content.append({"type": "image_url", "image_url": {"url": url}})

    messages = [
        {"role": "system", "content": role.prompt()},
        {"role": "user", "content": user_content},
    ]

    kwargs = dict(
        model=settings.model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        stream=True,
    )
    if caps.reasoning:
        kwargs["reasoning_effort"] = settings.reasoning_effort

    stream = litellm.completion(**kwargs)

    for chunk in stream:
        choices = getattr(chunk, "choices", None)
        if not choices:
            continue
        delta = choices[0].delta
        # Reasoning tokens (extended thinking) — litellm normalizes these onto
        # ``reasoning_content`` across providers.
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield "thinking", reasoning
        content = getattr(delta, "content", None)
        if content:
            yield "response", content
