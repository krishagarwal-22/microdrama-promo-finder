#!/usr/bin/env python3
"""
find_promos.py — CLI entry point.

Usage:
    python find_promos.py <scripts_dir> [--out out] [--scorer heuristic|llm]
                          [--top 15] [--per-episode 2]

Writes to <out>/:
    promos.json          every promo (machine-readable)
    promos_ranked.md     the ranked shortlist (what an editor reads)
    per_episode/epNN.md  promos found in each episode
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from promo_finder import parse_dir, find_all, get_scorer
from promo_finder.parse import seconds_to_ts


def seg_str(p):
    return "  +  ".join(f"Ep{s.episode} {s.to_dict()['start']}–{s.to_dict()['end']}"
                        for s in p.segments)


def write_ranked_md(promos, path, top):
    lines = ["# Promo shortlist — ranked", "",
             f"Top {min(top, len(promos))} of {len(promos)} promos found across the pack. "
             "Craft score 0–100 (hook 35% · cliffhanger 30% · stands-alone 20% · intensity 15%), "
             "plus an audience-resonance layer that lifts injustice→vindication (poetic-justice) "
             "clips for this romance/revenge audience — see PSYCH_NOTES.md.",
             ""]
    for rank, p in enumerate(promos[:top], 1):
        d = p.to_dict()
        lines += [
            f"## {rank}. Ep {d['episode']} · {d['duration_s']:.0f}s · score {d['score']}",
            f"- **Clip:** {seg_str(p)}",
            f"- **Hook (first 3s):** {d['hook']}  _({d['hook_desc']})_",
            f"- **Cliffhanger (cut on):** {d['cliffhanger']}",
            f"- **Why it works:** {d['why']}",
            f"- **Episode logline:** {d['logline']}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_per_episode(promos, outdir):
    by_ep = {}
    for p in promos:
        by_ep.setdefault(p.episode, []).append(p)
    pe = outdir / "per_episode"
    pe.mkdir(parents=True, exist_ok=True)
    for ep, ps in sorted(by_ep.items()):
        lines = [f"# Episode {ep} — promos", ""]
        for p in sorted(ps, key=lambda x: x.judgment.score, reverse=True):
            d = p.to_dict()
            lines += [f"- **{seg_str(p)}** · {d['duration_s']:.0f}s · score {d['score']}",
                      f"  - hook: {d['hook']}",
                      f"  - cliff: {d['cliffhanger']}", ""]
        (pe / f"ep{ep:02d}.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts_dir")
    ap.add_argument("--out", default="out")
    ap.add_argument("--scorer", default="heuristic", choices=["heuristic", "llm"])
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--per-episode", type=int, default=2)
    args = ap.parse_args()

    episodes = parse_dir(args.scripts_dir)
    scorer = get_scorer(args.scorer)
    promos = find_all(episodes, scorer, per_episode=args.per_episode)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "promos.json").write_text(
        json.dumps({"scorer": scorer.name,
                    "n_episodes": len(episodes),
                    "n_promos": len(promos),
                    "promos": [p.to_dict() for p in promos]},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    write_ranked_md(promos, outdir / "promos_ranked.md", args.top)
    write_per_episode(promos, outdir)

    print(f"Parsed {len(episodes)} episodes; found {len(promos)} promos "
          f"(scorer={scorer.name}). Wrote -> {outdir}/")
    print(f"Top 5:")
    for i, p in enumerate(promos[:5], 1):
        d = p.to_dict()
        print(f"  {i}. Ep{d['episode']} {seg_str(p)} score {d['score']} | hook: {d['hook'][:48]}")


if __name__ == "__main__":
    main()
