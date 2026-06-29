# 🕵️ Recruiter Agent

**An open source AI recruiter that scores your resume, tells you what's working and what isn't, for any job role.**

Point it at a resume and a role. It pulls every link off the resume, visits them, and builds a real picture of the candidate from their GitHub, personal site, blog, and more. Then it grades them against a rubric and hands back a verdict with specific strengths and fixes.

![Recruiter Agent Demo Animation](assets/recruiteragent-animation.webp)

## 🚀 Get started

### Prerequisites

- 🐍 **Python 3.13+**
- 📦 **[uv](https://docs.astral.sh/uv/)** for dependency management
- 🔑 An API key for whichever model you want to score with (anything [LiteLLM](https://docs.litellm.ai/docs/providers) routes to)

### Install

```bash
git clone https://github.com/lllincoln/recruiter-agent.git
cd recruiter-agent
uv sync
```

### Configure

Create a `.env` in the project root:

```dotenv
# The scoring model, in LiteLLM "provider/model" format.
RECRUITER_MODEL=gemini/gemma-4-31b-it

# Whichever provider key matches your model above.
ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=...
# OPENROUTER_API_KEY=...

# Optional but strongly recommended: a GitHub token.
# Without one you get 60 requests/hour and no private-repo visibility.
# A classic PAT with the `repo` scope gives the fullest picture.
GITHUB_TOKEN=...
```

### Run

```bash
uv run recruiter score path/to/resume.pdf
```

It'll ask which role to grade against (or pass `--role`). Watch the exploration tree fill in, then watch the model reason its way to a verdict.

```bash
uv run recruiter score resume.pdf --role "Software Engineer Intern (General)"
```

---

## ✨ What it does

Recruiter Agent runs in two phases.

**1. 🔍 Exploration**: Evidence gathering. It reads the resume PDF, extracts every link, and explores each one:

- 🐙 **GitHub**: real repos, stars, languages, and contributions (commits, PRs, issues) to other people's projects, pulled straight from the API.
- 🌐 **Personal sites & blogs**: crawled and read, including dev.to, Medium, Hashnode, and Substack posts.
- 📺 **YouTube**: talks and demos, transcribed.
- 📦 **More**: GitLab, Stack Overflow, Kaggle, Hugging Face, npm, and PyPI coming soon ([looking for contributions](CONTRIBUTING.md)).

**2. 🎯 Scoring**: The full evidence picture and the rendered resume pages go to an LLM, which grades the candidate against a rubric for a given role.

---

## 🎓 Roles

A **role** is the rubric the candidate gets graded against. Each one is a plain Markdown file in [`roles/`](roles/), and its contents are the scoring prompt the model follows.

This is the heart of the project, and it's deliberately just Markdown so anyone can read, fork, and improve a rubric without touching code. The bundled `[US] Software Engineer Intern (General)` role is for US-based software engineering intern roles.

Want to grade for a different role? Copy an existing file, rewrite the rubric, drop it in `roles/`. That's the whole process. We'd love for you to [contribute more roles across different industries](CONTRIBUTING.md).

---

## 🤖 Bring your own model

Scoring runs through [LiteLLM](https://docs.litellm.ai/), so you're not locked into one provider. Set `RECRUITER_MODEL` to any `provider/model` string:

| Provider | Example |
| --- | --- |
| Anthropic | `anthropic/claude-opus-4-8` |
| Google | `gemini/gemini-2.5-pro` |
| OpenRouter | `openrouter/openai/gpt-4o` |
| Ollama | `ollama/llama3.1` |

---

## 🙏 Inspiration

Recruiter Agent is inspired by [the Hacker Rank ATS](https://github.com/interviewstreet/hiring-agent), whose rubric and core idea got us started. We built this because we wanted something that produced consistent results, is easier to set up, nicer to use, modern, and open to contributions, with room to grow well past resume scoring.

---

## 🤝 Contributing

We're actively looking for contributions that elevate this project. **Don't be afraid to open an issue or otherwise get involved!**

We do ask that you open an issue before submitting a PR, so we can talk through your idea before any coding happens. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the details.

## 📄 License

[MIT](LICENSE)
