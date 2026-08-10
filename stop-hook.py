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

def already_spoken(text, sid):
    """Stop also fires on /clear, resume and compact -- don't repeat ourselves."""
    digest = hashlib.sha256(text.encode()).hexdigest()
    if tts.load_state(sid).get("hash") == digest:
        return True
    tts.save_state(sid, hash=digest)
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}

    if payload.get("stop_hook_active"):
        return

    cfg = tts.load_config()
    sid = tts.session_id(payload.get("session_id"))
    path = payload.get("transcript_path") or transcript.find_transcript()
    raw = transcript.last_assistant_text(path)
    if not raw.strip():
        return

    # Cache before the enabled check, so /repeat works even while muted.
    tts.cache_last(raw, "", sid)

    if not cfg.get("enabled") or cfg.get("mode") == "off":
        return
    if already_spoken(raw, sid):
        return

    line = tts.shape(raw, cfg)
    if line:
        tts.cache_last(raw, line, sid)
        tts.speak(line, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[claude-speak] {e}", file=sys.stderr)
    sys.exit(0)
