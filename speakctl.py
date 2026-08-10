#!/usr/bin/env python3
"""Control CLI for the TTS Stop hook. Backs the /speak skill."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speak as tts  # noqa: E402

GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

MODES = ("prose", "brief", "smart", "off")
BACKENDS = ("gemini", "say", "kokoro")
BACKEND_CMDS = ("use", "backend", "provider", "engine")

USAGE = """usage: speakctl <command>

  status                 show current settings
  on | off               enable / disable spoken replies
  mode prose|brief|smart set how much gets spoken
  use gemini|say|kokoro  switch TTS engine (aliases: backend, provider, engine;
                         or just name it: `speakctl kokoro`)
  voice <name>           set voice for the active engine
  model <id>             set the Gemini TTS model
  style <text>           Gemini delivery style, e.g. "Say it calm:" ("" clears)
  lang pt|en             shortcut: switch voice+lang for Portuguese/English
  voices                 list voices for the active backend
  test [text]            speak a sample now
  stop                   stop playback
  reset                  restore defaults"""


def show(cfg):
    voice = {"gemini": cfg["gemini_voice"], "say": cfg["say_voice"],
             "kokoro": cfg["kokoro_voice"]}[cfg["backend"]]
    state = "on" if cfg["enabled"] and cfg["mode"] != "off" else "off"
    lines = [
        f"speech   {state}",
        f"mode     {cfg['mode']}",
        f"backend  {cfg['backend']}",
        f"voice    {voice}",
    ]
    if cfg["backend"] == "gemini":
        lines.append(f"model    {cfg['gemini_model']}")
        if cfg.get("style"):
            lines.append(f"style    {cfg['style']}")
    print("\n".join(lines))


def list_voices(cfg):
    if cfg["backend"] == "gemini":
        print("\n".join(GEMINI_VOICES))
    elif cfg["backend"] == "say":
        subprocess.run(["say", "-v", "?"])
    else:
        print("english: af_heart af_bella am_michael bf_emma bm_george\n"
              "pt-br:   pf_dora pm_alex pm_santa")


def main():
    argv = sys.argv[1:]
    cfg = tts.load_config()
    cmd = (argv[0] if argv else "status").lower()
    arg = " ".join(argv[1:]).strip()

    if cmd in ("status", "show"):
        show(cfg)
        return
    if cmd == "help":
        print(USAGE)
        return
    if cmd == "voices":
        list_voices(cfg)
        return
    if cmd == "stop":
        tts.stop_playing()
        print("playback stopped")
        return

    if cmd == "on":
        cfg["enabled"] = True
        if cfg["mode"] == "off":
            cfg["mode"] = "brief"
    elif cmd == "off":
        cfg["enabled"] = False
    elif cmd == "mode" or cmd in MODES:
        mode = cmd if cmd in MODES else arg
        if mode not in MODES:
            sys.exit(f"mode must be one of: {', '.join(MODES)}")
        cfg["mode"] = mode
        cfg["enabled"] = mode != "off"
    elif cmd in BACKEND_CMDS or cmd in BACKENDS:
        backend = cmd if cmd in BACKENDS else arg.lower()
        if backend not in BACKENDS:
            sys.exit(f"engine must be one of: {', '.join(BACKENDS)}")
        cfg["backend"] = backend
    elif cmd == "voice":
        if not arg:
            sys.exit("need a voice name")
        cfg[{"gemini": "gemini_voice", "say": "say_voice",
             "kokoro": "kokoro_voice"}[cfg["backend"]]] = arg
    elif cmd == "model":
        cfg["gemini_model"] = arg
    elif cmd == "style":
        cfg["style"] = (arg + " ") if arg else ""
    elif cmd == "lang":
        if arg.lower() in ("pt", "pt-br", "portuguese"):
            cfg["say_voice"], cfg["kokoro_voice"], cfg["kokoro_lang"] = \
                "Luciana", "pf_dora", "p"
        else:
            cfg["say_voice"], cfg["kokoro_voice"], cfg["kokoro_lang"] = \
                "Samantha", "af_heart", "a"
    elif cmd == "test":
        sample = arg or "Speech hook is live. This is how your replies will sound."
        tts.speak(sample, cfg)
        print(f"spoke via {cfg['backend']}: {sample}")
        return
    elif cmd == "reset":
        cfg = dict(tts.DEFAULTS)
    else:
        print(USAGE)
        sys.exit(1)

    tts.save_config(cfg)
    show(cfg)


if __name__ == "__main__":
    main()
