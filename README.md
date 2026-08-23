# claude-speak

Claude Code reads its replies out loud.

A `Stop` hook grabs Claude's last message, strips everything that sounds terrible
spoken (code fences, tables, file paths, emoji), and pipes it to a TTS backend.
One skill controls all of it from inside Claude: `/speak`.

```
/speak                  # what's it set to?
/speak off              # quiet
/speak mode prose       # read the whole reply, not just the gist
/speak voice Puck       # different voice
/speak lang pt          # Portuguese

/speak repeat           # say that again
/speak repeat all       # the whole reply this time
/speak repeat slow      # ...slower
/speak repeat 3         # three replies back
/speak say hello there  # speak arbitrary words
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

The installer updates existing `skills/` symlinks in place — including dropping
links to skills it no longer ships, which is how the old separate `/repeat` skill
goes away on upgrade. A running session only enumerates slash commands at startup,
so restart once for the change to show.

## Gemini API key

Of the backends that ship today, only `gemini` needs a key — `say` and `kokoro`
need nothing, and any backend failure falls back to `say`, so the tool works
before you set this up. Future hosted backends will document their own keys
under their own heading; nothing here is a shared credential.

Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey),
then pick one of two places for it:

**Environment variable** (preferred — keeps the key out of every file):

```bash
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.zshrc
```

Claude Code passes its environment to hooks, so restart your shell *and* Claude
Code afterwards. This is also the variable `gemini` CLI and most Google SDKs
already use, so you may have it set.

**Or in the config file**, if you'd rather not touch your shell profile:

```json
{ "gemini_api_key": "your-key-here" }
```

in `~/.claude-speak/config.json`. That file lives outside this repo and is
created by the installer, so a key there can never be committed by accident.
Nothing in the repo reads, stores, or transmits your key anywhere except to
`generativelanguage.googleapis.com`.

The env var wins if both are set. Verify with:

```bash
python3 ~/.claude-speak/bin/speakctl.py test
```

If the key is missing you'll hear the sample in the macOS voice instead of the
Gemini one, with the reason on stderr.

## Modes

How much of the reply gets spoken:

| mode | what you hear |
|---|---|
| `brief` | first sentence + any closing question, ~220 chars (default) |
| `prose` | the whole reply, cleaned, ~600 chars |
| `smart` | a cheap Gemini call rewrites it into one spoken sentence |
| `off` | nothing |

## Backends

Switch with `/speak use <name>` — or `/speak gemini`, naming it directly.
`backend`, `provider` and `engine` all work as aliases for `use`.

```
/speak use kokoro       # or: /speak kokoro
/speak                  # confirm which one is active
```

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
speakctl use gemini|say|kokoro      # aliases: backend, provider, engine
speakctl voice <name>               # voice for the active backend
speakctl voices                     # list available voices
speakctl model <id>                 # Gemini TTS model
speakctl style <text>               # "" clears
speakctl lang pt|en
speakctl test [text]
speakctl stop                       # kill playback
speakctl reset
```

Replay lives under `repeat` (alias: `again`), so `mode brief` — a setting — never
collides with `repeat brief` — a one-off re-shaping:

```
speakctl repeat                     # last spoken line again, verbatim
speakctl repeat all                 # the full last reply, uncapped
speakctl repeat brief|prose|smart   # re-shape the last reply
speakctl repeat slow                # slower delivery
speakctl repeat <n>                 # n replies back (1 = last)
speakctl repeat list                # recent replies, without speaking
speakctl repeat show [cmd]          # print instead of speaking
speakctl say <words>                # speak arbitrary text
```

It lives in `~/.claude-speak/bin/`. Run it directly as
`python3 ~/.claude-speak/bin/speakctl.py <args>` — or just say what you want to
Claude and let the `/speak` skill do the mapping.

## Config

`~/.claude-speak/config.json`. Everything the CLI sets, plus a few knobs it
doesn't: `max_chars_prose`, `max_chars_brief`, `summarizer_model`,
`gemini_api_key` (if you'd rather not use the env var).

Override the location with `CLAUDE_SPEAK_HOME`.

## How it works

- `stop-hook.py` — reads the hook payload, waits for the turn's closing assistant
  message to reach the transcript, de-dupes against the previously spoken one,
  shapes, speaks. Always exits 0 — a broken speaker must never break a turn.
- `speak.py` — markdown cleanup, mode shaping, backend routing, playback, and the
  one-clip audio cache.
- `transcript.py` — locates this session's JSONL transcript and reads assistant
  turns out of it (subagent turns skipped).
- `speakctl.py` — the CLI behind `/speak`; `repeat.py` backs its replay commands.
- `skills/speak/SKILL.md` — teaches Claude to map "stop talking" / "different
  voice" / "say that again, slower" onto the right command.

Claude Code appends that closing message to the transcript *while the hook is
already running*, so reading the file once loses a race about half the time and
comes back with the previous reply — and, since the de-dupe hash lagged with it,
every following turn stayed one behind. The hook now polls (3s budget, 50ms
apart) for an assistant entry whose `uuid` it has not already handled, and says
nothing if none shows up.

The hook runs `async`, so speech never blocks a turn.

Repeating a line does not pay for it twice. Every synthesized clip is written to
`~/.claude-speak/.out.wav` and tagged in `.out.key` with the words *and* their
delivery — backend, voice, model, style. Ask for exactly that audio again and it
plays straight off disk: no API call, no cost, no wait. Measured on a 5.6s clip,
`repeat` went from 10.2s to 5.6s — the whole difference being the round trip that
no longer happens. Change the voice or the style and it re-synthesizes, as it
should. `say` writes no wav and is never cached.

Every reply is cached under `~/.claude-speak/sessions/<session-id>.json` even
while muted, so `/speak repeat` still works after `/speak off`. State is keyed by
session: run five Claude sessions at once and each `/speak repeat` replays its own
last reply, not whichever session finished most recently. Stale session files
are pruned after 30 days.

Editing these scripts takes effect immediately — the hook spawns a fresh process
each turn. Only `settings.json` changes need `/hooks` or a restart.

## License

MIT
