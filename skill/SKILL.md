---
name: speak
description: Control spoken replies (TTS). Turn Claude's voice on/off, switch how much gets spoken (prose/brief/smart), change backend (Gemini/macOS say/Kokoro), pick a voice, set delivery style, or test the output. Use when the user says "speak", "talk to me", "voice on/off", "read your replies", "change the voice", "stop talking", or invokes /speak.
---

# Speak

A Stop hook (`~/.claude-suga/tts/stop-hook.py`) speaks the last assistant message after
every turn. This skill is the control surface for it.

## How to run

Run the control CLI and report its output verbatim:

```
python3 ~/.claude-suga/tts/speakctl.py <args>
```

With no arguments it prints current settings. `help` prints the full command list.

## Mapping what the user says

| User says | Command |
|---|---|
| "speak", "voice on", "talk to me" | `on` |
| "quiet", "stop talking", "voice off" | `off` |
| "shut up" (mid-playback) | `stop` |
| "read the whole thing" | `mode prose` |
| "just the gist", "one line" | `mode brief` |
| "summarize it properly" | `mode smart` |
| "use a local/offline voice" | `backend kokoro` |
| "no API calls", "use the mac voice" | `backend say` |
| "different voice" | `voices`, then `voice <name>` |
| "speak Portuguese" | `lang pt` |
| "sound calmer/excited/etc" | `style Say it <adjective>:` |
| "test it" | `test` |

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

- Config lives at `~/.claude-suga/tts/config.json` — edit directly for anything the CLI
  doesn't cover (`max_chars_prose`, `max_chars_brief`, `summarizer_model`).
- The hook is async, so speech never blocks a turn.
- Backend failures fall back to `say` rather than going silent.
