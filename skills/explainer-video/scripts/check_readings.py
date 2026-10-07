#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Print the kana AivisSpeech actually pronounces for each sentence in a script.

The "kana" field of audio_query echoes the input, so join accent_phrases[].moras[].text instead.
Readings come from references/readings.json merged with script.json readings (script wins).
Usage: uv run check_readings.py script.json [scene id prefix ...]
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from yomi import compile_readings

BASE = "http://127.0.0.1:10101"


def main() -> None:
    """Print each sentence with its pronounced kana."""
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    only = tuple(sys.argv[2:])
    tts_text = compile_readings(cfg.get("readings", {}))
    for sc in cfg["scenes"]:
        if only and not sc["id"].startswith(only):
            continue
        for s in sc["sentences"]:
            url = f"{BASE}/audio_query?" + urllib.parse.urlencode({"text": tts_text(s), "speaker": cfg["speaker"]})
            with urllib.request.urlopen(urllib.request.Request(url, data=b"", method="POST")) as r:  # nosec B310
                q = json.load(r)
            kana = "".join("".join(m["text"] for m in ap["moras"]) for ap in q["accent_phrases"])
            print(f"{sc['id']}\t{s}\n\t{kana}")


if __name__ == "__main__":
    main()
