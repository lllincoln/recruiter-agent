"""resumekit command-line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from resumekit import ui
from resumekit.settings import settings
from resumekit.explore import build_profile

load_dotenv()

app = typer.Typer(
    add_completion=False,
    help="📄 ResumeKit — Evaluate and improve your resume.",
    rich_markup_mode="rich",
)


@app.command()
def score(
    resume: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Path to the resume PDF."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override scoring model (litellm format)."
    ),
    role: Optional[str] = typer.Option(
        None, "--role", "-r", help="Role to be graded against (matches a roles/ file)."
    ),
):
    """Explore a resume and score the candidate."""
    if model:
        settings.model = model

    from resumekit.scoring import capabilities, list_roles, score_stream  # lazy

    selected = _pick_role(list_roles(), role)

    # --- Phase 1: exploration (no AI) ---
    ui.console.rule("[bold bright_magenta]1 · Exploration[/bold bright_magenta]")
    profile = build_profile(resume)
    ui.render_profile_summary(profile)

    # --- Phase 2: scoring (AI, configurable model) ---
    ui.console.rule("[bold bright_magenta]2 · Scoring[/bold bright_magenta]")
    ui.step(
        "🤖",
        f"Scoring as [bold]{selected.name}[/bold] with [bold]{settings.model}[/bold] …",
        ui.ACCENT,
    )
    for msg in capabilities().warnings():
        ui.warn(msg)

    try:
        ui.render_score_stream(score_stream(profile, selected, resume))
    except Exception as e:  # noqa: BLE001
        ui.console.print(f"[bold bright_red]Scoring failed:[/bold bright_red] {e}")
        raise typer.Exit(code=1)


def _pick_role(roles, requested):
    """Resolve the role to score against, prompting interactively if needed."""
    if not roles:
        ui.console.print(
            f"[bold bright_red]No roles found in[/bold bright_red] {settings.roles_dir}"
        )
        raise typer.Exit(code=1)

    if requested:
        for r in roles:
            if r.name.lower() == requested.lower():
                return r
        ui.console.print(f"[bold bright_red]Unknown role:[/bold bright_red] {requested}")
        raise typer.Exit(code=1)

    if len(roles) == 1:
        return roles[0]

    ui.console.print("[bold bright_magenta]Select a role to be graded against:[/bold bright_magenta]")
    for i, r in enumerate(roles, 1):
        ui.console.print(f"  [cyan]{i}[/cyan]. {r.name}")
    choice = typer.prompt("Role", type=int, default=1)
    if not 1 <= choice <= len(roles):
        ui.console.print("[bold bright_red]Invalid selection.[/bold bright_red]")
        raise typer.Exit(code=1)
    return roles[choice - 1]


@app.command()
def config():
    """Show the current configuration."""
    ui.banner()
    redacted = settings.model_dump()
    
    if redacted.get("github_token"):
        redacted["github_token"] = "***set***"

    ui.console.print_json(json.dumps(redacted, default=str))


def main() -> None:
    app()
