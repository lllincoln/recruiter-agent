# 🤝 Contributing

Thanks for being willing to contribute! We're glad you're here, and we can't wait to see your contributions!!

## 📋 Two important things


1. **Open an issue before you open a PR OR if an issue contains multiple to-do items, link that issue number in your PR.** We can talk through the idea, agree on the shape, and then you build it knowing it'll get merged.

2. **Comment to claim issues.** This also saves everyone time so we don't double up on issues. 

## 🎯 Project goals

Keep these in mind, and your contribution will fit right in:

- **Easy to start.** Clone, `uv sync`, add a key, run. Every new feature should keep that path short.
- **Score the evidence, not the assertion.** The whole point is checking claims against a candidate's real footprint. Features should sharpen that, not blur it.
- **Model-agnostic.** Scoring stays behind LiteLLM so anyone can bring their own provider.
- **A platform, not a one-off.** We want to grow well past resume scoring. Build things that others can extend.
- **Fair by design.** Scoring must never turn on a candidate's name, demographics, school, GPA, or location. Guard this carefully.

## 🛠️ Ways to contribute

### 🎓 Add a new role

The easiest way to help. A **role** is a Markdown rubric in [`roles/`](roles/), and it contains the instructions the model follows when scoring. No code required.

Copy an existing role, rewrite it for your target (backend engineer, data scientist, PM, new-grad, different location, different industry, whatever), and drop it in `roles/`. Test it on a few real resumes, then send it our way. More roles make Recruiter Agent useful to more people on day one.

### 🔍 Improve exploration

The exploration phase turns a resume into evidence. Make it richer or more reliable:

- Add a handler for a source we don't cover yet (see [`recruiter/handlers/`](recruiter/handlers/)).
- Pull more information from a source we already explore.
- Make the crawler more efficient or better at finding the right pages.

### 🎨 Improve the experience

The CLI uses [Rich](https://github.com/Textualize/rich), and good UX is a priority. Sharper output, clearer errors, better progress views, and friendlier prompts are all valued.

### ⚡ Improve what's here

Tighten the scoring prompt flow, handle edge cases in PDF extraction, improve how capabilities get detected, or make the streamed output read better.

### 📋 Work on an issue

Browse the [open issues](https://github.com/lllincoln/recruiter-agent/issues). Anything tagged `good first issue` is a solid place to start. Comment to claim it so we don't double up.

### 🚀 Add a new feature

Got a bigger idea? Open an issue and pitch it. We're especially interested in features that push Recruiter Agent toward being a broader, open hiring platform.

### 🧹 Simplify and refactor

Clean code is a feature. Cut a dependency, simplify a module, or untangle something gnarly. Find places where the code is hard to read and make them more readable. These PRs are always welcome, but open an issue first so we can confirm the direction.

## 💻 Dev setup

```bash
git clone https://github.com/lllincoln/recruiter-agent.git
cd recruiter-agent
uv sync
cp .env.example .env   # then fill in your keys
uv run recruiter-agent score some-resume.pdf
```

Recruiter Agent uses Python 3.13 and manages everything with [uv](https://docs.astral.sh/uv/).

## ❓ Questions

Open an issue with the `question` label, or start a discussion.