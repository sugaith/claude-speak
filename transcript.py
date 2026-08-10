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


def assistant_messages(path, limit=10):
    """Main-thread assistant texts, newest first. Subagent turns are skipped."""
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
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text")
        if text.strip():
            out.append(text)
            if len(out) >= limit:
                break
    return out


def last_assistant_text(path):
    msgs = assistant_messages(path, limit=1)
    return msgs[0] if msgs else ""
