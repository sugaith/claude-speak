#!/usr/bin/env python3
"""TTS backend router. Reads text from argv or stdin, speaks it.

Backends: gemini (Gemini API), say (macOS built-in), kokoro (local model).
Config and runtime state live in $CLAUDE_SPEAK_HOME (default ~/.claude-speak),
which is shared by every Claude Code config dir the installer wires up.
"""
import base64
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
import wave

HOME_DIR = os.environ.get("CLAUDE_SPEAK_HOME") or os.path.expanduser("~/.claude-speak")
CONFIG_PATH = os.path.join(HOME_DIR, "config.json")
PID_PATH = os.path.join(HOME_DIR, ".playing.pid")
OUT_WAV = os.path.join(HOME_DIR, ".out.wav")
OUT_KEY_PATH = os.path.join(HOME_DIR, ".out.key")

DEFAULTS = {
    "enabled": True,
    "mode": "brief",            # prose | brief | smart | off
    "backend": "gemini",        # gemini | say | kokoro
    "gemini_model": "gemini-2.5-flash-preview-tts",
    "gemini_voice": "Kore",
    "summarizer_model": "gemini-2.5-flash-lite",
    "say_voice": "Samantha",
    "kokoro_voice": "af_heart",
    "kokoro_lang": "a",
    "max_chars_prose": 600,
    "max_chars_brief": 220,
    "style": "",               # e.g. "Say it calm and low-key: " (gemini only)
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


SESSIONS_DIR = os.path.join(HOME_DIR, "sessions")
STATE_TTL_DAYS = 30


def session_id(explicit=None):
    """Per-session key. Concurrent sessions must not clobber each other."""
    return explicit or os.environ.get("CLAUDE_CODE_SESSION_ID") or "default"


def _state_path(sid):
    return os.path.join(SESSIONS_DIR, sid + ".json")


def load_state(sid=None):
    try:
        with open(_state_path(session_id(sid))) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(sid=None, **fields):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sid = session_id(sid)
    state = load_state(sid)
    state.update({k: v for k, v in fields.items() if v})
    with open(_state_path(sid), "w") as f:
        json.dump(state, f)
    _prune_states()


def _prune_states():
    cutoff = time.time() - STATE_TTL_DAYS * 86400
    try:
        for name in os.listdir(SESSIONS_DIR):
            path = os.path.join(SESSIONS_DIR, name)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
    except OSError:
        pass


def cache_last(raw, spoken, sid=None, uuid=None):
    """Remember the last reply so `repeat` can replay it without the hook.

    `uuid` is the transcript entry it came from -- how the next Stop hook tells
    a fresh reply from the one it already handled.
    """
    save_state(sid, raw=raw, spoken=spoken, uuid=uuid)


def load_last(sid=None):
    """(raw_reply, spoken_line) for this session; either may be empty."""
    state = load_state(sid)
    return state.get("raw", ""), state.get("spoken", "")


def api_key():
    key = os.environ.get("GEMINI_API_KEY") or load_config().get("gemini_api_key")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set and no gemini_api_key in config.json")
    return key


# ---------------------------------------------------------------- text cleanup

FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s*")
BULLET_RE = re.compile(r"^\s*[-*+]\s+|^\s*\d+[.)]\s+")
EMPHASIS_RE = re.compile(r"\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__")
# Paths, but not slash-commands: /speak survives, /Users/me/x.py does not.
PATHY_RE = re.compile(
    r"(?<!\w)[\w.-]+(?:/[\w.-]+)*"
    r"\.(?:py|ts|tsx|js|jsx|json|md|sh|go|rs|java|yml|yaml)\b"
    r"|(?<!\w)(?:~|\.{1,2})/[\w.~/-]+"
    r"|(?<!\w)/[\w.~-]*[/.][\w.~/-]*")
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF←-⇿☀-➿⬀-⯿️]")
URL_RE = re.compile(r"https?://\S+")


def clean(text):
    """Strip everything that sounds terrible when read aloud."""
    text = FENCE_RE.sub(" ", text)
    text = URL_RE.sub(" link ", text)
    text = LINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = EMPHASIS_RE.sub(lambda m: next(g for g in m.groups() if g), text)

    lines = []
    for line in text.splitlines():
        if TABLE_ROW_RE.match(line):
            continue
        if set(line.strip()) <= {"-", "|", ":", " "} and line.strip():
            continue
        line = HEADING_RE.sub("", line)
        line = BULLET_RE.sub("", line)
        lines.append(line)
    text = "\n".join(lines)

    text = PATHY_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def to_brief(text, cap):
    """First sentence, plus a trailing question if the reply ends with one."""
    parts = [p.strip() for p in SENT_SPLIT_RE.split(text) if p.strip()]
    if not parts:
        return ""
    out = [parts[0]]
    if len(parts) > 1 and parts[-1].endswith("?"):
        out.append(parts[-1])
    return truncate(" ".join(out), cap)


def truncate(text, cap):
    if len(text) <= cap:
        return text
    cut = text[:cap]
    dot = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    return cut[: dot + 1] if dot > cap * 0.5 else cut.rstrip() + "."


def to_smart(text, cfg):
    """One spoken line via a cheap Gemini call. Falls back to brief on failure."""
    prompt = (
        "Rewrite this assistant reply as ONE short spoken sentence (max 20 words) "
        "a developer would want to hear out loud. State the outcome and any question "
        "asked. No markdown, no code, no file paths. Reply with the sentence only.\n\n"
        + text[:4000]
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{cfg['summarizer_model']}:generateContent?key={api_key()}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=25))
        parts = res["candidates"][0]["content"]["parts"]
        line = "".join(p.get("text", "") for p in parts).strip()
        return line or to_brief(text, cfg["max_chars_brief"])
    except Exception:
        return to_brief(text, cfg["max_chars_brief"])


def shape(text, cfg, mode=None):
    mode = mode or cfg["mode"]
    body = clean(text)
    if not body:
        return ""
    if mode == "prose":
        return truncate(body, cfg["max_chars_prose"])
    if mode == "smart":
        return to_smart(body, cfg)
    return to_brief(body, cfg["max_chars_brief"])


# ------------------------------------------------------------------- playback

def stop_playing():
    try:
        with open(PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def play(path):
    stop_playing()
    proc = subprocess.Popen(["afplay", path],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(PID_PATH, "w") as f:
        f.write(str(proc.pid))
    proc.wait()


WAV_BACKENDS = ("gemini", "kokoro")


def audio_key(text, cfg, backend=None):
    """Identifies the audio .out.wav holds: the words *and* their delivery.

    Voice, model and style all change how the same sentence comes out, so any
    of them changing has to miss the cache.
    """
    name = backend or cfg["backend"]
    parts = [name, text]
    if name == "gemini":
        parts += [cfg.get("gemini_voice", ""), cfg.get("gemini_model", ""),
                  cfg.get("style") or ""]
    else:
        parts += [cfg.get("kokoro_voice", ""), cfg.get("kokoro_lang", "")]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


def remember_audio(text, cfg, backend=None):
    """Tag the wav we just wrote, so an identical line can replay it."""
    try:
        with open(OUT_KEY_PATH, "w") as f:
            f.write(audio_key(text, cfg, backend))
    except OSError:
        pass


def replay(text, cfg, backend=None):
    """Play the cached wav if it is exactly this audio. True if it played.

    Saying the same line again is otherwise a second round trip to the TTS
    backend for a file already sitting on disk.
    """
    name = backend or cfg["backend"]
    if name not in WAV_BACKENDS or not os.path.exists(OUT_WAV):
        return False
    try:
        with open(OUT_KEY_PATH) as f:
            if f.read().strip() != audio_key(text, cfg, name):
                return False
    except OSError:
        return False
    play(OUT_WAV)
    return True


def write_wav(pcm, path, rate=24000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


# ------------------------------------------------------------------- backends

def speak_gemini(text, cfg):
    prompt = (cfg.get("style") or "") + text
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": cfg["gemini_voice"]}}},
        },
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{cfg['gemini_model']}:generateContent?key={api_key()}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=60))
    inline = res["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = 24000
    m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    if m:
        rate = int(m.group(1))
    write_wav(base64.b64decode(inline["data"]), OUT_WAV, rate)
    play(OUT_WAV)


def speak_say(text, cfg):
    stop_playing()
    argv = ["say", "-v", cfg["say_voice"]]
    if cfg.get("say_rate"):
        argv += ["-r", str(cfg["say_rate"])]
    proc = subprocess.Popen(argv + [text])
    with open(PID_PATH, "w") as f:
        f.write(str(proc.pid))
    proc.wait()


def speak_kokoro(text, cfg):
    try:
        import numpy as np
        from kokoro import KPipeline
    except ImportError:
        raise RuntimeError("kokoro not installed. Run: pip install kokoro soundfile "
                           "&& brew install espeak-ng")
    pipe = KPipeline(lang_code=cfg["kokoro_lang"])
    chunks = [audio for _, _, audio in pipe(text, voice=cfg["kokoro_voice"])]
    if not chunks:
        return
    audio = np.concatenate(chunks)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    write_wav(pcm, OUT_WAV, 24000)
    play(OUT_WAV)


BACKENDS = {"gemini": speak_gemini, "say": speak_say, "kokoro": speak_kokoro}


def speak(text, cfg, backend=None):
    """Speak text, falling back to macOS `say` if the chosen backend fails."""
    name = backend or cfg["backend"]
    try:
        BACKENDS[name](text, cfg)
    except Exception as e:
        if name == "say":
            raise
        print(f"[tts] {name} failed ({e}); falling back to say", file=sys.stderr)
        speak_say(text, cfg)
        return
    if name in WAV_BACKENDS:
        remember_audio(text, cfg, name)


def main():
    cfg = load_config()
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    text = text.strip()
    if not text:
        return
    speak(text, cfg)


if __name__ == "__main__":
    main()
