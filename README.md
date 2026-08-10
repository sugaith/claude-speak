# claude-speak

Claude Code reads its replies out loud.

A `Stop` hook grabs Claude's last message, strips everything that sounds terrible
spoken (code fences, tables, file paths, emoji), and pipes it to a TTS backend.
Control it from inside Claude with `/speak`, replay it with `/repeat`.

```
/speak                  # what's it set to?
/speak off              # quiet
/speak mode prose       # read the whole reply, not just the gist
/speak voice Puck       # different voice
/speak lang pt          # Portuguese

/repeat                 # say that again
/repeat all             # the whole reply this time
/repeat slow            # ...slower
/repeat 3               # three replies back
```

## Install

```bash
git clone https://github.com/sugaith/claude-speak.git
cd claude-speak
./install.sh
```

The installer finds every Claude Code config dir on the machine (`~/.claude`,
`$CLAUDE_CONFIG_DIR`, any `~/.claude-*`), symlinks the `/speak` skill into each,
and merges a `Stop` hook into each `settings.json` — existing hooks are preserved.
Re-running is safe. Point it at specific dirs instead with `./install.sh ~/.claude-work`.

Config and voice state live once in `~/.claude-speak/config.json`, so every config
dir speaks with the same voice.

Already-running sessions load the hook after you open `/hooks` once, or restart.

## Modes

How much of the reply gets spoken:

| mode | what you hear |
|---|---|
| `brief` | first sentence + any closing question, ~220 chars (default) |
| `prose` | the whole reply, cleaned, ~600 chars |
| `smart` | a cheap Gemini call rewrites it into one spoken sentence |
| `off` | nothing |

## Backends

| backend | quality | cost | offline |
|---|---|---|---|
| `gemini` (default) | best, prompt-steerable | ~$0.002/reply | no |
| `say` | robotic | free | yes |
| `kokoro` | decent English, weak Portuguese | free | yes |

**gemini** needs `GEMINI_API_KEY` in your environment. Measured on a typical
Claude Code reply (137 chars, ~9s of audio) with `gemini-2.5-flash-preview-tts`:
232 audio tokens at $10/1M = **$0.0023 per reply**, about $0.23 per 100 replies.
There is a free tier with lower rate limits.

**say** is macOS built-in and needs nothing. Quality jumps a lot if you download a
neural voice: System Settings → Accessibility → Spoken Content → System Voice →
Manage Voices.

**kokoro** is a local 82M-param Apache-2.0 model:

```bash
pip install kokoro soundfile
brew install espeak-ng   # required for non-English
```

Any backend failure falls back to `say` rather than going silent.

## Delivery style

Gemini takes direction:

```
/speak style Say it calm and understated:
/speak style Say it like you are reading bad news:
```

## Commands

```
speakctl status                     # current settings
speakctl on | off
speakctl mode prose|brief|smart
speakctl backend gemini|say|kokoro
speakctl voice <name>               # voice for the active backend
speakctl voices                     # list available voices
speakctl model <id>                 # Gemini TTS model
speakctl style <text>               # "" clears
speakctl lang pt|en
speakctl test [text]
speakctl stop                       # kill playback
speakctl reset
```

```
repeat                              # last spoken line again, verbatim
repeat all                          # the full last reply, uncapped
repeat brief|prose|smart            # re-shape the last reply
repeat slow                         # slower delivery
repeat <n>                          # n replies back (1 = last)
repeat list                         # recent replies, without speaking
repeat text <words>                 # speak arbitrary text
repeat show [cmd]                   # print instead of speaking
```

Both live in `~/.claude-speak/bin/`. Run them directly as
`python3 ~/.claude-speak/bin/speakctl.py <args>` — or just say what you want to
Claude and let the `/speak` and `/repeat` skills do the mapping.

## Config

`~/.claude-speak/config.json`. Everything the CLI sets, plus a few knobs it
doesn't: `max_chars_prose`, `max_chars_brief`, `summarizer_model`,
`gemini_api_key` (if you'd rather not use the env var).

Override the location with `CLAUDE_SPEAK_HOME`.

## How it works

- `stop-hook.py` — reads the hook payload, pulls the last main-thread assistant
  message out of the transcript, de-dupes against the previously spoken message,
  shapes, speaks. Always exits 0 — a broken speaker must never break a turn.
- `speak.py` — markdown cleanup, mode shaping, backend routing, playback.
- `transcript.py` — locates this session's JSONL transcript and reads assistant
  turns out of it (subagent turns skipped).
- `speakctl.py` / `repeat.py` — the CLIs behind `/speak` and `/repeat`.
- `skills/*/SKILL.md` — teach Claude to map "stop talking" / "different voice" /
  "say that again, slower" onto the right command.

The hook runs `async`, so speech never blocks a turn. Every reply is cached to
`~/.claude-speak/.last.raw.txt` even while muted, so `/repeat` still works after
`/speak off`.

## License

MIT
