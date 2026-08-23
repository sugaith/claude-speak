---
name: speak
description: "Speak Claude's replies out loud (TTS), and replay them. Sub-commands: status, on, off, stop, mode prose|brief|smart, use gemini|say|kokoro, voice, voices, model, style, lang, test, reset, repeat, repeat all, repeat brief|prose|smart, repeat slow, repeat <n>, repeat list, repeat show, say <words>."
---

# Speak

A Stop hook (`~/.claude-speak/bin/stop-hook.py`) speaks the last assistant message
after every turn. This skill is the control surface for it, and for replaying
anything already said.

## How to run

Run the CLI and report its output verbatim:

```
python3 ~/.claude-speak/bin/speakctl.py <sub-command>
```

With no arguments it prints current settings. `help` prints the full command list,
`repeat help` the replay ones.

## Mapping what the user says

| User says | Command |
|---|---|
| "speak", "voice on", "talk to me" | `on` |
| "quiet", "stop talking", "voice off" | `off` |
| "shut up" (mid-playback) | `stop` |
| "read the whole thing" | `mode prose` |
| "just the gist", "one line" | `mode brief` |
| "summarize it properly" | `mode smart` |
| "switch to X", "use X", "change the model/engine" | `use gemini\|say\|kokoro` |
| "use a local/offline voice" | `use kokoro` |
| "no API calls", "use the mac voice" | `use say` |
| "which one is it using?" | *(no args)* |
| "different voice" | `voices`, then `voice <name>` |
| "speak Portuguese" | `lang pt` |
| "sound calmer/excited/etc" | `style Say it <adjective>:` |
| "test it" | `test` |
| "repeat", "say that again", "I missed that" | `repeat` |
| "read the whole thing again", "all of it" | `repeat all` |
| "slower", "I couldn't follow" | `repeat slow` |
| "summarize what you said" | `repeat smart` |
| "what did you say before that" | `repeat 2` (or `3`, ...) |
| "what have you been saying" | `repeat list` |
| "don't say it, just show me" | `repeat show` |
| "say <something>" | `say <something>` |

## Modes

- **prose** — full reply, code blocks / tables / file paths stripped, capped ~600 chars
- **brief** — first sentence plus any closing question, capped ~220 chars (default)
- **smart** — a cheap Gemini call rewrites the reply into one spoken sentence

## Backends

- **gemini** (default) — best voices, prompt-steerable via `style`, ~$0.002/reply, needs `GEMINI_API_KEY`
- **say** — macOS built-in, free, offline, automatic fallback if the others fail
- **kokoro** — local open model; needs `pip install kokoro soundfile` and `brew install espeak-ng`

If the user asks about cost or which backend to pick, the tradeoff is: gemini sounds
best and costs fractions of a cent per reply; say is free but robotic; kokoro is free
and offline but its Portuguese voices are weak.

## Notes

- Config lives at `~/.claude-speak/config.json` — edit directly for anything the CLI
  doesn't cover (`max_chars_prose`, `max_chars_brief`, `summarizer_model`).
- The hook is async, so speech never blocks a turn.
- Backend failures fall back to `say` rather than going silent.
- `repeat` with no argument replays the *spoken* line verbatim from cache — the same
  words, not a fresh shaping. `repeat brief|prose|smart` re-shape the original reply.
- Replay works even when muted: the Stop hook caches every reply regardless.
- `repeat <n>` counts main-thread replies backwards; subagent turns are skipped.
- `gemini` and `kokoro` also work as bare engine names (`speakctl kokoro`); `say` does
  not, because `say <words>` speaks them.
