# Design notes — why the tool scores the way it does

Every scoring criterion maps to a named, cited reason: platform retention data for
the *structure*, and psychology for *what makes a viewer stay*. This is the
grounding behind the numbers in the code and the solution doc.

## Who the audience is (sets the whole strategy)
- US microdramas are driven by **affluent women ~30–60, especially drawn to
  romance, CEO, and revenge narratives.** — *The Micro-Drama Economy* report
  (exchange4media summary); dreamsquare "Microdrama Explained".
- **Women make up most of the microdrama audience**, and on YouTube women 35+
  heavily over-index (women 45–54 = 15.7% of microdrama streams vs 7.7% of all
  YouTube). — Digital i research (advanced-television.com, worldscreen.com); TheWrap/Similarweb.
- This show ("I Married a Broken Soldier. He was a Duke") is a betrayal→revenge
  romance — dead-center of that audience.

## The structure numbers
- **3-second hook.** TikTok treats the first 3s as a distinct ranking signal;
  ~40% of viewers swipe within it; >70% decide whether to keep watching in that
  window. — insights.ttsvibes.com; clipspeed.ai; TikTok for Business guidance.
- **20–60s clip length.** Platform sweet spot is 15–60s (15–30s ideal for
  engagement); ~72% of TikToks run under 60s and reach drops past 90s. For
  cliffhanger shorts the ending should land by ~20–45s. — shortimize.com;
  fanpagekarma 32k-video study; capcut.com.

## The psychology (what makes people stay)
- **Cliffhanger → Information-Gap Theory.** Loewenstein (1994), *Psychological
  Bulletin* 116(1):75–98. Curiosity = a "cognitive itch" from a knowledge gap;
  cliffhangers create a salient gap; the gap must be right-sized (closeable).
- **Open loop → Zeigarnik effect (1927).** Unfinished/interrupted tasks hold
  tension and stay cognitively active. *Honest caveat:* the memory claim
  replicates weakly (2025 meta-analysis finds ~no recall edge excluding
  Zeigarnik's own data), so the tool leans on the tension framing, not memory.
- **Which emotions → arousal.** Berger & Milkman (2012), "What Makes Online
  Content Viral?", *Journal of Marketing Research* 49(2):192–205. High-arousal
  emotions (awe, anger, anxiety) travel; low-arousal sadness does not.
- **Audience-resonance → Affective Disposition Theory.** Zillmann (2000);
  Raney & Bryant (2002), *Journal of Communication*; **Weber, Tamborini, Lee &
  Stipp (2008), "Soap opera exposure and enjoyment", *Media Psychology*
  11(4):462–487 — tested on 500+ female serial-drama viewers.** Enjoyment (and
  Nielsen ratings) peak on *poetic justice*: reward for the liked/wronged
  character, punishment for the disliked one. → the `disposition()` signal in
  `signals.py` boosts clips carrying an injustice→vindication arc.
- **Why it must stand alone → Narrative Transportation.** Green & Brock (2000),
  *JPSP* 79(5):701–721. Immersion makes a stranger care; it depends on
  coherent structure — scrambling events lowers it. Justifies keeping promos as
  one continuous, legible stretch.
- **Who is most susceptible.** Transportability is an individual difference
  (Dal Cin, Mazzocco & Green; need for affect, Appel & Richter 2010). A 2026
  46-country study (Malecki et al.) found women, urban, higher-SES/education,
  and more collectivist/religious people report greater transportability —
  consistent with the female-skewing microdrama audience.

## Honest limits of the resonance signal
It is keyword-based, so it can miss poetic justice that is *shown, not said*
(an aggressive weight once buried the strong Ep 18 clip; the weight was dialled
back to 0.35 so verified-good clips keep their rank). Reading *meaning* rather
than keywords is exactly the job of the swappable LLM scorer.
