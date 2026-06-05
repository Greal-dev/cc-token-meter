# cc-token-meter

A tiny **status line for [Claude Code](https://claude.com/claude-code)** that shows, at the
bottom of your terminal, your live token usage and **estimated cost at public API prices** —
per turn and per session.

```
Opus 4.8 │ ctx 93K/1.0M 9% │ In 70K │ Out 1.2K │ tour $0.12 │ sess $4.20
```

No dependencies beyond Python 3.7+. One file. Works on Windows, macOS and Linux.

---

## What each field means

| Field | Meaning |
|-------|---------|
| `Opus 4.8` | Model display name (from the status line payload). |
| `ctx 93K/1.0M 9%` | **Context used**: tokens of the latest assistant message (`input + cache_read + cache_creation`) over the model's context window. Window is `1M` for models tagged `[1m]`, otherwise `200K`. Color: green `<50%`, yellow `<80%`, red above. |
| `In 70K` | **Token In** for the current turn — total billed input (fresh input **+ cache read + cache creation**), summed across every assistant step since your last real prompt. |
| `Out 1.2K` | **Token Out** for the current turn. |
| `tour $0.12` | Estimated cost of the **current turn**, computed from the token counts above at public API prices. |
| `sess $4.20` | Estimated cost of the **whole session**, computed at API prices over the transcript. |

> A "turn" spans every assistant step (including intermediate tool calls) since your last
> real user message. Because the context is **re-read from cache on every tool call**,
> `In` can reach millions on a tool-heavy turn — that is the volume actually billed, which
> is why it stays consistent with the cost shown next to it.

---

## How it works

Claude Code feeds status-line commands a small JSON object on **stdin** (model, transcript
path, session cost…). `statusline.py`:

1. Reads that JSON.
2. Seeks the **tail** of the session transcript `.jsonl` (no full read — fast even on 25 MB+ files, ~0.3 s).
3. Sums the `usage` blocks of assistant messages to derive context, per-turn In/Out, and cost.
4. Prints a single colored line.

Cost is computed locally from the token counts and a pricing table — see
[Configuration](#configuration).

---

## Install

### 1. Get the script

Download `statusline.py` somewhere stable, e.g.:

- **Windows**: `C:\Users\<you>\.claude\statusline.py`
- **macOS / Linux**: `~/.claude/statusline.py`

```bash
curl -o ~/.claude/statusline.py \
  https://raw.githubusercontent.com/Greal-dev/cc-token-meter/main/statusline.py
```

### 2. Wire it into Claude Code

Add a `statusLine` block to your Claude Code **`settings.json`**
(`~/.claude/settings.json`, or `%USERPROFILE%\.claude\settings.json` on Windows).

**macOS / Linux** (system Python on PATH):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py",
    "padding": 0
  }
}
```

**Windows** — Claude Code runs status-line commands through Git Bash. Reference the Python
**executable** with a Git-Bash path (`/c/...`) but pass the **script** as a native Windows
path with forward slashes (`C:/...`). This is the only combination that survives both the
shell and the Windows Python interpreter:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python C:/Users/<you>/.claude/statusline.py",
    "padding": 0
  }
}
```

If `python` is not on PATH (e.g. an embeddable Python), use its full path, Git-Bash style:

```json
{
  "command": "/c/Users/<you>/python312-embed/python.exe C:/Users/<you>/.claude/statusline.py"
}
```

### 3. Restart Claude Code

The status line is loaded at startup. It then appears at the bottom of every session.

---

## Configuration

Everything tunable lives at the top of `statusline.py`.

### Pricing

Prices are **USD per million tokens**, matched by substring on the model id. Edit to match
the [current Anthropic pricing](https://www.anthropic.com/pricing) or to add other tiers:

```python
PRICING = {
    "opus":   {"in": 15.0, "out": 75.0, "cw": 18.75, "cr": 1.50},
    "sonnet": {"in": 3.0,  "out": 15.0, "cw": 3.75,  "cr": 0.30},
    "haiku":  {"in": 1.0,  "out": 5.0,  "cw": 1.25,  "cr": 0.10},
}
```

`in` = fresh input · `out` = output · `cw` = cache write (5 min) · `cr` = cache read.

### Context window

`1M` is used when the model id contains `1m`, otherwise `200K`. Adjust `context_window()`
if you need other defaults.

### Colors / layout

The line is plain ANSI. Change the `CYAN`, `GREEN`, `SEP`, … constants, or the `parts`
list in `main()`, to restyle or drop fields (e.g. remove `sess`).

---

## Caveats

- **Estimates, not invoices.** Costs are derived from transcript token counts at the prices
  in the table — they will drift if Anthropic prices change or if your model isn't matched.
- **1M long-context premium is not applied.** Anthropic charges a premium above 200K tokens
  on the 1M window; this script uses flat per-million prices for simplicity.
- **Session cost** is summed over the transcript tail loaded from disk; for very large
  transcripts it falls back to the `total_cost_usd` reported by Claude Code when that value
  is higher.
- Reads only your **local** transcript files. It sends nothing anywhere.

---

## License

[MIT](LICENSE) © Aléaume Muller

Not affiliated with Anthropic. "Claude" and "Claude Code" are trademarks of Anthropic.
