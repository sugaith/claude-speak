#!/usr/bin/env python3
"""Finding and reading Claude Code session transcripts.

Transcripts are JSONL, one entry per line, under
$CLAUDE_CONFIG_DIR/projects/<sanitized-cwd>/<session-id>.jsonl
"""
import glob
import json
import os


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def find_transcript():
    """This session's transcript, or the most recently touched one."""
    root = os.path.join(config_dir(), "projects")
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session:
        hits = glob.glob(os.path.join(root, "*", session + ".jsonl"))
        if hits:
            return hits[0]
    candidates = glob.glob(os.path.join(root, "*", "*.jsonl"))
    return max(candidates, key=os.path.getmtime) if candidates else None


def assistant_entries(path, limit=10, with_text=True):
    """Main-thread assistant entries, newest first, as {"uuid", "text"} dicts.

    Subagent turns are skipped. With `with_text`, so are entries carrying no
    text -- a tool call on its own.
    """
    try:
        with open(path) as f:
            lines = f.readlines()
    except (OSError, TypeError):
        return []

    out = []
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a half-written final line: the writer is still going
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text")
        if with_text and not text.strip():
            continue
        out.append({"uuid": entry.get("uuid", ""), "text": text})
        if len(out) >= limit:
            break
    return out


def assistant_messages(path, limit=10):
    """Main-thread assistant texts, newest first."""
    return [entry["text"] for entry in assistant_entries(path, limit)]


def latest_assistant_entry(path):
    """Newest main-thread assistant entry, tool-call-only ones included.

    Empty text means the turn is still mid-flight -- its closing message has
    not reached the transcript yet.
    """
    entries = assistant_entries(path, limit=1, with_text=False)
    return entries[0] if entries else None
