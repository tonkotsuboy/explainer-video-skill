#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build a HyperFrames project from script.json and the timeline written by gen_voice.py.

Writes index.html (one sub-composition slot per scene), compositions/<scene>.html and
assets/gsap.min.js into the current folder. Titles and visuals come from script.json, so a
visual-only edit needs no new voices. Run gen_voice.py again when sentences change.
Usage: uv run build_video.py [script.json] [timeline.json]
"""

import html
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FPS, W, H = 30, 1920, 1080
KINDS = {"card", "big", "step", "note", "img", "code"}
LAYOUTS = {"grid", "steps", "split"}

# Motion: short, ease-out, small distances, no bounce or loops. Seconds.
REVEAL = '{opacity:0,y:24},{opacity:1,y:0,duration:0.6,ease:"expo.out"}'
SOFT_REVEAL = '{opacity:0,y:16,scale:0.98},{opacity:1,y:0,scale:1,duration:0.7,ease:"power3.out"}'
ARROW_REVEAL = '{opacity:0,x:-12},{opacity:1,x:0,duration:0.5,ease:"power3.out"}'
STAGGER = 0.08  # between items that appear on the same sentence
FOCUS_DELAY, FOCUS_IN, FOCUS_OUT = 0.15, 0.35, 0.45
COUNT_UP = 0.9
SCENE_IN, SCENE_OUT = 0.5, 0.35
ARROW_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15M13 6l6 6-6 6" fill="none" '
    'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
NUMBER = re.compile(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$", re.DOTALL)

e = html.escape


def sec(frames: int) -> float:
    """Convert frames to seconds."""
    return round(frames / FPS, 3)


def code_size(body: str) -> int:
    """Shrink code so the longest line fits the split column and every line fits the height."""
    lines = body.split("\n")
    longest = max(sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line) for line in lines) or 1
    return int(max(17, min(34, 860 / (longest * 0.61), 600 / (len(lines) * 1.45))))


class Scene:
    """One scene: markup for the board and the tweens of its timeline."""

    def __init__(self, sc: dict, tl: dict, index: int, tones: set[str]) -> None:
        """Merge the script scene with its timeline entry."""
        self.id, self.title, self.index, self.tones = sc["id"], sc["title"], index, tones
        self.visual = sc.get("visual") or {}
        self.sentences = tl["sentences"]
        self.dur = sec(tl["durationInFrames"])
        self.starts = [sec(s["from"]) for s in self.sentences]
        self.ends = [*self.starts[1:], self.dur]
        self.js: list[str] = []
        self.seen: dict[int, int] = {}

    def fail(self, msg: str) -> None:
        """Stop with a message that names the scene."""
        sys.exit(f"{self.id}: {msg}")

    def start(self, at: int) -> float:
        """Return when an item that appears on sentence `at` starts, staggering items on the same sentence."""
        if not 0 <= at < len(self.sentences):
            self.fail(f"at={at} is out of range (0..{len(self.sentences) - 1})")
        k = self.seen.get(at, 0)
        self.seen[at] = k + 1
        return round(self.starts[at] + k * STAGGER, 3)

    def focus(self, ring: str, at: int, t: float) -> None:
        """Show a ring around the item while its sentence is narrated, then let it settle."""
        hold = max(0.0, self.ends[at] - t - FOCUS_DELAY - FOCUS_IN - FOCUS_OUT)
        self.js.append(
            f'tl.to("#{ring}",{{keyframes:[{{opacity:1,duration:{FOCUS_IN},ease:"power2.out"}},'
            f'{{opacity:1,duration:{hold:.3f}}},{{opacity:0,duration:{FOCUS_OUT},ease:"power2.inOut"}}]}},{t + FOCUS_DELAY:.3f});'
        )

    def count_up(self, el: str, value: str, t: float) -> None:
        """Count a number in a big card up from zero."""
        m = NUMBER.match(value)
        if not m:
            return
        pre, num, post = m.groups()
        digits = len(num.split(".")[1]) if "." in num else 0
        n = float(num.replace(",", ""))
        fmt = f'{{minimumFractionDigits:{digits},maximumFractionDigits:{digits},useGrouping:{str("," in num).lower()}}}'
        self.js.append(
            f'{{const el=document.getElementById("{el}"),o={{v:0}};tl.fromTo(o,{{v:0}},{{v:{n},duration:{COUNT_UP},'
            f'ease:"power3.out",onUpdate:()=>{{el.textContent={json.dumps(pre)}+o.v.toLocaleString("en-US",{fmt})'
            f"+{json.dumps(post)};}}}},{t});}}"
        )

    def item(self, it: dict, n: int, fill: bool) -> str:
        """Render one board item and add its tweens."""
        kind, at = it.get("kind", "card"), it.get("at", 0)
        if kind not in KINDS:
            self.fail(f"unknown kind {kind!r}")
        tone = it.get("tone", "blue")
        if tone not in self.tones:
            self.fail(f"unknown tone {tone!r} (theme.css has {sorted(self.tones)})")
        sid = f"{self.id}-i{n}"
        t = self.start(at)
        head = e(it.get("head", ""))
        body = e(it.get("body", ""))
        ring = f'<div class="ring" id="{sid}-ring"></div>'
        if kind == "img":
            src = it.get("src", "")
            if not Path(src).is_file():
                self.fail(f"image not found: {src}")
            inner = (
                (f'<div class="shot-label">{head}</div>' if head else "")
                + f'<div class="shot-frame"><img src="{e(src)}" alt="{head}"></div>'
                + (f'<div class="shot-source">出典 {e(it["source"])}</div>' if it.get("source") else "")
            )
            inner = f'<div class="shot">{inner}</div>'
        elif kind == "code":
            inner = (
                f'<div class="code">{f"<div class=code-head>{head}</div>" if head else ""}<div class="code-panel">'
                f'<pre class="code-body" style="font-size:{code_size(it.get("body", ""))}px">{body}</pre>{ring}</div></div>'
            )
            self.focus(f"{sid}-ring", at, t)
        elif kind == "note":
            inner = f'<div class="note">{body}</div>'
        elif kind == "big":
            value = it.get("value", "")
            inner = (
                f'<div class="card filled">{f"<div class=bh>{head}</div>" if head else ""}'
                f'<div class="bv" id="{sid}-v">{e(value)}</div>{f"<div class=bb>{body}</div>" if body else ""}{ring}</div>'
            )
            self.focus(f"{sid}-ring", at, t)
            if it.get("count", True):
                self.count_up(f"{sid}-v", value, t)
        else:
            cls = "card filled step" if kind == "step" else "card"
            inner = (
                f'<div class="{cls}">{f"<div class=ch>{head}</div>" if head else ""}'
                f'{f"<div class=cb>{body}</div>" if body else ""}{ring}</div>'
            )
            self.focus(f"{sid}-ring", at, t)
        self.js.append(f'tl.fromTo("#{sid}",{SOFT_REVEAL if kind in ("img", "code") else REVEAL},{t});')
        until = it.get("until")
        if until is not None and at <= until < len(self.sentences) - 1:
            self.js.append(
                f'tl.fromTo("#{sid}-slot",{{opacity:1}},{{opacity:0,duration:0.3,ease:"power2.out"}},{self.starts[until + 1]});'
            )
        return (
            f'<div class="slot{" fill" if fill else ""} tone-{tone}" id="{sid}-slot">'
            f'<div class="item" id="{sid}">{inner}</div></div>'
        )

    def board(self) -> str:
        """Lay out the items as a grid, steps or split."""
        if comp := self.visual.get("component"):
            return self.custom(comp)
        layout = self.visual.get("layout", "grid")
        if layout not in LAYOUTS:
            self.fail(f"unknown layout {layout!r}")
        items = list(enumerate(self.visual.get("items", [])))

        def kinds(ks: set[str]) -> list[tuple[int, dict]]:
            return [(n, it) for n, it in items if it.get("kind", "card") in ks]

        notes = kinds({"note"})
        notes_html = "".join(self.item(it, n, fill=False) for n, it in notes)
        notes_html = f'<div class="notes">{notes_html}</div>' if notes else ""
        if layout == "split":
            left = "".join(self.item(it, n, fill=True) for n, it in kinds({"img", "code"}))
            right = "".join(self.item(it, n, fill=False) for n, it in kinds({"card", "big", "step"}))
            return f'<div class="split"><div class="split-left">{left}</div><div class="split-right">{right}{notes_html}</div></div>'
        out = ""
        if steps := kinds({"step"}):
            row = ""
            for k, (n, it) in enumerate(steps):
                if k:
                    aid = f"{self.id}-a{n}"
                    row += f'<div class="arrow" id="{aid}">{ARROW_SVG}</div>'
                    self.js.append(f'tl.fromTo("#{aid}",{ARROW_REVEAL},{self.starts[it.get("at", 0)]});')
                row += self.item(it, n, fill=True)
            out += f'<div class="steps">{row}</div>'
        if grid := kinds({"card", "big", "img", "code"}):
            cells = "".join(self.item(it, n, fill=True) for n, it in grid)
            out += f'<div class="grid" style="--cols:{self.visual.get("cols", 2)}">{cells}</div>'
        return out + notes_html

    def custom(self, name: str) -> str:
        """Inline custom/<name>.html: its markup goes on the board, its <script> body joins the scene timeline.

        The script can use tl (the scene timeline), S (sentence start seconds) and E (sentence end seconds).
        """
        path = Path(f"custom/{name}.html")
        if not path.is_file():
            self.fail(f"custom scene not found: {path}")
        src = path.read_text(encoding="utf-8")
        self.js.extend(re.findall(r"<script>(.*?)</script>", src, re.DOTALL))
        return re.sub(r"<script>.*?</script>", "", src, flags=re.DOTALL)

    def html(self) -> str:
        """Return the sub-composition file for this scene."""
        board = self.board()
        caps = "".join(
            f'<div class="clip cap" id="{self.id}-cap{n}" data-start="{self.starts[n]}" '
            f'data-duration="{round(self.ends[n] - self.starts[n], 3)}" data-track-index="2">'
            f'<div class="capbox">{e(s["text"])}</div></div>'
            for n, s in enumerate(self.sentences)
        )
        audio = "".join(
            f'<audio id="{self.id}-vo{n}" src="{e(s["file"])}" data-start="{self.starts[n]}" '
            f'data-duration="{sec(s["frames"])}" data-hf-media-start-basis="local" '
            f'data-track-index="{10 + self.index}"></audio>'
            for n, s in enumerate(self.sentences)
        )
        js = "\n".join(
            [
                "const tl = gsap.timeline({ paused: true });",
                f"const S = {json.dumps(self.starts)}, E = {json.dumps(self.ends)};",
                f'tl.fromTo("#{self.id}-inner",{{opacity:0,y:16}},{{opacity:1,y:0,duration:{SCENE_IN},ease:"power3.out"}},0);',
                (
                    f'tl.fromTo("#{self.id}-content",{{opacity:1}},{{opacity:0,duration:{SCENE_OUT},ease:"power2.in"}},'
                    f"{round(self.dur - SCENE_OUT - 0.05, 3)});"
                ),
                *self.js,
                f'window.__timelines["{self.id}"] = tl;',
            ]
        )
        return f"""<template id="{self.id}-template">
<div data-composition-id="{self.id}" data-width="{W}" data-height="{H}" data-duration="{self.dur}">
<div class="scene"><div class="content" id="{self.id}-content"><div class="inner" id="{self.id}-inner">
<div class="head"><div class="badge">{self.index}</div><div class="title">{e(self.title)}</div></div>
<div class="board">{board}</div>
</div>{caps}</div>{audio}</div>
<script>
{js}
</script>
</div>
</template>
"""


def main() -> None:
    """Write the HyperFrames project into the current folder."""
    script_path, timeline_path = ([*sys.argv[1:], "script.json", "timeline.json"])[:2]
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))
    timeline = {s["id"]: s for s in json.loads(Path(timeline_path).read_text(encoding="utf-8"))}
    theme = (ASSETS / "theme.css").read_text(encoding="utf-8")
    tones = set(re.findall(r"^\.tone-([a-z0-9-]+)", theme, re.MULTILINE))
    gsap = Path("node_modules/gsap/dist/gsap.min.js")
    if not gsap.is_file():
        sys.exit("node_modules/gsap not found. Run: npm i -D hyperframes gsap")
    Path("assets").mkdir(exist_ok=True)
    shutil.copy(gsap, "assets/gsap.min.js")
    comps = Path("compositions")
    if comps.exists():
        shutil.rmtree(comps)
    comps.mkdir()

    slots, settled, t = [], [], 0.0
    for i, sc in enumerate(script["scenes"], 1):
        tl = timeline.get(sc["id"])
        if tl is None or [s["text"] for s in tl["sentences"]] != sc["sentences"]:
            sys.exit(f"{sc['id']}: sentences differ from {timeline_path}. Run gen_voice.py again.")
        scene = Scene(sc, tl, i, tones)
        (comps / f"{sc['id']}.html").write_text(scene.html(), encoding="utf-8")
        slots.append(
            f'<div class="clip" id="el-{sc["id"]}" data-composition-id="{sc["id"]}" '
            f'data-composition-src="compositions/{sc["id"]}.html" data-start="{round(t, 3)}" '
            f'data-duration="{scene.dur}" data-track-index="1" data-width="{W}" data-height="{H}"></div>'
        )
        settled.append(f"{t + scene.starts[-1] + 1.2:.1f}")  # every item of the scene is on screen
        t += scene.dur
    base = (ASSETS / "base.css").read_text(encoding="utf-8")
    Path("index.html").write_text(
        f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={W}, height={H}">
<script src="assets/gsap.min.js"></script>
<style>
{theme}
{base}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{round(t, 3)}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
{chr(10).join(slots)}
</div>
<script>
window.__timelines["main"] = gsap.timeline({{ paused: true }});
</script>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(f"{len(slots)} scenes, {round(t / 60, 2)} min -> index.html")
    print(f"snapshot --at {','.join(settled)}")


if __name__ == "__main__":
    main()
