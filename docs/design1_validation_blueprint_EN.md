# Blueprint 1: Empirical Validation of the "Stars ⇄ Food Quality" Divergence

> Purpose: Validate the hypothesis underlying this proposal **with data, not impressions**.
> Status: **Real-data validation complete (652 restaurants / 3,249 reviews in Barcelona)**. The original naive hypothesis was partially rejected by the real data and reframed more accurately. This document preserves the original design while annotating it throughout with **[Real-Data Verdict]**. The fact that the validation process is visible is itself part of the evaluation (do not erase the process).

---

## ★ Real-Data Validation Summary (most important — read this first)

**Original story (hypothesis)**: "Google stars don't reflect food quality. Tourist bars get ★5 while good restaurants sit in the 3-point range. The more touristy a district, the less its reviews touch on food."

**The story the real data told (revised)**: "In Barcelona, Google stars are **saturated and have lost discriminative power**. Almost all 652 restaurants are compressed into ★4.3–4.9 (only 21 are in the 3-point range). Stars cannot distinguish between restaurants. Within that band crowded with ties, **FQS recovers the differences in food quality**."

| Metric | Synthetic data | Real data | Verdict |
|---|---|---|---|
| Pearson r (stars vs FQS) | 0.226 | **0.448** | Divergence is real but moderate. Stars explain only ~20% of FQS variance |
| food-mention rate, tourist vs local | (difference engineered in) | **96% vs 96%** | **STEP 3 hypothesis rejected** (no difference) |
| ambiance-mention rate, tourist vs local | — | 51% vs 46% | Predicted direction but marginal gap |
| Restaurants with stars in the 3-point range | — | **21/652** | Extremely thin tail = range restriction (evidence of saturation) |

**Core of the reframing**:
- ✗ Old: "Stars are **wrong**" → subjective and easy to rebut ("that's just your taste, isn't it?")
- ✓ New: "Stars are **saturated / non-discriminative** (stuck at 4.5, carrying no information). FQS recovers discriminative power" → an objective fact you can demonstrate in one shot with a star histogram. You can pitch it as "complementing a malfunctioning region" rather than dismissing Google entirely.

**Why the new framing is stronger**: the 5-point scale is pinned at its top end, with near-zero entropy = broken as a ranking instrument. This can be proven with data. "We patch the region where stars are broken with FQS" is far easier for Google to accept.

**How rejected hypotheses are handled**: STEP 3 (tourist bias) was rejected by the real data. **Put it on the slide without hiding it.** The process of "forming a hypothesis → testing it → rejecting it" is evidence that the validation was actually done = bonus points. Erasing it makes it indistinguishable from "never validated."

---

> Purpose (original text, for reference): Prove **with data, not impressions** the hypothesis underlying this proposal — "Google Maps stars do not reflect food quality (especially in Barcelona's tourist-city context)." Each step specifies its **input / processing / output (= the figures that go on the slides)**.

---

## 0. Where this part fits

- It maps directly to the **"Business Problem and Value Proposition — 30%"** grading weight.
- If the divergence isn't visible here as "numbers," the whole proposal ends up as "one person's opinion."
- The goal is to produce three figures:
  1. **Divergence scatter plot** (stars vs food-quality score)
  2. **Bar chart of the "high stars but no food mention" rate**
  3. **Before/after swap table for the re-ranking**

---

## 1. Data sources (two tracks)

### 1-A. For methodology validation: Google Local (McAuley / UCSD)
- URL: https://cseweb.ucsd.edu/~jmcauley/datasets.html#google_local (to be confirmed)
- What it is: a research-released version of Google Maps reviews (US, through September 2021)
- Fields: `user_id, name, time, rating, text, pics, resp` plus restaurant metadata (category, price, coordinates, average stars, review count)
- Role: because **reviewer histories and timestamps are complete**, the full method including reviewer weighting / time decay can be demonstrated.
- Caveat: **Barcelona is not included (all US)**. So we frame it as "different city, but the method is portable."

### 1-B. For story validation: Barcelona real data (Google Places API New)
- Acquisition: collected with a **modified version** of the existing `ingest_google_places.py` (Module A in Blueprint 2).
- Constraint: **at most 5 reviews per restaurant** (a hard constraint — unchanged even on the paid tier).
- Role: even at small scale, it provides a concrete example that "the divergence actually occurs in the tourist city of Barcelona." Even with 5 reviews you can plot one point on the scatter.

> **Fallback if data acquisition is impossible**: substitute a **synthetic data generator** that reflects Barcelona's reality (Module A-sim in Blueprint 2). This is legitimate because the professor's assignment permits mock data. The synthetic assumptions (tourist-bar star inflation, no food mentions, etc.) are stated explicitly.

---

## 2. Analysis steps (in execution order)

### STEP 1 — Defining the food-quality score (Food Quality Score, FQS)
**Input**: each restaurant's set of reviews (text, rating, author, time)
**Processing**:
1. Run each review through **ABSA (Aspect-Based Sentiment Analysis)**, decomposing it into 4 aspects:
   - `food` / `service` / `ambiance` / `price`
2. For each review, extract the **sentiment polarity of the food aspect** (-1 to +1). If there is no food mention, `null`.
3. The restaurant's **FQS = the weighted average of the sentiment polarity of food-mentioning reviews** (weight design in STEP 4).
**Output**: two values per restaurant — `star_rating` (raw stars) and `FQS` (food quality).

### STEP 2 — Measuring the divergence (★Figure 1)
**Processing**:
- Compute the **correlation coefficient (Pearson / Spearman)** between `star_rating` and `FQS` across all restaurants.
- Draw the scatter plot. Visualize the deviation from the diagonal (perfect agreement).
- **Highlight in red** the restaurants that are "★4.5+ yet in the bottom 50% on FQS" = "tourist-trap restaurants."
**Output (for slides)**:
- One scatter plot (with the correlation coefficient noted). **The lower the correlation, the stronger the claim.**
- Hypothesis-test sentence: "The correlation between stars and food quality is r=○○. Choosing on stars alone explains only ○○% of food quality."

> **[Real-Data Verdict]** r=0.448 (higher than the synthetic 0.226 but comfortably below 1.0). The divergence is real.
> **But the interpretation is revised**: in the scatter plot most restaurants are compressed into ★4.3–4.9, and within that band FQS spreads widely from −0.9 to +1.1. This is not "stars and FQS point in opposite directions" but rather **"stars are saturated/non-discriminative, while FQS discriminates food quality within the tied band."**
> The slide wording becomes not "stars are wrong" but **"stars are saturated/non-discriminative; FQS recovers food quality within the tied band."** Show Figure 1 (real_fig1_star_vs_fqs.png) together with the star histogram (real_star_histogram.png), and lead with "almost every restaurant is 4.5★ = stars carry no information."

### STEP 3 — The "high stars but no food mention" rate (★Figure 2)
**Processing**:
- Among reviews of restaurants rated ★4.0+, tally the share of reviews with **zero food mentions**.
- Plot aspect-occurrence frequency as a bar chart (food / ambiance / price / service).
- **Stratified comparison** between tourist districts (e.g., La Rambla, Barceloneta) and local districts (e.g., Gràcia, Sant Andreu).
**Output (for slides)**:
- Bar chart: "Even at ★4.5+ restaurants, ○○% of reviews never say a word about the food."
- Stratified comparison: the more touristy the district, the more ambiance/price mentions and the fewer food mentions (= visualizing tourist bias).

> **[Real-Data Verdict: this hypothesis is rejected]** The food-mention rate is 96% in tourist areas and 96% in local areas — **no difference**. "The more touristy a district, the less it touches on food" did not hold up in the real data.
> Cause: the "top-relevance" reviews Google returns are detailed regardless of district, and almost all of them mention food.
> **How to handle it on the slide**: don't erase it — present it explicitly as "hypothesis → test → rejection" (= evidence the validation was actually done = bonus points). Honestly note alongside it that ambiance mentions are 51% tourist vs 46% local — predicted direction but a marginal gap.
> **Byproduct (use in Limitations)**: a new finding that "Google's top-relevance reviews carry a selection bias toward favorable, detailed reviews." This is itself a "hard-to-see trap."

### STEP 4 — Re-ranking (★Figure 3)
**Processing**:
- Within the same area and same cuisine, line up the `star_rating` order against the `FQS` order.
- Extract restaurants with large rank changes (rank delta):
  - **"Low stars but real food"** (a sharp rise on FQS) = a hidden gem that was surfaced
  - **"High stars but mediocre food"** (a sharp fall on FQS) = a tourist-trap restaurant
**Output (for slides)**:
- A before/after rank-swap table (with arrows). This is the evidence of the proposal's "effect."

> **[Real-Data Verdict]** Among the 196 "trap" restaurants at the top of rank_delta, **genuine traps do exist** (★4.5 with FQS −0.4). But note: the restaurants that surfaced at the top of the report (L'APE REGINA, etc.) have FQS of +0.6 to 0.76 — their **absolute values are actually high**; they merely fell in relative rank within a small district×cuisine subgroup. They are not "high-star restaurants with bad food."
> **How to handle it on the slide**: distinguish "absolute traps (FQS genuinely low)" from "relative traps (relative rank within a small subgroup)." Don't exaggerate and call them "bad restaurants." Choose genuine traps (high-star restaurants whose FQS absolute value is low) as the examples.

---

## 3. Evaluation: proving FQS is "more correct than stars" (★most important — 30% of the grade)

Since this is a problem with no ground-truth labels, we use **independent external lists of "restaurants with good food" as proxy ground truth**.

### 3-A. Proxy ground-truth labels (those obtainable in Barcelona)
- **Michelin Guide** (stars / Bib Gourmand)
- **Repsol Guide (Soles Repsol)** ← especially effective in the Spanish context
- (reinforcement) local food-media "best of the year" lists, etc.

### 3-B. Validation logic
- Hypothesis: "FQS agrees more closely with these specialist-guide listings than raw stars do."
- Metrics:
  - **Precision@K / Recall@K**: how many guide-listed restaurants fall within the top-K by FQS vs the top-K by stars
  - **NDCG**: compare ranking quality, treating "listed = high relevance"
  - **AUC**: as a binary classification of "listed/not listed," compare the ROC of FQS vs stars
**Output (for slides)**:
- A comparison bar chart: "Capture rate of specialist-guide listings: stars ○○% → FQS ○○%."

### 3-C. Robustness (ablation)
- Show how accuracy drops when each signal (reviewer weighting / time decay / cuisine normalization) is **removed one at a time**.
- Demonstrating which signals matter = technical honesty (Technical 20% of the grade).

---

## 4. Signal design (what goes into FQS) — with strengths/weaknesses made explicit

| Signal | Adopt? | Rationale | Data requirement |
|---|---|---|---|
| ① food-aspect sentiment (ABSA) | **Adopt — the core axis** | Strips away ambiance/drinks/terrace. The heart of the proposal | Review text |
| ② Reviewer trustworthiness (weight food-focused reviewers more) | **Adopt (McAuley only)** | Give more weight to ratings from people with a foodie history | Reviewer history (not available in Places) |
| ③ Time decay (favor recent reviews) | **Adopt** | Flavor changes when the chef changes. It's "review recency," not "restaurant age" | Timestamps |
| ④ Per-cuisine normalization | **Adopt** | Don't judge a sushi place and a tapas bar on the same star baseline | Restaurant category |
| ⑤ food share of photos | **Optional (extra mile)** | Infer the restaurant's evaluation axis from whether photos are food or terrace | Images (multimodal) |
| ✗ Restaurant age (favor those ≤10 years old) | **Not adopted** | Kills established, renowned restaurants. No causal link from newness → flavor. Fairness risk | — |

> The important point is that ②③ **rebuilt** the original idea of "favor restaurants under 10 years old." It wasn't dropped; the "freshness" we genuinely wanted to leverage was implemented correctly via ③ time decay.

---

## 5. Biases to watch for (writing them out preemptively = bonus points)

> **[Limitations revealed by the real data — flag with top priority]**
> - **Star range restriction (saturation)**: almost all 652 restaurants sit around ★4.5. The variance of stars is small, which itself distorts the divergence metric (the correlation). This is not a flaw but **the very premise of the proposal** (stars are saturated = the reason FQS is needed) — frame it that way.
> - **At most 5 reviews per restaurant (Places constraint)**: FQS is noisy on small samples. State clearly that in production this is resolved with full reviews from the partner (Google).
> - **Selection bias**: the targets are Google's "top-relevance" reviews = biased toward the detailed and favorable. The high 96% food-mention rate is partly due to this. It is not a truly random review population.
> - **Minor**: cuisine normalization (mean-centering) occasionally pushes FQS slightly beyond ±1 / representative review examples are chosen as "the longest," so they may not match the FQS average (a note on display logic).

- **foodie snobbery bias**: weighting the "gourmet crowd" in ② can introduce the reverse bias — overrating upscale restaurants and underrating cheap good ones. The opposite direction of the "dry-snacks bar ★5" you dislike. Decide the weights by learning, not by a hard rule.
- **Drawing the tourist vs local line**: "discounting tourist votes" dismisses the voices of some users. Argue its legitimacy in the ethics section.
- **Language bias**: multilingual reviews (Spanish/Catalan/English mixed). ABSA may have accuracy differences across languages. Since the real data showed no difference in food-mention rate across districts, no large distortion has been observed, but it warrants caution.
- **Fairness to restaurants**: the legitimacy of structurally down-ranking a legal business format (terrace bars).

---

## 6. Deliverables checklist (definition of done for this part)

- [ ] Figure 1: stars vs FQS scatter plot (with correlation coefficient)
- [ ] Figure 2: bar chart of aspect-mention rates (stratified tourist/local)
- [ ] Figure 3: before/after re-ranking table
- [ ] Evaluation table: specialist-guide capture rate, stars vs FQS (Precision@K, NDCG, AUC)
- [ ] Ablation table: contribution of each signal
- [ ] Measured values that fill in the "reasons not to trust it" (correlation r, no-mention %)

---

## 7. The first 3 commands to run once the real data arrives (connecting to Blueprint 2)

```
# 1. Acquire Barcelona (Blueprint 2 Module A)
python -m rag.ingest_bcn_grid --city "Barcelona" --grid districts_x_cuisines

# 2. Compute FQS (Blueprint 2 Module B+C)
python -m pipeline.compute_fqs --input data/bcn_raw.jsonl --output data/bcn_fqs.parquet

# 3. Generate the divergence report (auto-draws STEP 2-4 of this blueprint)
python -m analysis.divergence_report --input data/bcn_fqs.parquet --out reports/
```
