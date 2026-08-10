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
import transcript  # noqa: E402

LAST_HASH_PATH = os.path.join(tts.HOME_DIR, ".last.hash")


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
    path = payload.get("transcript_path") or transcript.find_transcript()
    raw = transcript.last_assistant_text(path)
    if not raw.strip():
        return

    # Cache before the enabled check, so /repeat works even while muted.
    tts.cache_last(raw, "")

    if not cfg.get("enabled") or cfg.get("mode") == "off":
        return
    if already_spoken(raw):
        return

    line = tts.shape(raw, cfg)
    if line:
        tts.cache_last(raw, line)
        tts.speak(line, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[claude-speak] {e}", file=sys.stderr)
    sys.exit(0)
