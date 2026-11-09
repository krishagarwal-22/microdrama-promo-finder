"""
signals.py — Cheap, deterministic signals for every beat.

These are the free, rules-based features the engine uses to decide where a promo
should START (a hook) and END (a cliffhanger). They are intentionally simple and
transparent: every score can be traced to words in the script. The LLM scorer
(scorer.py) can later re-rank the shortlist, but these signals already do the
heavy lifting of finding candidates, which is what keeps the tool cheap at scale.
"""
from __future__ import annotations

import re
from .parse import Beat

# --- lexicons ---------------------------------------------------------------
# High-intensity emotion tags that appear in the scripts' (emotion) annotations.
HOT_EMOTIONS = {
    "outraged", "betrayed", "devastated", "horrified", "furious", "shaken",
    "desperate", "piercing", "scathing", "defiant", "triumphant", "gloating",
    "mocking", "scornful", "callous", "cruel", "vicious", "menacing", "cold",
    "shocked", "stunned", "trembling", "pleading", "accusing", "crushed",
    "incredulous", "venomous", "ominous", "commanding", "ruthless", "seething",
}

# Words/phrases in ACTION or dialogue text that signal a scroll-stopping moment.
HOOK_WORDS = [
    "slap", "slaps", "slapped", "strike", "strikes", "struck", "shove", "shoves",
    "grab", "grabs", "seize", "seizes", "collapse", "collapses", "faints",
    "gasp", "gasps", "scream", "screams", "slams", "throws", "kiss", "kisses",
    "blood", "knife", "gun", "sword", "dagger", "pregnant", "dead", "dies",
    "killed", "murder", "poison", "betray", "affair", "divorce", "reveal",
    "reveals", "unmask", "exposes", "secret", "slaughter", "chokes",
]

# Phrases that signal an UNRESOLVED moment (good place to cut a cliffhanger).
CLIFF_WORDS = [
    "cut to black", "freeze", "to be continued", "who are you", "what do you mean",
    "how long", "you knew", "i'm pregnant", "you're alive", "it's you",
    "reveals", "reveal", "unmask", "turns to see", "door opens", "footsteps",
    "a figure", "shadow", "gasps", "swells",
]

# Score weight for a beat being dialogue vs action vs camera.
KIND_WEIGHT = {"dialogue": 1.0, "action": 0.85, "sfx": 0.5, "camera": 0.15, "other": 0.3}


def _has(text: str, words) -> int:
    t = text.lower()
    return sum(1 for w in words if w in t)


def hook_score(beat: Beat) -> float:
    """How well this beat works as the FIRST 3 seconds of a promo (0..100)."""
    s = 0.0
    emo = (beat.emotion or "").lower()
    s += 22 * sum(1 for e in HOT_EMOTIONS if e in emo)
    s += 14 * _has(beat.text, HOOK_WORDS)
    # A short, punchy spoken line is a strong opener.
    if beat.kind == "dialogue":
        wc = len(beat.text.split())
        if 0 < wc <= 9:
            s += 14
        if beat.text.strip().endswith(("!", "?")):
            s += 10
    if beat.kind == "action":
        s += 6 * _has(beat.text, HOOK_WORDS)
    s *= KIND_WEIGHT.get(beat.kind, 0.3)
    return min(s, 100.0)


def cliff_score(beat: Beat, is_episode_end: bool, is_scene_end: bool) -> float:
    """How well this beat works as the LAST moment of a promo (0..100)."""
    s = 0.0
    t = beat.text.lower()
    s += 16 * _has(beat.text, CLIFF_WORDS)
    # Unanswered question left hanging.
    if beat.kind == "dialogue" and beat.text.strip().endswith("?"):
        s += 20
    # Trailing off ("...") = unresolved.
    if beat.text.strip().endswith("..."):
        s += 10
    emo = (beat.emotion or "").lower()
    s += 10 * sum(1 for e in HOT_EMOTIONS if e in emo)
    if "cut to black" in t or "freeze" in t:
        s += 30
    if beat.kind == "sfx" and ("swell" in t or "sting" in t or "drone" in t):
        s += 18
    if is_episode_end:
        s += 28          # episodes are built to end on a cliffhanger
    elif is_scene_end:
        s += 8
    return min(s, 100.0)


def named_entities(text: str) -> set[str]:
    """Rough proper-noun grab, used as a weak 'does this stand alone?' proxy."""
    return set(re.findall(r"\b[A-Z][a-z]{2,}\b", text))


# --- Audience-resonance lexicons (Affective Disposition Theory) --------------
# The US microdrama audience is documented as women ~30-60 drawn to romance and
# REVENGE. Affective Disposition Theory (Zillmann; Weber et al. 2008, tested on
# 500+ female serial-drama viewers) says enjoyment peaks on "poetic justice":
# a wronged, liked character (INJUSTICE) who is then vindicated / sees the
# villain punished (VINDICATION). We boost promos that carry that arc.
INJUSTICE = [
    "betray", "abandon", "humiliat", "accuse", "falsely", "innocent", "struck",
    "slap", "imprison", "framed", "discard", "cast aside", "you knew", "wrongly",
    "blame", "cruel", "mock", "threw me", "let me believe", "worthless", "poison",
    "liar", "lied", "no right", "how could you",
]
VINDICATION = [
    "triumph", "vengeance", "revenge", "expose", "confess", "confession", "unmask",
    "you will pay", "justice", "pay for", "regret", "ruin", "downfall", "defiant",
    "shown them", "kneel", "the truth", "i will not", "never again", "how dare",
    "avenge", "you have shown",
]


def disposition(beats) -> tuple[int, int, float]:
    """
    Count injustice and vindication markers across a window of beats and return
    (injustice, vindication, resonance_raw). A clip that carries BOTH the wrong
    and the payback (the full poetic-justice arc) gets an extra bonus.
    """
    text = " ".join((b.text or "").lower() for b in beats)
    inj = sum(text.count(w) for w in INJUSTICE)
    vin = sum(text.count(w) for w in VINDICATION)
    raw = 6 * min(inj, 3) + 7 * min(vin, 3)
    if inj > 0 and vin > 0:
        raw += 12
    return inj, vin, min(raw, 40.0)
