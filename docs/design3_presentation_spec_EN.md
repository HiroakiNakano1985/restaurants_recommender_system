# Blueprint 3 — COMPLETE, BUILD-READY Slide Spec (single source of truth)

> **What this file is:** a self-contained specification from which the **entire PowerPoint can be
> generated**. Everything needed is inlined here — final on-slide text, every number, every figure
> path, placement, captions, speaker notes, and the design system. You do **not** need any other
> file to build the deck. (The companion `business_analysis_EN.md` / `_JA.md` is the long-form
> written report; all of its key content is already inlined below.)

---

# PART 0 — INSTRUCTIONS FOR THE AI THAT BUILDS THE DECK (read this first)

You are generating a finished PowerPoint pitch deck from the spec below. Do exactly this:

1. **Output a single Python script using `python-pptx`** that builds `reports/BCN_FQS_pitch.pptx`.
   - If `python-pptx` is not installed, output `pip install python-pptx` first, then the script.
   - Slide size **16:9** (`prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)`).
   - Embed figures with `slide.shapes.add_picture("<relative path from project root>", ...)`.
     **Run the script from the project root** so the `reports/...` paths resolve.
   - **Fallback:** if the user prefers, also offer the same deck as **Marp markdown** (one `---`
     per slide) embedding the same images.
2. **Copy the on-slide text verbatim** from each slide's "ON-SLIDE TEXT" block. Keep it tight — this
   is slide copy, not prose. Put the longer explanation in PowerPoint **speaker notes**
   (`slide.notes_slide.notes_text_frame.text = ...`) from the "SPEAKER NOTES" block.
3. **Do NOT invent or alter any number.** Every figure on the evidence/eval slides must trace to the
   real run (652 Barcelona restaurants / 3,249 reviews). If you cannot place a figure, leave a
   labelled placeholder box — never fabricate a chart.
4. **Use the corrected framing** (PART 1) everywhere. Never say "stars are wrong / inverted." Say
   "stars are **saturated and non-discriminative**; FQS restores discrimination."
5. **Design system:** apply the colors/fonts in PART 1 to every slide. One idea per slide. Dark
   title + closing slides; light content slides. Repeat the dual-axis motif (⭐ blue popularity vs
   🍽 green food).
6. Produce **16 core slides + 5 appendix slides** in the exact order below. Each slide's spec gives
   LAYOUT, ON-SLIDE TEXT, FIGURE (path + placement + caption), SPEAKER NOTES, GRADING LINK.

---

# PART 1 — DECK-WIDE SETTINGS

**Title:** *Beyond the Stars — A Food-Quality Recommender for Saturated Rating Markets*
**Subtitle:** *When every restaurant is 4.5★, the star stops meaning anything.*
**Audience:** an investor / a platform (Google) integration team. Convincing to BOTH technical and
business listeners.

**Rubric (drives emphasis):** Business Problem & Value Proposition **30%** · Technical Considerations
**20%** · Evaluation & Business Impact **30%** · Communication & Professionalism **20%**.
Professor's rule: *"It is not about implementing but about analysing the business application and
opportunity."* → Lead with business logic; the working prototype is the graded **"extra mile."**

**Design system**
- Aspect ratio 16:9. Margins ≥ 0.6 in.
- Colors: background-dark `#14213D`; text-on-dark `#FFFFFF`; content-bg `#FFFFFF`; text-on-light
  `#14213D`; **stars/popularity = blue `#4C72B0`**; **FQS/food = green `#55A868`**; **trap red
  `#C44E52`**; gem green `#55A868`; neutral grey `#8895A7`.
- Font: Calibri/Arial/Helvetica. Title 40pt bold · slide title 30pt bold · body 18–20pt · caption
  12pt italic grey.
- Motif: a two-axis mark (⭐ blue vs 🍽 green) on title and closing.

**THE CORRECTED FRAMING (use everywhere):**
- ✅ "Google stars are **saturated** in Barcelona — 96% of restaurants are 4.0★+, only 21 of 652 are
  below 4.0. Stars can't tell restaurants apart. **FQS restores discrimination within that tied
  band.**" (objective, provable with one histogram — complements Google, doesn't attack it)
- ❌ Never: "stars are wrong / tourist bars get 5★ / tourist districts only review ambiance." We
  **tested** the tourist-bias hypothesis and it was **FALSE** — keep it in the deck as
  "hypothesis → tested → rejected" (Slide 14); that earns credit for genuine validation.

**THE CANONICAL NUMBERS (use these exact values; do not round differently):**
- Data: **652** restaurants · **3,249** reviews · 5 districts × 10 cuisines · Google Places API
  (New) · ABSA cost ≈ **$0.17**.
- Saturation: mean **4.54★** · **96%** ≥4.0★ · **71%** ≥4.5★ · only **21/652** below 4.0.
- Spread on a common [0,1] scale: star std **0.076** vs FQS std **0.142** (**~1.9×** wider).
- **Tie-resolution (headline): 12%** of all restaurant pairs are tied on stars (25,602/211,575);
  FQS separates **45%** of them at |Δ|≥0.2 (69% at |Δ|≥0.1).
- Within district×cuisine: orderable spread star **0.21** vs FQS **0.41**.
- Concrete case: in **Gràcia**, **10 tapas bars all at 4.5★** → FQS **−0.10 to +0.95**.
- Rank churn: Kendall **τ = 0.234** (Spearman 0.326) → FQS is new information, not a rehash.
- Star↔FQS correlation: Pearson **0.448** (moderate; star range-restriction dominates).
- Yield: **31 hidden gems** (≤4.4★ but top-quartile FQS) · **56 absolute traps** (≥4.6★ but
  bottom-quartile FQS).
- Aspect coverage: food **100%** · service **99%** · ambiance **92%** · price **70%**.
- Personalization sanity: weights `{food:1.0}` reproduces the pure FQS order exactly.
- External-label attempt: Michelin matched only **4/652** (fine-dining; wrong population) → abandoned;
  evaluate with self-contained metrics.

---

# PART 2 — FIGURE INVENTORY (exact paths; all already generated)

> All paths are relative to the **project root**. The deck uses the **real-data** figures as primary
> evidence; the synthetic figures are appendix (pipeline/eval demonstration).

| # | File | What it shows | Used on |
|---|---|---|---|
| F1 | `reports/real_star_histogram.png` | Star distribution of the 652 real restaurants; 3.x band shaded (only 21 there) | Slides 1, 3, 7 |
| F2 | `reports/divmetric_fig1_saturation.png` | Two histograms side by side: Google star (saturated, std 0.076) vs FQS (spread, std 0.142) | Slide 7 (lead) |
| F3 | `reports/divmetric_fig3_tie_resolution.png` | Distribution of \|ΔFQS\| among star-tied pairs; annotations 12% tied, 45% separated at ≥0.2 | Slide 7 (headline), 11 |
| F4 | `reports/divmetric_fig2_spread_norm.png` | Violin plot: star vs FQS on the same [0,1] scale (FQS visibly wider) | Slide 7 / 11 |
| F5 | `reports/divmetric_fig4_rank_churn.png` | Scatter star-rank vs FQS-rank; Kendall τ=0.234 (points scattered = new info) | Slide 11 |
| F6 | `reports/real_fig1_star_vs_fqs.png` | Real scatter star vs FQS with the 4.5★/low-FQS "tourist trap" quadrant in red; Pearson 0.448 | Slide 7 (alt) |
| F7 | `reports/real_fig2_aspect_mention.png` | Aspect-mention rate tourist vs local districts (food 96% vs 96% — the rejected hypothesis) | Slide 14 |
| A1 | `reports/fig4_capture_rate_star_vs_fqs.png` | (synthetic) proxy-label capture rate star vs FQS — pipeline eval demo | Appendix |
| A2 | `reports/fig5_ablation_fqs.png` | (synthetic) ablation of FQS signals (time decay / cuisine norm) | Appendix |
| A3 | `reports/fig3_rerank_before_after.png` | (synthetic) before/after rerank table (gems/traps) — pipeline demo | Appendix |
| — | `reports/fig1_star_vs_fqs_scatter.png`, `reports/fig2_aspect_mention_rate.png` | (synthetic) scatter & aspect-mention — pipeline demo, optional | Appendix (optional) |

---

# PART 3 — SLIDE-BY-SLIDE SPEC (16 core slides)

### SLIDE 1 — Title  ·  LAYOUT: dark full-bleed, centered
- **ON-SLIDE TEXT:**
  - Title: **Beyond the Stars**
  - Subtitle: *A Food-Quality Recommender for Saturated Rating Markets*
  - Tagline: *"When every restaurant is 4.5★, the star stops meaning anything."*
  - Footer: team names · course · date.
- **FIGURE:** F1 `reports/real_star_histogram.png` as a faint background or a small teaser strip
  (the tall pile at 4.5★ hints stars have collapsed). Caption: none on title.
- **SPEAKER NOTES:** "This is a business proposal, not a coding demo. The core insight: in Barcelona,
  Google stars have stopped discriminating restaurants — and we can fix it."
- **GRADING:** Communication.

### SLIDE 2 — Executive Summary  ·  LAYOUT: light, 4-box strip
- **ON-SLIDE TEXT (one line each box):**
  1. **Problem** — On Google Maps in Barcelona, star ratings have **saturated**: 96% are 4.0★+, only
     21 of 652 below 4.0. Stars can't discriminate.
  2. **Evidence** — 12% of restaurant pairs are *tied* on stars; under the tie, true food quality
     ranges hugely (10 Gràcia tapas at 4.5★ → FQS −0.10…+0.95).
  3. **Solution** — A **Food Quality Score (FQS)**: ABSA isolates *food-only* sentiment and restores
     discrimination; a thin personalization layer matches your taste.
  4. **Ask** — Google integrates FQS as a **second axis** beside stars; pilot in Barcelona → tourist
     cities → global.
- **FIGURE:** none (or a tiny 4-icon strip).
- **SPEAKER NOTES:** "30-second version. Stars measure popularity; FQS measures the food. In every
  saturated market, whoever restores the signal owns the dining decision."
- **GRADING:** Business Problem (30%).

### SLIDE 3 — Business Context & Opportunity  ·  LAYOUT: light, text-left / figure-right
- **ON-SLIDE TEXT:**
  - **Reviews are the default decision layer for dining — their discriminating power IS the product.**
  - In saturated markets ratings compress to the ceiling: almost everything is 4.5★.
  - Consequence: diners can't choose on stars · good small kitchens are invisible · the platform's
    ranking value erodes.
  - **Market (illustrative — validate):** Barcelona ~12–15M overnight visitors/yr; the EU tourist-city
    cluster (Venice, Lisbon, Prague…) multiplies it. Dining is a top-3 trip expense.
- **FIGURE:** F1 `reports/real_star_histogram.png`, right half. Caption: *"652 real Barcelona
  restaurants — only 21 below 4.0★."*
- **SPEAKER NOTES:** "Present saturation as a measured finding (Slide 7), not a pet peeve. This is a
  known phenomenon (rating inflation / J-shaped distributions) — we measured it directly."
- **GRADING:** Business Problem (30%).

### SLIDE 4 — Target Users & Stakeholders  ·  LAYOUT: light, persona row + table
- **ON-SLIDE TEXT:**
  - **Primary persona — the visiting diner:** few days, 6–10 meals, no local cues, high regret per
    wrong pick; currently chooses on stars+photos and lands in traps.
  - **Secondary — the local food lover:** wants quality over hype; values hidden gems + aspect control.
  - **Stakeholder table:**

    | Stakeholder | Interest | Effect of FQS |
    |---|---|---|
    | Visiting / local diners | choose good food, avoid regret | **Win** — ties broken, traps flagged, gems surfaced |
    | High-quality small kitchens | underrated by saturated stars | **Win** — discoverability ↑ (31 gems in 652) |
    | Terrace / ambiance bars | rated for vibe, not food | **Risk** — may rank lower on the food axis |
    | Platform (Google) | trust, engagement, ad inventory | **Win** — credibility + a new discriminating feature |
    | Travel/booking apps, tourism boards | quality signal / over-tourism relief | **Win** — license (B2B2C) / redistribute flow (B2G) |
- **FIGURE:** none (table is the visual). Optionally a 2×2 winners/losers.
- **SPEAKER NOTES:** "The brief explicitly asks for stakeholders. Note we name a **loser** (ambiance
  bars) — FQS is a *second axis*, not a replacement, and ambiance weight is user-controlled (Slide
  10). Honesty about who loses earns credit."
- **GRADING:** Business Problem (30%) + Ethics.

### SLIDE 5 — Value Proposition  ·  LAYOUT: light, big quote + 3 bullets
- **ON-SLIDE TEXT:**
  - Quote: **"Stars measure popularity. FQS measures the food. When every place is 4.5★, we tell
    them apart — and rank them the way *you* care about."**
  - For **diners:** trustworthy, explainable "best food near me" that works *even when stars don't*.
  - For **good small restaurants:** discoverability they can't buy and stars don't grant.
  - For the **platform:** defends rating trust, adds a differentiator, expands the discoverable long
    tail of local advertisers.
  - **Why now/us:** rating saturation is measured & growing; LLM-ABSA is newly cheap & multilingual
    (our full run = **$0.17**); no incumbent de-biases the rating signal.
- **FIGURE:** none.
- **SPEAKER NOTES:** "Differentiation: TheFork's 2025 AI search improves *search over the same
  saturated stars* — it does not fix the signal. Our moat is framing + a working PoC + the
  de-biasing insight, not deep tech (say this honestly)."
- **GRADING:** Business Problem & Value Proposition (30%).

### SLIDE 6 — The Recommendation Task (two layers)  ·  LAYOUT: light, left-to-right diagram
- **ON-SLIDE TEXT:**
  - This is a genuine **two-layer recommender**, not a re-scorer:
  - **Layer 1 — De-biasing (the novelty):** ABSA → food-only sentiment → FQS (time-decayed,
    cuisine-normalized). Shared, user-independent quality signal.
  - **Layer 2 — Personalization (content-based):** user sets aspect weights; candidates filtered
    (cuisine/district/price/min-star) and ranked by the weighted blend.
  - **No collaborative filtering** — Places API exposes no reviewer identity (`author_id`) → no
    user×item matrix. Content-based only (also privacy-protective).
- **FIGURE:** a built diagram (no PNG needed):
  `raw reviews → [ABSA] → food/service/ambiance/price → [FQS de-bias] → [Layer 2: your weights] → ranked list`.
  Build it as pptx shapes/arrows in blue→green.
- **SPEAKER NOTES:** "Framing it as two layers is what makes it a recommender system, not a filter.
  Layer 1 is the new IP; Layer 2 proves it personalizes (Slide 10)."
- **GRADING:** Technical (20%) + Business (30%).

### SLIDE 7 — ★ CENTERPIECE — Evidence: Stars Saturated, FQS Restores Discrimination  ·  LAYOUT: light, figure-led
- **ON-SLIDE TEXT (4 findings, one line each):**
  1. **Saturation:** only **21/652** below 4.0★ (96% ≥4.0, 71% ≥4.5). Star std on [0,1] = **0.076**.
  2. **FQS recovers signal:** FQS std **0.142** (~**1.9×** wider); star↔FQS Pearson **0.448**.
  3. **Ties broken (headline):** **12%** of all pairs tie on stars; FQS separates **45%** at |Δ|≥0.2.
  4. **Concrete case:** Gràcia — **10 tapas bars all at 4.5★** → FQS **−0.10 to +0.95**.
- **FIGURE (use TWO, side by side):**
  - Left: F2 `reports/divmetric_fig1_saturation.png` — caption *"Stars pile at the ceiling; FQS
    spreads out."*
  - Right: F3 `reports/divmetric_fig3_tie_resolution.png` — caption *"12% of pairs tie on stars; FQS
    breaks 45% of them."*
  - (Optional small inset table: the 10 Gràcia tapas at 4.5★ with their FQS.)
- **SPEAKER NOTES (say the honesty notes — they earn credit):** "These show stars **don't
  discriminate** and FQS **discriminates differently** — NOT that FQS is provably 'correct' (that
  needs an external label; Slide 11/15). It's 'stars can't discriminate,' not 'stars are inverted.'
  Use **absolute** traps (genuinely low FQS), not small-group relative ones. FQS has a ceiling
  (rave-review bias); max 5 reviews/place; Google's 'most-relevant' reviews are a favorable sample."
- **GRADING:** Business Problem (30%) + Evaluation (30%). **Most important slide — most polish.**

### SLIDE 8 — Dataset & Data Strategy  ·  LAYOUT: light, 3-column flow
- **ON-SLIDE TEXT:**
  1. **What we did:** **652** real restaurants / **3,249** reviews via Google Places API (New), 5
     districts × 10 cuisines, full structured metadata (per-review rating, text, language, ISO
     timestamp, lat/lng, cuisine, price). ABSA cost ≈ **$0.17**.
  2. **The hard limit:** Places returns **max 5 reviews/place** (even paid) and only "most-relevant"
     reviews → small, favorable sample. Caps an *independent* product.
  3. **Production supply:** Google owns *all* reviews → integration removes the 5-review cap. *"We
     don't scrape; we provide an engine that runs on data Google already has."*
- **FIGURE:** none (3 labelled columns). Optional: F1 small.
- **SPEAKER NOTES:** "Turn the weakness into the pitch: the 5-review cap is the reason to pitch to
  the data owner. We used the official **paid API, not scraping** (lower legal risk — Slide 14)."
- **GRADING:** Technical (20%) + Business (30%).

### SLIDE 9 — Recommender Methods (signals)  ·  LAYOUT: light, table
- **ON-SLIDE TEXT (table):**

  | Signal | Role | Status |
  |---|---|---|
  | ABSA food aspect | Core — isolate food from ambiance/price/service | Primary (validated on real data) |
  | Time decay | recent reviews weighted (chefs change) | Included (real ISO timestamps) |
  | Reviewer weighting | trust food-focused reviewers | Designed; **inert on Places (no author history)** |
  | Cuisine normalization | don't compare sushi & tapas on one scale | Included (fairness trade-off) |
  | Food-photo ratio (image) | praised for food or terrace? | Extra mile |
  | ~~Venue age (<10y)~~ | ~~kills old gems, no causal link~~ | **Rejected** |
- **FIGURE:** none (the struck-through "Rejected" row is the visual signal of critical thinking).
- **SPEAKER NOTES:** "Show the rejected row — it demonstrates critical thinking. Optional: ablation
  (Appendix A2) — removing cuisine normalization slightly *raises* global metrics but breaks
  within-group fairness — a deliberate trade-off."
- **GRADING:** Technical (20%).

### SLIDE 10 — Personalization in Action (Layer 2)  ·  LAYOUT: light, side-by-side lists
- **ON-SLIDE TEXT:**
  - The user sets **aspect weights** (food / service / ambiance / price); same filters, different
    weights → different recommendations.
  - **Sanity:** weights `{food:1.0}` reproduces the pure FQS order (built-in check).
  - **Gràcia, same area & cuisine, different user:**
    - *Food-first* top picks: TERNERITO, Pink Buda, Chivuo's (burger/ramen kitchens that nail food)
    - *Ambiance-first* top picks: La Pubilla, Santa Gula, El Disbarat (atmospheric tapas/Catalan)
  - Each card is **explainable**: the match score breaks down by aspect (e.g. food +0.49 · ambiance
    +0.18) + food-mention rate + a representative review.
- **FIGURE:** a screenshot of the **Streamlit prototype** Layer-2 view if available (live MVP = extra
  mile); else two labelled lists built as pptx text boxes.
- **SPEAKER NOTES:** "This is the proof it's a *recommender*, not just a re-ranker — a food-first and
  an ambiance-first user get genuinely different top picks from the same candidate set. We built a
  working Streamlit prototype (the graded 'extra mile')."
- **GRADING:** Technical (20%) + Business (30%) + Communication.

### SLIDE 11 — Evaluation Methodology (3 axes)  ·  LAYOUT: light, 3-axis table + figure  ★ 30%
- **ON-SLIDE TEXT:**
  - **No external label:** Michelin matched only **4/652** (fine-dining — wrong population) → we
    evaluate with self-contained metrics. *(Stating this pivot proves we engineered the evaluation.)*

  | Axis | Metric | Result |
  |---|---|---|
  | **Technical** | star vs FQS spread [0,1] | 0.076 vs **0.142** (~1.9×) |
  | | star-tie resolution | **12%** tied; FQS separates **45%** at \|Δ\|≥0.2 |
  | | rank churn | Kendall **τ=0.234** (new info) |
  | **User-centered** | within-group orderable spread | star 0.21 vs FQS **0.41** |
  | | explainability coverage | **100%** of scored venues |
  | **Business** | hidden gems / absolute traps | **31** / **56** |
- **FIGURE:** F5 `reports/divmetric_fig4_rank_churn.png`, right. Caption: *"Rank by stars vs rank by
  FQS — τ=0.234: FQS is not a rehash of stars."* (Optional 2nd: F4 spread violin.)
- **SPEAKER NOTES (say it):** "These prove FQS *discriminates differently* from stars, not that it
  is *correct*. Final correctness needs a casual-tier external label (Repsol Soletes / Bib Gourmand
  — guides that actually overlap our sample) — future work."
- **GRADING:** Evaluation & Business Impact (30%) — hits all three metric types the brief names.

### SLIDE 12 — Business Model & Monetization  ·  LAYOUT: light, table + guardrail callout
- **ON-SLIDE TEXT:**

  | Path | Who pays | Value exchange | Fit |
  |---|---|---|---|
  | **A. Platform integration (primary)** | Google / a Maps rival | FQS as a 2nd ranking axis on data they own; removes 5-review cap | **Strongest** |
  | **B. B2B2C API license** | travel/booking/hotel apps | license the FQS engine + aspect personalization | Good |
  | **C. Tourism board (B2G)** | city / DMO | redistribute visitors from traps to vetted local gems (over-tourism + local economy) | Strong for Barcelona |
  | D. Independent B2C app | diners (freemium) + booking commission | standalone discovery | Weakest (5-review cap) |
  - **GUARDRAIL (callout box):** **Never pay-for-rank.** The asset is *trust in a de-biased signal*;
    selling placement re-creates the bias we remove. OK revenue: feature value / API subscription /
    public contract / commission on *honestly* ranked results.
- **FIGURE:** none (table + a highlighted guardrail box in red).
- **SPEAKER NOTES:** "Lead with A (pitch the data owner). C is the public-value wedge for Barcelona
  (a poster child for over-tourism). The guardrail is the ethical spine — it's also what protects the
  long-term business."
- **GRADING:** Business Problem & Value Proposition (30%).

### SLIDE 13 — Business Impact (KPIs + value model)  ·  LAYOUT: light, KPI table + formula  ★ 30%
- **ON-SLIDE TEXT:**
  - **Google's upside:** Trust (we found **56** venues at 4.6★+ whose food is bottom-quartile —
    silent trust risks) · Engagement (a "Food Quality" filter; stars no longer differentiate —71% at
    4.5+) · Local discovery (**31** hidden gems → expands the advertiser long tail) · Scale
    (Barcelona → tourist cities → global).
  - **Business KPIs to A/B test (FQS-ranked vs star-ranked):** regret reduction (post-meal rating
    delta) · decision confidence / time-to-choose · gem-discovery rate · "Food Quality" filter
    usage & retention · booking conversion · (B2G) tourist redistribution % · partner NPS.
  - **Illustrative value model (assumptions, not a result):**
    avoided-regret ≈ **V × M × p_trap × r × c**. With V=1M visitors, M=4 risky meals, p_trap=**0.09**
    (=56/652), r=0.5 re-routed, c=€10 → ≈ **€1.8M/yr** at one-city scale. *The formula is the point;
    every input is a lever.*
- **FIGURE:** none (KPI table + the formula box). Optional: F3 tie-resolution as the "decision-help"
  proof.
- **SPEAKER NOTES:** "Today's evidence is **offline/proxy** (gems/traps/ties/churn). The production
  KPIs need a live A/B test — state that as the validation plan, not as an achieved result. Don't
  present €1.8M as fact; it's a transparent model the listener can re-parameterize."
- **GRADING:** Evaluation & Business Impact (30%).

### SLIDE 14 — What We Tested, Rejected & The Risks  ·  LAYOUT: light, two columns
- **ON-SLIDE TEXT — Left "Hypothesis → Rejected":**
  - We hypothesized *"tourist districts review ambiance, not food."* **Tested → FALSE:** food-mention
    was **96% tourist vs 96% local**. Google's "most-relevant" reviews discuss food everywhere.
  - Surfaced a real bias: relevance-ranked reviews are a **favorable, detailed selection** (selection
    bias) — a trap for any review-based system, including ours.
- **ON-SLIDE TEXT — Right "Risk → Mitigation":**
  - **Venue fairness:** down-ranking legal ambiance/terrace bars → FQS is a *second axis*, shown
    *beside* stars; ambiance weight is user-controlled; never silently overwrite a rating.
  - **Foodie-snobbery bias** ("who defines good food?") → cuisine normalization + user-set weights,
    not a hard-coded notion of quality.
  - **Manipulation:** 5 reviews/place → more exposed to fake reviews → show FQS with a confidence
    signal, not as truth.
  - **Legal (ToS / GDPR):** Places review *text* has caching/retention limits + attribution rules
    (place IDs may persist, review text generally may not be stored long-term) → production must
    comply (path A, *inside* Google, is cleanest). Review text + author names are **personal data
    (GDPR)** → minimize / lawful basis / erasure; no `author_id` ⇒ no CF ⇒ privacy-protective. We
    used the **official paid API, not scraping**.
- **FIGURE:** F7 `reports/real_fig2_aspect_mention.png` (small, left) — caption *"Hypothesis
  rejected: food-mention 96% in BOTH tourist and local districts."*
- **SPEAKER NOTES:** "A rejected hypothesis is **proof we actually validated** — keep it in; deleting
  it makes us look like a team that never checked. Legal is the gap most teams miss — naming it earns
  credit."
- **GRADING:** Evaluation/Ethics + Communication (honesty differentiates).

### SLIDE 15 — Limitations & Future Work  ·  LAYOUT: light, roadmap
- **ON-SLIDE TEXT:**
  - **5-review API cap** → noisy per-venue FQS; independent prototype is supply-throttled (→ path A).
  - **Selection bias** (Google's "most-relevant" reviews); **FQS ceiling** (top venues near +1, best
    discrimination in mid/lower range); **aspect sparsity** (food 100/service 99/ambiance 92/**price
    70%**).
  - **No external ground truth** yet (Michelin 4/652); **build-vs-buy** — moat is framing + PoC +
    insight, not technology (said honestly).
  - **Future:** external casual-tier validation (Repsol/Bib) · multimodal (food-photo ratio) ·
    reviewer-trust at scale · multilingual ABSA hardening · live A/B on the business KPIs.
- **FIGURE:** simple roadmap timeline (pptx shapes).
- **SPEAKER NOTES:** "Maturity = pre-empting objections. The three you WILL get are on the
  cheat-sheet (PART 4)."
- **GRADING:** Communication + Technical honesty.

### SLIDE 16 — Closing / The Ask  ·  LAYOUT: dark, single statement
- **ON-SLIDE TEXT:**
  - Recap: **"Stars measure popularity. We measure the food. Google should ship both."**
  - The ask: a **Barcelona pilot** (FQS as a second axis), validated against **Repsol Soletes / Bib
    Gourmand**, then a **tourist-city rollout**.
- **FIGURE:** the dual-axis motif (⭐ blue + 🍽 green) from Slide 1.
- **SPEAKER NOTES:** "End confident. One sentence, one ask, one image."
- **GRADING:** Communication.

---

# PART 4 — APPENDIX SLIDES (for Q&A defense; build after the 16 core)

- **A1 — ABSA example:** one real review → its 4 aspect scores (food/service/ambiance/price). Shows
  the decomposition concretely. (Build a small table; sample text from `data/processed/bcn_absa.jsonl`.)
- **A2 — FQS formula:** FQS = time-decayed, reviewer-weighted mean of the *food* aspect, cuisine-
  normalized. Show the weight terms. FIGURE: `reports/fig5_ablation_fqs.png` (ablation of the signals).
- **A3 — Pipeline / proxy-label eval (synthetic):** FIGURE `reports/fig4_capture_rate_star_vs_fqs.png`
  (capture rate star vs FQS on synthetic proxy labels) + `reports/fig3_rerank_before_after.png`
  (before/after rerank). Caption: *"Full pipeline validated on synthetic data with proxy labels; real
  data has no external label (Slide 11)."*
- **A4 — Cost analysis:** Google Places API SKUs — Text Search ×52 + Place Details (Atmosphere SKU)
  ×652; Gemini ABSA total ≈ **$0.17** for 3,249 reviews (~258 tokens/review). Shows you understand
  the unit economics.
- **A5 — Competitive scan:** TheFork AI Search (Sep 2025) does natural-language multi-attribute
  search but does **not** decompose/correct the rating bias → we sit *upstream* of search, not
  competing. We restore the signal that search runs on.

### Presenter cheat-sheet — the three questions you WILL be asked
1. **"Where's your data from?"** → 3-layer story (Slide 8). The 5-review cap is irrelevant because
   Google owns all reviews.
2. **"Why won't Google build it themselves?"** → No technical moat claimed; we bring problem-framing
   + a working PoC + the de-biasing angle nobody addresses (Slide 15).
3. **"Isn't this just TheFork / existing recommenders?"** → They improve *search* over the same
   saturated stars; we fix the *ranking signal*. When every place is 4.5★, search can't help; FQS
   restores discrimination (A5).

---

# PART 5 — FINAL BUILD CHECKLIST (the AI must satisfy all before returning the deck)

- [ ] 16 core slides + 5 appendix slides, in order, 16:9, design-system colors/fonts applied.
- [ ] Every figure embedded from its **exact `reports/...` path**; captions added; script run from
      project root. No fabricated charts — placeholders if a file is missing.
- [ ] On-slide text copied **verbatim**; longer detail moved to **speaker notes**.
- [ ] Corrected framing everywhere ("saturated," never "wrong/inverted"); the rejected hypothesis
      kept (Slide 14).
- [ ] Every number matches PART 1's canonical list exactly.
- [ ] Slide 7 (centerpiece) and Slides 11 & 13 (the two 30% criteria) are the most polished.
- [ ] Output: a runnable `python-pptx` script producing `reports/BCN_FQS_pitch.pptx` (+ optional
      Marp markdown fallback).
