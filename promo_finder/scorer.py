"""
scorer.py — The swappable judgment layer.

A promo CANDIDATE (a start/end window the rules found) is handed to a Scorer that
rates it 0..100 and explains why. The default `HeuristicScorer` is free and runs
offline. `LLMScorer` is a drop-in replacement that asks a model to judge the same
four things against the same rubric — so "the model is easy to swap" is literally
one flag at the command line. If no API key is present, LLMScorer falls back to
the heuristic, so the tool never hard-fails.

Rubric (shared by both scorers), each 0..1, weighted:
    hook        0.35  does it grab in the first 3 seconds?
    cliffhanger 0.30  does it cut on something unresolved?
    standalone  0.20  does it make sense to a brand-new viewer?
    intensity   0.15  is the emotional charge high throughout?
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

WEIGHTS = {"hook": 0.35, "cliffhanger": 0.30, "standalone": 0.20, "intensity": 0.15}


@dataclass
class Judgment:
    score: float               # 0..100
    parts: dict                # the four sub-scores, 0..1
    why: str                   # one line


class HeuristicScorer:
    """Free, deterministic. Uses the candidate's pre-computed signal features."""
    name = "heuristic"

    def score(self, cand) -> Judgment:
        f = cand.features
        parts = {
            "hook": min(f["hook_raw"] / 60.0, 1.0),
            "cliffhanger": min(f["cliff_raw"] / 60.0, 1.0),
            "standalone": f["standalone"],
            "intensity": min(f["intensity"] / 100.0, 1.0),
        }
        score = 100 * sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
        why = (f"hook {parts['hook']:.2f}, cliff {parts['cliffhanger']:.2f}, "
               f"stands alone {parts['standalone']:.2f}, intensity {parts['intensity']:.2f}")
        return Judgment(round(score, 1), {k: round(v, 3) for k, v in parts.items()}, why)


# --- LLM rubric prompt (used by LLMScorer) ---------------------------------
LLM_SYSTEM = (
    "You are a social-media editor for a vertical microdrama studio. You pick 20-60s "
    "clips to post on TikTok/Reels to pull in NEW viewers. Judge one candidate clip "
    "against four criteria, each 0..1: hook (grabs in first 3s), cliffhanger (cuts on "
    "something unresolved), standalone (a stranger gets it with no context), intensity "
    "(emotional charge). Reply ONLY with JSON: "
    '{"hook":0-1,"cliffhanger":0-1,"standalone":0-1,"intensity":0-1,"why":"one short line"}.'
)


class LLMScorer:
    """
    Drop-in replacement that calls an LLM. Reads provider config from env so the
    model can be swapped without touching code:
        PROMO_LLM_PROVIDER = openai | anthropic   (default openai)
        OPENAI_API_KEY / ANTHROPIC_API_KEY
        PROMO_LLM_MODEL    = e.g. gpt-4o-mini / claude-3-5-sonnet-...
    Falls back to the heuristic score if anything is missing or errors.
    """
    name = "llm"

    def __init__(self):
        self.provider = os.getenv("PROMO_LLM_PROVIDER", "openai").lower()
        self.model = os.getenv("PROMO_LLM_MODEL",
                               "gpt-4o-mini" if self.provider == "openai"
                               else "claude-3-5-sonnet-20241022")
        self._fallback = HeuristicScorer()

    def _call(self, text: str) -> dict:
        if self.provider == "anthropic":
            import anthropic  # lazy import
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=self.model, max_tokens=200, system=LLM_SYSTEM,
                messages=[{"role": "user", "content": text}])
            return json.loads(msg.content[0].text)
        else:
            from openai import OpenAI  # lazy import
            client = OpenAI()
            r = client.chat.completions.create(
                model=self.model, temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": LLM_SYSTEM},
                          {"role": "user", "content": text}])
            return json.loads(r.choices[0].message.content)

    def score(self, cand) -> Judgment:
        has_key = (self.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY")) or \
                  (self.provider == "openai" and os.getenv("OPENAI_API_KEY"))
        if not has_key:
            return self._fallback.score(cand)
        try:
            p = self._call(cand.as_prompt())
            parts = {k: float(p.get(k, 0)) for k in WEIGHTS}
            score = 100 * sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
            return Judgment(round(score, 1), parts, str(p.get("why", ""))[:160])
        except Exception as e:  # never hard-fail a batch run
            j = self._fallback.score(cand)
            j.why += f"  [LLM fell back: {type(e).__name__}]"
            return j


def get_scorer(name: str):
    return {"heuristic": HeuristicScorer, "llm": LLMScorer}[name]()
