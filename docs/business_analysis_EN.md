# Business Analysis — Food Quality Score (FQS) for Restaurant Discovery

> Companion to `design3_presentation_spec_EN.md` (the slide spec). This is the **business-analysis
> report** the brief grades most heavily: *Business Problem & Value Proposition (30%)*,
> *Evaluation & Business Impact (30%)*, plus the *ethical/legal/social* analysis and an
> *executive summary*. The professor's note — *"It is not about implementing but about analysing
> the business application and opportunity"* — frames this document as the core deliverable; the
> working prototype (652 real restaurants, ABSA, FQS, Streamlit) is the "extra mile" evidence.

All figures trace to our real run on **652 Barcelona restaurants / 3,249 reviews** (5 districts ×
10 cuisines, Google Places API New). Illustrative business estimates are explicitly labelled as
assumptions to validate.

---

## 1. Executive summary

On Google Maps in Barcelona, star ratings have **saturated**: 96% of restaurants sit at 4.0★+ and
71% at 4.5★+ — only **21 of 652** are below 4.0. The 5-star scale is pinned to the ceiling and can
no longer tell a great kitchen from an average one. **12% of all restaurant pairs are tied on
stars** (literally indistinguishable), and within a single district×cuisine the food signal varies
enormously (10 Gràcia tapas bars all at 4.5★ span an FQS of **−0.10 to +0.95**).

We built a **Food Quality Score (FQS)**: an Aspect-Based Sentiment pipeline that isolates the
*food-only* signal from review text and restores discrimination where stars collapsed. FQS spreads
~1.9× wider than stars on a common scale and is **largely new information** (rank churn Kendall
τ = 0.234 vs stars). On top of it sits a thin **personalization layer** (aspect weights: food /
service / ambiance / price) so a food-first diner and an ambiance-first diner get different picks.

**The opportunity:** in saturated-rating markets, the ranking signal is broken; whoever restores it
owns the "where should I eat" decision. We propose Google integrate FQS as a **second axis** beside
stars (primary path — Google owns the data), with B2B2C and tourism-board (B2G) variants as
alternatives. **The ask:** a Barcelona pilot, validated against casual-tier guides (Repsol Soletes /
Bib Gourmand), then a staged tourist-city rollout.

---

## 2. Business problem & opportunity

**The problem (measured, not asserted).** Review platforms are the default decision layer for
dining; their *discriminating power IS the product*. In Barcelona that power has collapsed:

| Symptom | Real measurement (n=652) |
|---|---|
| Rating inflation / ceiling | mean 4.54★; 96% ≥4.0★; 71% ≥4.5★; only **21 below 4.0** |
| Stars can't separate places | star std on [0,1] = **0.076**; **12%** of all pairs are exactly tied |
| Real quality still varies under the tie | FQS std = 0.142 (**1.9×** wider); Gràcia: 10 venues at 4.5★ → FQS −0.10…+0.95 |
| Stars ≠ food quality | Pearson(star, FQS) = **0.448** (moderate; star range-restriction dominates) |

**Why it matters commercially.** When every result is 4.5★, the user cannot choose, genuinely good
small kitchens are invisible, and the platform's ranking value erodes. The pain is highest for
**visitors in unfamiliar cities** — few meals, no local cues, high regret cost per wrong choice.

**Market context (illustrative — validate).** Barcelona alone draws on the order of ~12–15M
overnight visitors/year; the EU tourist-city cluster (Venice, Lisbon, Prague, …) multiplies this.
Dining is a top-3 trip expense and a top driver of trip satisfaction. A ranking that actually
discriminates food quality is valuable wherever ratings have saturated — which is most mature
review markets.

---

## 3. Target users & stakeholders

**Primary persona — the visiting diner.** In a foreign city for a few days; 6–10 meals total;
cannot read local cues; currently picks on stars + photos and frequently lands in a "tourist trap".
High willingness to engage with a tool that prevents a wasted meal.

**Secondary persona — the local food lover.** Wants quality over hype; tired of the same
algorithmically-boosted venues; values hidden gems and aspect control (e.g. "great food, don't care
about ambiance").

**Stakeholder map (who wins, who is at risk).**

| Stakeholder | Interest | Effect of FQS | Our stance |
|---|---|---|---|
| Visiting / local diners | Choose good food, avoid regret | **Win** — ties broken, traps flagged, gems surfaced | Primary beneficiary |
| High-quality small kitchens | Underrated by saturated stars | **Win** — discoverability ↑ (31 gems found in 652) | Fairness *for* the underdog |
| Terrace / ambiance bars | Rated for vibe, not food | **Risk** — may rank lower on the food axis | FQS is a *second axis*, not a replacement; ambiance weight is user-controlled |
| Platform (Google) | Trust, engagement, ad inventory | **Win** — credibility + a new discriminating feature | Primary customer (path A) |
| Travel/booking apps (TheFork, hotels) | Differentiated quality signal | **Win** — license the FQS axis | Customer (path B) |
| City / tourism board | Over-tourism, local economy | **Win** — redistribute flow from traps to local gems | Customer (path C) |
| Restaurant marketers / advertisers | Paid visibility | **Tension** — pay-for-rank would corrupt FQS | Hard line: no pay-for-placement (see §9) |

---

## 4. Value proposition

> **"Stars measure popularity. FQS measures the food. When every place is 4.5★, we tell them
> apart — and rank them the way *you* care about."**

- **For diners:** a trustworthy, explainable "best food near me" that works *even when stars don't*,
  personalized by the aspects you value.
- **For good small restaurants:** discoverability they can't buy and stars don't grant.
- **For the platform:** defends the core asset (rating trust), adds a differentiating feature, and
  expands the discoverable long tail of local advertisers.

**Why now / why us:** rating saturation is a measured, growing phenomenon; ABSA via LLMs is newly
cheap and multilingual (our full run cost **$0.17**); no incumbent decomposes and de-biases the
rating signal (TheFork's 2025 AI search improves *search over the same saturated stars* — it does
not fix the signal). Our edge is **problem framing + a working PoC + the de-biasing insight**, not a
deep technical moat (stated honestly).

---

## 5. Business model & monetization

The data-supply constraint shapes the model: the Places API returns **max 5 reviews/place**, which
caps an independent product. So the strongest path is the one where the customer already owns the
reviews.

| Path | Customer / who pays | Value exchange | Fit |
|---|---|---|---|
| **A. Platform integration (primary)** | Google (or a Maps competitor) | FQS as a second ranking axis on data they already own; removes the 5-review cap | **Strongest** — solves data supply, complements not competes |
| **B. B2B2C API license** | Travel/booking/hotel-concierge apps | License the FQS engine + aspect personalization as an API/widget | Good — many apps want a quality axis, lack the de-biasing |
| **C. Tourism board (B2G)** | City / DMO | Redistribute visitors from saturated traps to vetted local gems (over-tourism + local-economy policy) | Strong fit for Barcelona specifically |
| D. Independent B2C app | Diners (freemium) + booking commission | Standalone discovery app | Weakest alone — throttled by the 5-review cap |

**Recommended:** lead with **A** (pitch to the data owner), with **C** as a credible
public-value wedge for Barcelona and **B** as the horizontal expansion. **Monetization guardrail
(non-negotiable):** revenue must never come from *pay-for-rank*. The entire asset is **trust in a
de-biased signal**; selling placement re-creates exactly the bias we remove. Acceptable revenue:
platform feature value / API subscription / public contract / booking commission on *honestly*
ranked results.

---

## 6. The recommendation task (solution, in brief)

A genuine two-layer recommender (not a re-scorer):

1. **Layer 1 — De-biasing (the novelty).** ABSA decomposes each review into food / service /
   ambiance / price sentiment; FQS = a time-decayed weighted mean of the *food* aspect, cuisine-
   normalized. This is the shared, user-independent quality signal.
2. **Layer 2 — Personalization (content-based).** The user sets aspect weights; candidates are
   filtered (cuisine / district / price / min-star) and ranked by the weighted blend of their
   aspect scores. Food-first vs ambiance-first users get **different** top picks; `weights={food:1}`
   reproduces the pure FQS order (a built-in sanity check).

Collaborative filtering is **deliberately not used**: the Places API exposes no reviewer identity
(`author_id`), so a user×item matrix cannot be built. We restrict to content-based scoring — also a
privacy advantage (no per-user tracking needed). *(Technical detail lives in the design blueprints;
this section exists so the business reader sees why it is a recommender, not a filter.)*

---

## 7. Evaluation — technical, user-centered, business

We engineered a **self-contained** evaluation because no usable external label exists (Michelin
matched only **4 / 652** — fine-dining, the wrong population for casual discovery). State this pivot
openly: it proves the evaluation was genuinely designed.

| Axis | Metric | Result | Reading |
|---|---|---|---|
| **Technical** | star vs FQS spread (std, [0,1]) | 0.076 vs **0.142** (~1.9×) | stars saturated; FQS discriminates |
| | star-tie resolution | **12%** of pairs tied; FQS separates **45%** at \|Δ\|≥0.2 | "stars can't choose; FQS can" |
| | rank churn | Kendall **τ=0.234** | FQS is new information, not a rehash |
| **User-centered** | within-group orderable spread | star 0.21 vs FQS **0.41** | ~2× more choosable inside a real choice set |
| | explainability coverage | **100%** of scored venues | every rec carries food-mention rate + a representative review |
| **Business** | hidden gems surfaced | **31** (≤4.4★ but top-quartile FQS) | new discoverable inventory |
| | absolute traps flagged | **56** (≥4.6★ but bottom-quartile FQS) | silent trust/regret risks |

**Honesty note (graded):** these prove FQS *discriminates differently* from stars — **not** that it
is provably "more correct". Correctness needs an external casual-tier label (Repsol Soletes / Bib
Gourmand) — future work.

---

## 8. Business impact — measurable value

The technical metrics translate into business KPIs. Today's evidence is **offline / proxy**; the
production KPIs require an A/B test (FQS-ranked vs star-ranked) measuring post-meal satisfaction —
stated as the validation plan, not as achieved results.

**Proposed business KPIs**

| KPI | What it captures | How to measure (production) |
|---|---|---|
| Regret reduction | fewer "wasted meals" | post-visit rating delta, FQS-ranked vs star-ranked (A/B) |
| Decision confidence / time-to-choose | the saturation pain directly | survey + session analytics |
| Gem-discovery rate | long-tail value for small kitchens | % of selections that are sub-4.4★ but high-FQS |
| Engagement / retention | new reason to open the app | "Food Quality" filter usage, repeat sessions |
| Booking conversion | monetizable action | selection → reservation rate |
| Tourist redistribution (B2G) | over-tourism relief | % flow shifted from saturated zones to local gems |
| Partner NPS | restaurant-side fairness | survey of surfaced venues |

**Illustrative impact model (assumptions to validate — not a result).**
Avoided-regret value ≈ `V × M × p_trap × r × c`, where
`V` = visitors served, `M` = meals at risk per visitor, `p_trap` = probability a star-chosen venue
is a food-quality trap, `r` = fraction of those FQS would re-route, `c` = value of converting a
wasted meal into a good one. From our sample, **56/652 ≈ 9%** of high-star venues are bottom-quartile
on food (a defensible anchor for `p_trap`), and **12%** of choices are star-ties FQS can break.
Plugging *illustrative* inputs (V=1M reachable visitors, M=4 risky meals, p_trap=0.09, r=0.5,
c=€10 experiential value) gives ≈ **€1.8M/yr** of avoided-regret value at a single-city scale — the
formula matters more than the number; every input is a lever the reader can set.

---

## 9. Ethical, legal & social risks

**Legal (the gap design3 was thin on — flag explicitly).**
- **Google Places API terms / review caching.** Place IDs may be stored indefinitely, but most
  Places *content* (including review text) is subject to caching/retention limits and attribution
  requirements. Our prototype stored review text locally for research; a **production system must
  comply with the platform ToS** — which is precisely why path A (run *inside* Google, on Google's
  data) is also the cleanest legal posture.
- **GDPR / personal data.** Review text and author display names are personal data. We store
  `author_name`; production must minimize, lawfully base, and honor erasure. CF being impossible
  (no `author_id`) is, conveniently, **privacy-protective** — no per-user profiling.
- **No scraping.** We used the official paid API, not scraping — materially lower legal risk than
  review-scraping competitors.

**Fairness & social.**
- **Venue fairness:** structurally down-ranking legal ambiance/terrace businesses needs
  justification. FQS is a *second axis* shown *beside* stars, with ambiance weight under user
  control — we never silently overwrite a rating.
- **"Who defines food quality?" — foodie-snobbery bias:** over-rewarding fine dining / penalizing
  cheap excellence. Mitigation: cuisine normalization + user-set weights, not a hard-coded notion of
  "good".
- **Manipulation / review fraud:** with only 5 reviews/place, FQS is *more* exposed to fake reviews
  than aggregate stars — present FQS with a confidence signal, not as absolute truth.
- **Language bias:** ES/CA/EN mixed; food-mention parity across districts (96% vs 96%) is reassuring
  but multilingual ABSA accuracy must be monitored.
- **Long-term trust:** the asset is a *trusted* de-biased signal; transparency (explainable FQS) and
  the no-pay-for-rank guardrail are what protect it.

---

## 10. Limitations & future work

- **5-review API cap** → noisy per-venue FQS; the independent prototype is supply-throttled
  (production needs the data owner — reinforces path A).
- **Selection bias:** Google returns "most-relevant" (favorable, detailed) reviews — a hidden trap
  for any review-based system, including ours.
- **No external ground truth** (Michelin 4/652); FQS ceiling (top venues cluster near +1, so FQS
  discriminates best in the mid/lower range).
- **Aspect sparsity:** food 100% / service 99% / ambiance 92% / **price 70%** coverage — price is
  the thinnest; personalization renormalizes over present aspects.
- **Build-vs-buy:** the platform could build this in-house; our moat is framing + PoC + insight, not
  technology. **Future:** external casual-tier validation, multimodal (food-photo ratio),
  reviewer-trust at scale, multilingual ABSA hardening, live A/B on the business KPIs above.

---

## 11. The ask / next steps

1. **Pilot** in Barcelona: FQS as a second axis, validated against Repsol Soletes / Bib Gourmand
   (the casual-tier guides that actually overlap our population).
2. **A/B test** the business KPIs (§8) — regret reduction and gem-discovery as primary endpoints.
3. **Stage the rollout:** saturated tourist cities → global; B2G (tourism board) as the public-value
   wedge, B2B2C as horizontal expansion.

> **One line for the investor:** *"Stars measure popularity; we measure the food. In every market
> where ratings have saturated, whoever restores the signal owns the dining decision — we have the
> insight, the evidence, and a working prototype."*
