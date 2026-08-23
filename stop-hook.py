#!/usr/bin/env python3
"""Stop hook: speaks Claude's last message.

Reads the hook payload on stdin, waits for the turn's final assistant message
to reach the transcript, shapes it per the configured mode, and hands it to
speak.py.
Always exits 0 -- a broken speaker must never break a turn.
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speak as tts  # noqa: E402
import transcript  # noqa: E402

SETTLE_TIMEOUT = 3.0   # seconds to wait for the turn's last message to land
POLL_INTERVAL = 0.05


def await_reply(path, seen_uuid, timeout=SETTLE_TIMEOUT, interval=POLL_INTERVAL):
    """The turn's closing message, once the transcript actually holds it.

    Claude Code appends that message while this hook is already running, so a
    single read races the writer and comes back with the *previous* reply.
    Poll until an unseen one shows up instead of speaking a stale turn.
    """
    deadline = time.time() + timeout
    while True:
        entry = transcript.latest_assistant_entry(path)
        fresh = entry and entry["text"].strip() and entry["uuid"] != seen_uuid
        if fresh or time.time() >= deadline:
            return entry if fresh else None
        time.sleep(interval)


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
    entry = await_reply(path, tts.load_state(sid).get("uuid"))
    if not entry:
        return
    raw = entry["text"]

    # Cache before the enabled check, so /speak repeat works even while muted.
    tts.cache_last(raw, "", sid, entry["uuid"])

    if not cfg.get("enabled") or cfg.get("mode") == "off":
        return
    if already_spoken(raw, sid):
        return

    line = tts.shape(raw, cfg)
    if line:
        tts.cache_last(raw, line, sid, entry["uuid"])
        tts.speak(line, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[claude-speak] {e}", file=sys.stderr)
    sys.exit(0)
