#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""List the speakers and styles installed in AivisSpeech Engine.

Synthesis takes the numeric style id, not the model UUID.
Usage: uv run list_speakers.py [base url]
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:10101"

try:
    with urllib.request.urlopen(f"{BASE}/speakers", timeout=10) as r:  # nosec B310
        speakers = json.load(r)
except OSError as e:
    sys.exit(f"Cannot connect to AivisSpeech Engine at {BASE}. Is it running? {e}")
for s in speakers:
    for st in s["styles"]:
        print(f"{s['name']}\t{st['name']}\t{st['id']}")
