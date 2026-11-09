"""
parse.py — Turn a Kuku microdrama screenplay (.txt) into structured beats.

The screenplays are highly regular, so parsing is deterministic (no AI needed):

    EPISODE NUMBER: Episode 1
    EPISODE LOGLINE: ...
    CONTINUITY NOTES: ...
    --- SCRIPT START ---
    SCENE 01
    Scene heading: INT. CATHEDRAL - DAY
    Scene start: 00:00.00
    Scene end: 02:18.00
    Actions and dialogue:

    **CAMERA:**
    Start: (00:00.00) | End: (00:04.80)
    <text>

    **LADY JULIANA (Confused, Breathless):**
    Start: (00:13.50) | End: (00:14.30)
    "Why?"

Timestamps run continuously inside an episode (scene 2 starts where scene 1 ends),
so a promo is simply a [start_s, end_s] interval within an episode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Block headers that are NOT spoken dialogue.
NON_DIALOGUE = {"CAMERA", "ACTION", "SOUND FX", "SFX", "MUSIC", "MONTAGE",
                "TRANSITION", "SUPER", "TITLE", "TEXT", "VOICEOVER"}

_TS = re.compile(r"\((\d{1,2}):(\d{2}(?:\.\d+)?)\)")
_HEADER = re.compile(r"^\*\*(.+?):\*\*\s*$")
_STARTEND = re.compile(r"Start:\s*\((\d{1,2}:\d{2}(?:\.\d+)?)\)\s*\|\s*End:\s*\((\d{1,2}:\d{2}(?:\.\d+)?)\)")
_SCENE = re.compile(r"^SCENE\s+(\d+)")


def ts_to_seconds(mmss: str) -> float:
    """'01:03.40' -> 63.4 seconds."""
    m, s = mmss.split(":")
    return int(m) * 60 + float(s)


def seconds_to_ts(sec: float) -> str:
    """63.4 -> '01:03.40' (the format the scripts use)."""
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:05.2f}"


@dataclass
class Beat:
    episode: int
    scene: int
    idx: int                 # running index of the beat within the episode
    kind: str                # 'dialogue' | 'camera' | 'action' | 'sfx' | 'other'
    speaker: Optional[str]   # for dialogue
    emotion: Optional[str]   # emotion tag in parentheses, e.g. "Outraged, Accusing"
    start_s: float
    end_s: float
    text: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Episode:
    number: int
    logline: str
    continuity: str
    beats: list[Beat] = field(default_factory=list)
    duration_s: float = 0.0
    source_file: str = ""


def _classify_header(header: str):
    """Return (kind, speaker, emotion) for a '**...:**' header line."""
    core = header.strip()
    # Name part is everything before the first '('.
    name = core.split("(")[0].strip().rstrip(":").strip()
    emotion = None
    paren = re.findall(r"\(([^)]*)\)", core)
    if paren:
        # Last parenthetical is usually the emotion; O.S./V.O. are delivery flags.
        for p in reversed(paren):
            if p.strip().upper() not in {"O.S.", "V.O.", "CONT'D", "OS", "VO"}:
                emotion = p.strip()
                break
    upper = name.upper()
    if upper in NON_DIALOGUE:
        kind = {"CAMERA": "camera", "ACTION": "action"}.get(upper, "sfx"
                if "SOUND" in upper or upper in {"SFX", "MUSIC"} else "other")
        return kind, None, emotion
    # Otherwise it's a character speaking.
    return "dialogue", name, emotion


def parse_episode(path: str | Path) -> Episode:
    path = Path(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    number = 0
    logline = ""
    continuity = ""
    for ln in lines[:8]:
        if ln.startswith("EPISODE NUMBER:"):
            m = re.search(r"(\d+)", ln)
            number = int(m.group(1)) if m else 0
        elif ln.startswith("EPISODE LOGLINE:"):
            logline = ln.split(":", 1)[1].strip()
        elif ln.startswith("CONTINUITY NOTES:"):
            continuity = ln.split(":", 1)[1].strip()

    ep = Episode(number=number, logline=logline, continuity=continuity,
                 source_file=path.name)

    scene = 0
    idx = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        sc = _SCENE.match(line.strip())
        if sc:
            scene = int(sc.group(1))
            i += 1
            continue
        hm = _HEADER.match(line)
        if hm:
            kind, speaker, emotion = _classify_header(hm.group(1))
            # Next non-empty line should carry Start/End.
            j = i + 1
            start_s = end_s = None
            while j < n and lines[j].strip() == "":
                j += 1
            if j < n:
                se = _STARTEND.search(lines[j])
                if se:
                    start_s = ts_to_seconds(se.group(1))
                    end_s = ts_to_seconds(se.group(2))
                    j += 1
            # Collect text until blank line or next header.
            text_lines = []
            while j < n and lines[j].strip() != "" and not _HEADER.match(lines[j]) \
                    and not _SCENE.match(lines[j].strip()):
                text_lines.append(lines[j].strip())
                j += 1
            text = " ".join(text_lines).strip().strip('"').strip()
            if start_s is not None:
                ep.beats.append(Beat(number, scene, idx, kind, speaker, emotion,
                                     start_s, end_s, text))
                idx += 1
            i = j
            continue
        i += 1

    ep.duration_s = max((b.end_s for b in ep.beats), default=0.0)
    return ep


def parse_dir(scripts_dir: str | Path) -> list[Episode]:
    scripts_dir = Path(scripts_dir)
    files = sorted(scripts_dir.glob("episode-*.txt"))
    eps = [parse_episode(f) for f in files]
    eps.sort(key=lambda e: e.number)
    return eps


if __name__ == "__main__":
    import sys, json
    eps = parse_dir(sys.argv[1])
    print(f"Parsed {len(eps)} episodes")
    for e in eps[:3]:
        print(f"  Ep {e.number}: {len(e.beats)} beats, {e.duration_s:.1f}s — {e.logline[:60]}")
