#!/usr/bin/env python3
"""Replay what Claude just said. Backs `speakctl repeat` and `speakctl say`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speak as tts  # noqa: E402
import transcript  # noqa: E402

USAGE = """usage: speakctl repeat [command]

  (none)        say the last spoken line again, verbatim
  all           the full last reply, uncapped
  brief         first sentence of the last reply
  prose         the last reply, cleaned and capped
  smart         one-sentence summary of the last reply
  slow          the last spoken line, slower
  <n>           n replies back (1 = last, 2 = the one before, ...)
  back <n>      same as <n>
  list          show the last few replies without speaking
  show          print what would be spoken, without speaking it

  arbitrary words: speakctl say <words>"""

MODES = ("brief", "prose", "smart")


def nth_reply(n):
    msgs = transcript.assistant_messages(transcript.find_transcript(), limit=max(n, 1))
    if len(msgs) < n:
        sys.exit(f"only found {len(msgs)} replies in the transcript")
    return msgs[n - 1]


def last_reply():
    """Cached raw reply, falling back to the transcript."""
    raw, _ = tts.load_last()
    return raw or nth_reply(1)


def resolve(argv, cfg):
    """(text_to_speak, config_to_speak_it_with)."""
    cmd = (argv[0] if argv else "").lower()
    arg = " ".join(argv[1:]).strip()

    if not cmd:
        _, spoken = tts.load_last()
        return spoken or tts.shape(last_reply(), cfg), cfg

    if cmd == "all":
        text = tts.clean(last_reply())
        return text, cfg

    if cmd in MODES:
        return tts.shape(last_reply(), cfg, cmd), cfg

    if cmd == "slow":
        slow = dict(cfg)
        slow["style"] = "Say this slowly and clearly, with pauses: "
        slow["say_rate"] = 145
        _, spoken = tts.load_last()
        return spoken or tts.shape(last_reply(), cfg), slow

    if cmd in ("text", "say"):
        if not arg:
            sys.exit("need something to say")
        return arg, cfg

    if cmd == "back":
        cmd = arg

    if cmd.isdigit():
        return tts.shape(nth_reply(int(cmd)), cfg), cfg

    print(USAGE)
    sys.exit(1)


def run(argv):
    cfg = tts.load_config()

    if argv and argv[0].lower() in ("help", "-h", "--help"):
        print(USAGE)
        return

    if argv and argv[0].lower() == "list":
        msgs = transcript.assistant_messages(transcript.find_transcript(), limit=5)
        for i, m in enumerate(msgs, 1):
            print(f"{i}. {tts.truncate(tts.clean(m), 90)}")
        return

    show_only = bool(argv) and argv[0].lower() == "show"
    if show_only:
        argv = argv[1:]

    text, use_cfg = resolve(argv, cfg)
    if not text.strip():
        sys.exit("nothing to repeat yet")

    if show_only:
        print(text)
        return

    tts.speak(text, use_cfg)
    print(text)


if __name__ == "__main__":
    run(sys.argv[1:])
