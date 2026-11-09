"""
engine.py — Find and rank promo candidates.

Flow (all free/offline except the optional LLM re-rank):
    1. parse episodes            -> beats
    2. score each beat           -> hook_score, cliff_score (signals.py)
    3. generate candidates       -> for each strong HOOK beat, find the best
                                    CLIFFHANGER beat 20-60s later; window = between them
    4. compute features          -> hook, cliff, intensity, standalone
    5. judge                     -> Scorer (heuristic by default, LLM if --scorer llm)
    6. dedupe + keep best/episode -> rank everything
"""
from __future__ import annotations

from dataclasses import dataclass, field
from .parse import Episode, seconds_to_ts, Beat
from . import signals

MIN_DUR = 20.0
MAX_DUR = 60.0
HOOK_MIN = 18.0     # a beat must clear this to anchor a promo
TARGET_LO, TARGET_HI = 25.0, 45.0   # preferred length band (soft)
# Audience-resonance weight (Affective Disposition Theory). Deliberately gentle:
# it lifts injustice->vindication clips for this romance/revenge audience without
# steamrolling well-built clips whose "justice" is shown rather than keyworded.
# Tuned by hand (0.35) so verified-strong clips keep their rank — see PSYCH_NOTES.md.
RESONANCE_WEIGHT = 0.35


@dataclass
class Segment:
    episode: int
    start_s: float
    end_s: float

    @property
    def dur(self):
        return self.end_s - self.start_s

    def to_dict(self):
        return {"episode": self.episode,
                "start": seconds_to_ts(self.start_s),
                "end": seconds_to_ts(self.end_s),
                "start_s": round(self.start_s, 2),
                "end_s": round(self.end_s, 2)}


@dataclass
class Promo:
    segments: list[Segment]
    features: dict
    hook_text: str
    hook_desc: str
    cliff_text: str
    logline: str
    judgment: object = None

    @property
    def total_dur(self):
        return sum(s.dur for s in self.segments)

    @property
    def episode(self):
        return self.segments[0].episode

    def as_prompt(self) -> str:
        """Compact text handed to the LLM scorer."""
        return (f"Show logline: {self.logline}\n"
                f"Clip length: {self.total_dur:.0f}s\n"
                f"Opens with: {self.hook_desc} — \"{self.hook_text}\"\n"
                f"Ends with: \"{self.cliff_text}\"")

    def to_dict(self):
        return {
            "episode": self.episode,
            "segments": [s.to_dict() for s in self.segments],
            "duration_s": round(self.total_dur, 1),
            "score": self.judgment.score if self.judgment else None,
            "parts": self.judgment.parts if self.judgment else None,
            "hook": self.hook_text,
            "hook_desc": self.hook_desc,
            "cliffhanger": self.cliff_text,
            "why": self.judgment.why if self.judgment else None,
            "audience_resonance": {
                "injustice_markers": self.features.get("injustice"),
                "vindication_markers": self.features.get("vindication"),
                "resonance": self.features.get("resonance"),
            },
            "logline": self.logline,
        }


def _window_beats(beats, start_s, end_s):
    return [b for b in beats if b.start_s >= start_s - 0.01 and b.end_s <= end_s + 0.01]


def _standalone(win_beats, full_entities_before) -> float:
    """Weak proxy for 'a stranger understands this'. Honest about being rough."""
    if not win_beats:
        return 0.0
    first3 = win_beats[:3]
    ents_first = set().union(*[signals.named_entities(b.text) for b in first3]) if first3 else set()
    dlg = [b for b in win_beats if b.kind == "dialogue"]
    score = 0.5
    if ents_first:
        score += 0.2                     # a name is established early
    if len(dlg) >= 4:
        score += 0.15                    # enough exchange to orient a viewer
    # Penalty: opens mid-thought on a bare pronoun with nobody named yet.
    opener = (win_beats[0].text or "").strip()
    if opener[:4].lower() in ("you ", "he ", "she ", "it ", "that", "they") and not ents_first:
        score -= 0.2
    return max(0.0, min(1.0, score))


def _intensity(win_beats) -> float:
    if not win_beats:
        return 0.0
    tot = 0.0
    for b in win_beats:
        emo = (b.emotion or "").lower()
        tot += 20 * sum(1 for e in signals.HOT_EMOTIONS if e in emo)
        tot += 10 * signals._has(b.text, signals.HOOK_WORDS)
    return min(tot / max(len(win_beats), 1) * 3.0, 100.0)


def _length_bonus(dur: float) -> float:
    """Soft multiplier favouring the 25-45s sweet spot."""
    if TARGET_LO <= dur <= TARGET_HI:
        return 1.0
    if dur < TARGET_LO:
        return 0.9
    return 0.95


def generate_for_episode(ep: Episode) -> list[Promo]:
    beats = ep.beats
    if not beats:
        return []
    n = len(beats)
    last_end = ep.duration_s
    # precompute cliff scores
    cliff = []
    for i, b in enumerate(beats):
        is_ep_end = b.end_s >= last_end - 0.6
        is_scene_end = (i + 1 < n and beats[i + 1].scene != b.scene) or is_ep_end
        cliff.append(signals.cliff_score(b, is_ep_end, is_scene_end))

    cands: list[Promo] = []
    for i, hb in enumerate(beats):
        h = signals.hook_score(hb)
        if h < HOOK_MIN:
            continue
        start_s = hb.start_s
        # find best cliffhanger whose END lands 20..60s after the hook starts
        best_j, best_c = -1, -1.0
        for j in range(i, n):
            eb = beats[j]
            dur = eb.end_s - start_s
            if dur < MIN_DUR:
                continue
            if dur > MAX_DUR:
                break
            if cliff[j] > best_c:
                best_c, best_j = cliff[j], j
        if best_j < 0:
            continue
        end_s = beats[best_j].end_s
        win = _window_beats(beats, start_s, end_s)
        inj, vin, reso = signals.disposition(win)
        feats = {
            "hook_raw": h,
            "cliff_raw": best_c,
            "intensity": _intensity(win),
            "standalone": _standalone(win, None),
            "n_beats": len(win),
            "injustice": inj,
            "vindication": vin,
            "resonance": reso,
        }
        # pick a readable hook line (prefer a spoken line / action in first 3s)
        hook_text = hb.text
        hook_desc = f"{hb.kind}" + (f" · {hb.speaker}" if hb.speaker else "")
        cliff_text = beats[best_j].text
        p = Promo([Segment(ep.number, start_s, end_s)], feats,
                  hook_text, hook_desc, cliff_text, ep.logline)
        cands.append(p)
    return cands


def _overlap(a: Promo, b: Promo) -> float:
    sa, sb = a.segments[0], b.segments[0]
    lo = max(sa.start_s, sb.start_s)
    hi = min(sa.end_s, sb.end_s)
    inter = max(0.0, hi - lo)
    return inter / min(sa.dur, sb.dur) if min(sa.dur, sb.dur) else 0.0


def dedupe(cands: list[Promo], max_overlap=0.5, keep=2) -> list[Promo]:
    cands = sorted(cands, key=lambda p: p.judgment.score, reverse=True)
    kept: list[Promo] = []
    for c in cands:
        if any(_overlap(c, k) > max_overlap for k in kept):
            continue
        kept.append(c)
        if len(kept) >= keep:
            break
    return kept


def find_all(episodes: list[Episode], scorer, per_episode=2) -> list[Promo]:
    all_kept: list[Promo] = []
    for ep in episodes:
        cands = generate_for_episode(ep)
        for c in cands:
            c.judgment = scorer.score(c)
            # soft length preference, then the audience-resonance (poetic-justice) layer
            base = c.judgment.score * _length_bonus(c.total_dur)
            c.judgment.score = round(base + RESONANCE_WEIGHT * c.features["resonance"], 1)
            if c.features["injustice"] and c.features["vindication"]:
                c.judgment.why += "  [poetic-justice arc: wrong + payback]"
            elif c.features["resonance"] >= 12:
                c.judgment.why += "  [strong audience-resonance]"
        all_kept.extend(dedupe(cands, keep=per_episode))
    all_kept.sort(key=lambda p: p.judgment.score, reverse=True)
    return all_kept
