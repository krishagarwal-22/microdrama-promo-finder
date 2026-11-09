# Microdrama Promo Finder

Reads a microdrama screenplay (the kind in the Kuku input pack) and finds the best
**promo clips** in it — 20–60s cuts that open on a *hook* and end on a *cliffhanger* —
then ranks them so an editor can post the strongest ones first.

Built for **Problem 1** of the Kuku AI Generalist assignment.

---

## What it does

For every episode it outputs, for each promo:
- the episode and the **start/end timestamps** of every segment,
- the **hook** (what grabs you in the first 3 seconds),
- the **cliffhanger** (the unresolved moment it cuts on),
- **one line on why it works**, and a 0–100 score.

Then it ranks all promos across the whole pack.

## How it works (30-second version)

```
parse  →  score every beat  →  generate candidates  →  judge  →  dedupe + rank
(rules)   (rules: hook/cliff)   (hook-start → cliff-end,   (scorer)  (best per episode,
                                 20–60s window)                       then overall)
```

- **Parsing is deterministic.** The scripts are regular (every beat has a type,
  speaker, emotion tag and in/out timestamp), so no AI is needed to read them.
- **Finding candidates is rules-based and free.** A promo must *start* on a
  high-energy beat (shock words, hot emotion, a short punchy line) and *end* on a
  cliffhanger (an unanswered question, "cut to black", a score swell, the episode's
  end) 20–60s later.
- **Judgment is swappable.** The default `heuristic` scorer is free and offline.
  Pass `--scorer llm` to re-rank the shortlist with an API model — the model is a
  one-flag swap (see below).

## Run it

No dependencies for the core tool (pure Python 3.10+ stdlib):

```bash
python find_promos.py "/path/to/I Married a Broken Soldier. He was a Duke" --out out
```

Outputs land in `out/`:
- `promos_ranked.md` — the ranked shortlist (what an editor reads)
- `promos.json` — every promo, machine-readable
- `per_episode/epNN.md` — promos grouped by episode

### Demo UI (optional)

```bash
pip install -r requirements.txt
streamlit run app.py        # upload the episode .txt files in the browser
```

### Colab

Open `notebook.ipynb` in Google Colab, upload the scripts, run all cells.

## Swapping in a stronger model

The judgment step is isolated in `promo_finder/scorer.py`. To use an API model,
set env vars and pass `--scorer llm`:

```bash
export PROMO_LLM_PROVIDER=openai           # or anthropic
export OPENAI_API_KEY=sk-...               # or ANTHROPIC_API_KEY
export PROMO_LLM_MODEL=gpt-4o-mini         # any chat model
python find_promos.py <scripts_dir> --scorer llm --out out_llm
```

If no key is set, `LLMScorer` silently falls back to the heuristic, so a batch run
never breaks. The rules still do candidate-finding, so the LLM only judges a short
list — which is what keeps it cheap at scale.

## A note on the input pack

Kuku's scripts are confidential. This repo does **not** include them and the
Streamlit app takes uploads at runtime, so nothing private is ever committed or
hosted. Keep the pack out of git (see `.gitignore`).

## Layout

```
find_promos.py          CLI
app.py                  Streamlit demo
promo_finder/
  parse.py              screenplay -> structured beats
  signals.py            cheap per-beat hook / cliffhanger features + poetic-justice lexicon
  engine.py             candidate generation, audience-resonance layer, dedupe, ranking
  scorer.py             HeuristicScorer (free) + LLMScorer (swappable)
out/                    example raw outputs (committed for review)
PSYCH_NOTES.md          why each score exists — audience data + cited psychology
solution_doc.pdf        the 2-page write-up
```

## Why the scores are what they are
Each criterion is grounded, not guessed: the 3-second hook and 20–60s length come
from platform retention data; the cliffhanger from Loewenstein's information-gap
theory; the emotion weighting from Berger & Milkman's arousal findings; and the
**audience-resonance layer** (boosting injustice→vindication "poetic-justice" clips)
from Affective Disposition Theory, validated on 500+ female serial-drama viewers —
matching this show's romance/revenge audience. Full citations in `PSYCH_NOTES.md`.
