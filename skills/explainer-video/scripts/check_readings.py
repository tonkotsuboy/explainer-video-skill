#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Print the kana AivisSpeech actually pronounces for each sentence in a script.

The "kana" field of audio_query echoes the input, so join accent_phrases[].moras[].text instead.
Readings come from the dictionaries merged with script.json readings (see yomi.py).
Usage: uv run check_readings.py [script.json] [scene id prefix ...]
"""

import json
import sys
from pathlib import Path

from gen_voice import post
from yomi import compile_readings


def main() -> None:
    """Print each sentence with its pronounced kana."""
    args = sys.argv[1:]
    script = args.pop(0) if args and args[0].endswith(".json") else "script.json"
    cfg = json.loads(Path(script).read_text(encoding="utf-8"))
    only = tuple(args)
    tts_text = compile_readings(cfg.get("readings", {}))
    for sc in cfg["scenes"]:
        if only and not sc["id"].startswith(only):
            continue
        for s in sc["sentences"]:
            q = json.loads(post("/audio_query", {"text": tts_text(s), "speaker": cfg["speaker"]}))
            kana = "".join("".join(m["text"] for m in ap["moras"]) for ap in q["accent_phrases"])
            print(f"{sc['id']}\t{s}\n\t{kana}")


if __name__ == "__main__":
    main()
