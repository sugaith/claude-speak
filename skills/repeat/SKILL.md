---
name: repeat
description: Say Claude's last reply out loud again — verbatim, in full, summarized, slower, or from further back in the conversation. Use when the user says "repeat", "say that again", "what did you say", "read it all", "slower", "I missed that", or invokes /repeat.
---

# Repeat

Replays spoken output. Pairs with `/speak`, which controls the voice itself.

## How to run

Run the CLI and report its output verbatim (it prints what it spoke):

```
python3 ~/.claude-speak/bin/repeat.py <args>
```

If that path does not exist, use the repo copy the `/speak` skill points at.

## Mapping what the user says

| User says | Command |
|---|---|
| "repeat", "say that again", "I missed that" | *(no args)* |
| "read the whole thing", "all of it" | `all` |
| "just the gist" | `brief` |
| "summarize what you said" | `smart` |
| "slower", "I couldn't follow" | `slow` |
| "what did you say before that" | `2` (or `3`, ...) |
| "what have you been saying" | `list` |
| "say <something>" | `text <something>` |
| "don't say it, just show me" | `show` |

## Notes

- No-args repeats the *spoken* line verbatim from cache — the same words, not a
  fresh shaping. `brief`/`prose`/`smart` re-shape the original reply instead.
- Works even when `/speak` is muted: the Stop hook caches every reply regardless.
- `<n>` counts main-thread replies backwards; subagent turns are skipped.
- `slow` slows delivery via Gemini style direction, or `say -r 145`.
