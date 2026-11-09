"""
app.py — Minimal Streamlit demo for the promo finder.

Run locally:   streamlit run app.py
Deploy free:   push this repo to GitHub, then Streamlit Community Cloud -> New app.

The app does NOT bundle Kuku's confidential input pack. You upload episode .txt
files at runtime, so nothing private is ever committed or hosted.
"""
import tempfile
from pathlib import Path

import streamlit as st

from promo_finder import parse_dir, find_all, get_scorer
from promo_finder.engine import generate_for_episode

st.set_page_config(page_title="Microdrama Promo Finder", layout="wide")
st.title("🎬 Microdrama Promo Finder")
st.caption("Reads screenplay .txt files and finds 20–60s promo clips: a hook to stop the "
           "scroll, a cliffhanger to cut on. Upload the episode scripts to begin.")

with st.sidebar:
    st.header("Settings")
    scorer_name = st.radio("Scorer", ["heuristic", "llm"],
                           help="heuristic = free & offline. llm = re-rank with an API "
                                "model (set your key as an env var; falls back to "
                                "heuristic if none).")
    per_ep = st.slider("Max promos per episode", 1, 4, 2)
    top_n = st.slider("Show top N overall", 5, 50, 15)

files = st.file_uploader("Upload episode scripts (.txt)", type="txt",
                         accept_multiple_files=True)

if files:
    with tempfile.TemporaryDirectory() as d:
        for f in files:
            # the engine globs 'episode-*.txt'
            name = f.name if f.name.startswith("episode-") else f"episode-{f.name}"
            Path(d, name).write_bytes(f.read())
        episodes = parse_dir(d)
        promos = find_all(episodes, get_scorer(scorer_name), per_episode=per_ep)

    st.success(f"Parsed {len(episodes)} episodes · found {len(promos)} promos "
               f"(scorer: {scorer_name})")

    for rank, p in enumerate(promos[:top_n], 1):
        dd = p.to_dict()
        seg = "  +  ".join(f"Ep{s.episode} {s.to_dict()['start']}–{s.to_dict()['end']}"
                           for s in p.segments)
        with st.expander(f"#{rank}  ·  Ep {dd['episode']}  ·  {dd['duration_s']:.0f}s  "
                         f"·  score {dd['score']}"):
            st.markdown(f"**Clip:** {seg}")
            st.markdown(f"**Hook (first 3s):** {dd['hook']}  _({dd['hook_desc']})_")
            st.markdown(f"**Cliffhanger:** {dd['cliffhanger']}")
            st.markdown(f"**Why:** {dd['why']}")
            st.caption(dd["logline"])
else:
    st.info("👆 Upload the `episode-*.txt` files from the input pack to see ranked promos.")
