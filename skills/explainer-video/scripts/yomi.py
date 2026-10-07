#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Apply the shared readings dictionary and script.json readings to narration text.

Shared entries live in references/readings.json; entries in script.json win.
Run this file directly to self-check the replacement rules.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path

SHARED = Path(__file__).resolve().parent.parent / "references/readings.json"


def compile_readings(script_readings: dict[str, str], shared: dict[str, str] | None = None) -> Callable[[str], str]:
    """Return a function that replaces every key with its reading in one pass.

    Longer keys win, and ASCII-only keys match on word boundaries so PI does not hit inside API.
    """
    if shared is None:
        shared = json.loads(SHARED.read_text(encoding="utf-8")) if SHARED.exists() else {}
    table = {**shared, **script_readings}
    if not table:
        return lambda s: s

    def pattern(key: str) -> str:
        esc = re.escape(key)
        return rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])" if re.fullmatch(r"[A-Za-z0-9]+", key) else esc

    rx = re.compile("|".join(pattern(k) for k in sorted(table, key=len, reverse=True)))
    return lambda s: rx.sub(lambda m: table[m.group(0)], s)


if __name__ == "__main__":
    f = compile_readings({"Acme": "あくめ"}, {"PI": "ピーアイ", "Acme": "アクメ", "AcmeAds": "アクメアッズ", "toC": "トゥーしー"})
    cases = [
        ("API と PI", "API と ピーアイ"),
        ("AcmeAdsとAcmeの", "アクメアッズとあくめの"),
        ("BtoC と toC", "BtoC と トゥーしー"),
        ("PIPI", "PIPI"),
    ]
    for src, want in cases:
        assert f(src) == want, (src, f(src))  # nosec B101
    print("ok")
