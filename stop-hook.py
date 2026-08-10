#!/usr/bin/env python3
"""Stop hook: speaks Claude's last message.

Reads the hook payload on stdin, pulls the final assistant text out of the
transcript, shapes it per the configured mode, and hands it to speak.py.
Always exits 0 -- a broken speaker must never break a turn.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speak as tts  # noqa: E402

LAST_HASH_PATH = os.path.join(tts.HOME_DIR, ".last.hash")


def last_assistant_text(transcript_path):
    """Final main-thread assistant message. Subagent (sidechain) turns are skipped."""
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        return ""

    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, str):
            return content
        text = "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
        if text.strip():
            return text
    return ""


def already_spoken(text):
    """Stop also fires on /clear, resume and compact -- don't repeat ourselves."""
    os.makedirs(tts.HOME_DIR, exist_ok=True)
    digest = hashlib.sha256(text.encode()).hexdigest()
    try:
        with open(LAST_HASH_PATH) as f:
            if f.read().strip() == digest:
                return True
    except OSError:
        pass
    with open(LAST_HASH_PATH, "w") as f:
        f.write(digest)
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}

    if payload.get("stop_hook_active"):
        return

    cfg = tts.load_config()
    if not cfg.get("enabled") or cfg.get("mode") == "off":
        return

    raw = last_assistant_text(payload.get("transcript_path", ""))
    if not raw.strip() or already_spoken(raw):
        return

    line = tts.shape(raw, cfg)
    if line:
        tts.speak(line, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[tts hook] {e}", file=sys.stderr)
    sys.exit(0)
