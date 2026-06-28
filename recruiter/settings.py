"""Runtime configuration for recruiter, loaded from env / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROLES_DIR = Path(__file__).parent.parent / "roles"


class Settings(BaseSettings):
    """All tunable knobs. Reads from environment and a local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="RECRUITER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Scoring model (routed through litellm; provider-agnostic) ---
    # e.g. "anthropic/claude-opus-4-8", "gemini/gemini-2.5-pro",
    #      "ollama/llama3.1", "openrouter/openai/gpt-4o"
    model: str = "anthropic/claude-opus-4-8"
    temperature: float = 1.0
    max_tokens: int = 32000

    # Extended thinking: the model reasons before answering. "high" => think hard.
    reasoning_effort: str = "high"

    # Directory of role prompts (one markdown file per role). The user picks which
    # role to be graded against; the file's contents become the scoring prompt.
    roles_dir: Path = ROLES_DIR

    # --- GitHub ---
    # A PAT with private-repo scope is strongly recommended for a full picture.
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    # --- Crawler ---
    crawl_depth: int = 3
    crawl_max_pages: int = 40
    request_timeout: float = 20.0
    max_concurrency: int = 8
    user_agent: str = "recruiter-agent/1.0 (+https://github.com/lllincoln/recruiter-agent)"

    # --- Per-host rate limiting (requests/sec) ---
    host_rate_per_sec: float = 4.0  # generic web hosts
    github_rate_per_sec: float = 10.0  # api.github.com (also honors RL headers)

    # --- GitHub depth ---
    github_max_repos: int = 500  # cap on repos pulled from the list endpoint
    github_deep_all_repos: bool = True  # deep-fetch every repo (languages, README…)
    github_max_contributions: int = 50  # cap per contribution kind (commits/PRs/issues)


settings = Settings()
