#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Synthesize every sentence in script.json with AivisSpeech and write the timeline.

Writes <voice dir>/<scene>/<n>.wav and timeline.json in the current folder (the video project).
Only sentences whose spoken text, speaker or speedScale changed are synthesized again
(<voice dir>/cache.json remembers what each wav was made from); timeline.json is always rebuilt.
Readings come from the dictionaries merged with script.json readings (see yomi.py).
Usage: uv run gen_voice.py [script.json] [timeline.json] [voice dir]
"""

import hashlib
import json
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from yomi import compile_readings

BASE = "http://127.0.0.1:10101"
FPS, GAP, HEAD, TAIL = 30, 9, 15, 24  # frames: pause after a sentence, scene head, scene tail
DEFAULTS = ["script.json", "timeline.json", "assets/voice"]


def post(path: str, params: dict, body: bytes | None = None) -> bytes:
    """POST to the local AivisSpeech Engine, or exit with a message saying what to fix."""
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=body or b"", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:  # nosec B310
            return r.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        sys.exit(
            f"AivisSpeech Engine returned {err.code} for {path}: {detail}\n"
            f"Check the style ID (speaker={params.get('speaker')}) with list_speakers.py."
        )
    except OSError as err:  # URLError, refused connection, timeout
        sys.exit(f"Cannot reach AivisSpeech Engine at {BASE} ({err}). Start AivisSpeech and run again.")


def wav_seconds(b: bytes) -> float:
    """Read byteRate and the data chunk length from a RIFF header."""
    byte_rate = struct.unpack("<I", b[28:32])[0]
    i = 12
    while i < len(b):
        cid, size = b[i : i + 4], struct.unpack("<I", b[i + 4 : i + 8])[0]
        if cid == b"data":
            return size / byte_rate
        i += 8 + size
    msg = "no data chunk"
    raise ValueError(msg)


def main() -> None:
    """Generate voices and the timeline."""
    script, timeline_path, voice = (sys.argv[1:] + DEFAULTS[len(sys.argv) - 1 :])[:3]
    cfg = json.loads(Path(script).read_text(encoding="utf-8"))
    spk, speed = cfg["speaker"], cfg.get("speedScale", 1.05)
    tts_text = compile_readings(cfg.get("readings", {}))
    cache_path = Path(voice) / "cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    timeline, made, total = [], 0, 0
    for sc in cfg["scenes"]:
        Path(f"{voice}/{sc['id']}").mkdir(parents=True, exist_ok=True)
        t, items = HEAD, []
        for n, text in enumerate(sc["sentences"]):
            spoken = tts_text(text)
            key = hashlib.sha256(json.dumps([spoken, spk, speed], ensure_ascii=False).encode()).hexdigest()
            path = f"{voice}/{sc['id']}/{n:02d}.wav"
            if cache.get(path) == key and Path(path).is_file():
                wav = Path(path).read_bytes()
            else:
                q = json.loads(post("/audio_query", {"text": spoken, "speaker": spk}))
                q["speedScale"] = speed
                wav = post("/synthesis", {"speaker": spk}, json.dumps(q).encode())
                Path(path).write_bytes(wav)
                cache[path] = key
                cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
                made += 1
            total += 1
            frames = int(wav_seconds(wav) * FPS + 0.999)
            items.append({"text": text, "file": path, "from": t, "frames": frames})
            t += frames + GAP
        timeline.append({"id": sc["id"], "durationInFrames": t + TAIL, "sentences": items})
        print(sc["id"], round((t + TAIL) / FPS, 1), "s")
    Path(timeline_path).write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"synthesized {made} of {total} sentences (the rest were unchanged)")
    print("total", round(sum(s["durationInFrames"] for s in timeline) / FPS / 60, 2), "min")


if __name__ == "__main__":
    main()
