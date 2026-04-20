# CommitCraft

### AI commit messages. Fully offline. No API key needed.

![CommitCraft demo](./demo.gif)

> ✨ **Works 100% offline — no API key required.** CommitCraft runs on your machine via [Ollama](https://ollama.com) by default. An Anthropic Claude provider is available if you prefer the API, but it's entirely optional.

CommitCraft reads your staged diff, asks a local or cloud AI model for 3 well-crafted commit messages, and commits the one you pick. It learns your team's style from your last 20 commits, detects breaking changes, and can even draft your PR description.

---

## 2-Minute Quickstart

### Offline (recommended — free, private)

```bash
# 1. Install Ollama and pull a chat-capable model
# https://ollama.com/download
ollama serve &
ollama pull qwen3.5:cloud

# 2. Install CommitCraft
pip install -e .

# 3. Use it in any git repo
git add <files>
cc
```

### API (Anthropic Claude)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install -e '.[anthropic]'

git add <files>
cc --provider anthropic
```

That's it. No config file required — run `cc setup` only if you want to save a default.

---

## Demo (text)

```
$ git add auth.py
$ cc

╭─ Staged (1 file) ───────────────────────────╮
│   • auth.py                                 │
╰─────────────────────────────────────────────╯
🤖 Using ollama (qwen3.5:cloud)
⠋ Crafting commit messages…

                   Commit suggestions
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Message                               ┃ Why                            ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1 │ feat: implement sha256 password …      │ Frames it as a new feature.    │
│ 2 │ fix: replace stubbed verify logic …    │ Treats the hardcoded return    │
│   │                                        │ as a bug to correct.           │
│ 3 │ refactor: add check_hash helper …      │ Highlights code organization.  │
└───┴────────────────────────────────────────┴────────────────────────────────┘
╭─ Summary ───────────────────────────────────╮
│ Replaces hardcoded verify success with      │
│ SHA256 hashing logic.                       │
╰─────────────────────────────────────────────╯

Pick 1/2/3  ·  edit  ·  regenerate  ·  quit  [1]: 2
╭─────────────────────────────────────────────╮
│ ✓ Committed: fix: replace stubbed verify …  │
╰─────────────────────────────────────────────╯
```

---

## Why CommitCraft?

| Feature                      | CommitCraft | aicommits | opencommit | gitmoji-cli |
| ---------------------------- | :---------: | :-------: | :--------: | :---------: |
| **Works fully offline**      |      ✅      |     ❌     |     ❌      |     ⚠️      |
| **No API key required**      |      ✅      |     ❌     |     ❌      |      ✅      |
| **Learns team commit style** |      ✅      |     ❌     |     ⚠️     |      ❌      |
| Multiple suggestions         |      ✅      |     ✅     |     ⚠️     |      ❌      |
| PR description generation    |      ✅      |     ❌     |     ⚠️     |      ❌      |
| Breaking-change detection    |      ✅      |     ❌     |     ❌      |      ❌      |
| Conventional Commits         |      ✅      |     ✅     |     ✅      |     ⚠️      |
| Interactive selector         |      ✅      |     ❌     |     ✅      |      ✅      |

Offline support is the biggest win — your diffs never leave your machine.

---

## Install

```bash
pip install -e .
```

Then pick a path below. **You don't need both** — either one works on its own.

### Quick start — Offline (Ollama, no API key)

```bash
# 1. Install Ollama (macOS / Linux / Windows)
#    https://ollama.com/download

# 2. Start the Ollama server
ollama serve

# 3. Pull a chat-capable model
ollama pull qwen3.5:cloud

# 4. In any git repo with staged changes:
cc
```

### Quick start — API (Anthropic Claude)

```bash
# 1. Get a key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Install the SDK (if you haven't already)
pip install anthropic

# 3. Tell CommitCraft to use it
cc --provider anthropic
# or save it as your default:
cc setup
```

---

## Usage

```bash
cc                          # default — auto-detects provider
cc --provider ollama        # force offline
cc --provider anthropic     # force API
cc --model llama3.1:8b      # override model
cc --no-smart               # skip style-learning from recent commits
cc --pr                     # also generate a PR description
cc setup                    # interactive setup wizard
cc doctor                   # diagnose setup problems
cc version
```

Environment variables:

| Variable                     | Purpose                                                    |
| ---------------------------- | ---------------------------------------------------------- |
| `ANTHROPIC_API_KEY`          | Your Anthropic API key (required for `--provider anthropic`) |
| `COMMITCRAFT_OLLAMA_MODEL`   | Override the Ollama model name                             |
| `COMMITCRAFT_OLLAMA_HOST`    | Override the Ollama server URL (default `http://localhost:11434`) |
| `COMMITCRAFT_ANTHROPIC_MODEL`| Override the Anthropic model ID                            |
| `EDITOR`                     | Editor launched on `e` (edit) — defaults to `nano` or `vi` |

---

## FAQ

**Which mode should I use — offline or API?**
- **Offline (Ollama)** — free, private, zero setup friction after install. Best for day-to-day and for anyone working with sensitive code that shouldn't leave the machine.
- **API (Anthropic)** — slightly better quality and more consistent on tricky diffs, but costs a few cents per commit and sends your diff to a third party.

Most users should start offline and switch to the API only if they want stronger output.

**Does it ever send my code anywhere?**
Not in offline mode. Ollama runs fully on localhost. In API mode, the staged diff is sent to Anthropic's API — same as any other cloud AI tool.

**What if Ollama isn't running?**
You'll see a friendly panel telling you how to start it. CommitCraft never crashes on a missing provider.

**Can I use a different Ollama model?**
Yes — `cc --model llama3.1:8b`, or set `COMMITCRAFT_OLLAMA_MODEL`, or save it via `cc setup`. Any chat-capable model works; code-tuned models (`qwen3.5:cloud`, `qwen2.5-coder`, `codellama`, `deepseek-coder`) tend to produce the best commit messages.

**What Python version do I need?**
Python 3.9+.

---

## Roadmap

- [x] Offline mode via Ollama
- [x] Anthropic Claude support
- [x] Team-style learning from recent commits
- [x] Breaking-change detection
- [x] PR description generation
- [x] Interactive setup + doctor commands
- [ ] `cc hook install` — drop-in `prepare-commit-msg` hook
- [ ] Monorepo scope detection
- [ ] OpenAI-compatible provider (for LM Studio, vLLM, etc.)
- [ ] Commit message linting against a project style file

---

## Contributing

PRs welcome. Keep the MVP small and focused — offline-first is the brand.

## License

MIT — see [LICENSE](LICENSE).

---

⭐ **Star if this saved you time.**
