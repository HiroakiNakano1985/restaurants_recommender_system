"""Design blueprint 2 §4: Synthetic data generator (Module A-sim).

Synthetic data reflecting the realities of Barcelona, so that all of design blueprint 1's
analyses can be run even before real data is collected.
Generative model (embedding the hypotheses):

    true_food_quality ~ Beta(2, 2)                       # 0-1 latent food quality
    is_tourist_area   ~ Bernoulli(p=district-dependent)
    ambiance          = tourist: Uniform(0.3, 1.0) / local: Uniform(0.0, 0.35)
    appeal            = 0.35*tfq + 0.65*ambiance          # ambiance dominates the star rating
    star_rating       = clip(3.4 + 1.7*appeal + noise, 3.0, 5.0)  # Google's real inflation band
    food_mention_prob = 0.7 - 0.4*is_tourist_area         # the more touristy, the lower the food mention rate

-> Data where "star rating and food quality diverge" is constructed structurally. Because the
  star rating inflates in an ambiance-driven way, tourist-trap restaurants that are
  "rated 4.6 stars yet have bad food" are actually generated.

Revision note (2026-06-20): the original formula
    ambiance_boost = is_tourist * Uniform(0,0.8); star = 1 + 4*(0.5*tfq + 0.5*ambiance_boost)
produced stars centered around a mean of ~2.4, which (a) diverged from Google's inflated star
distribution, and (b) since food accounted for 50% of the star, made it impossible in principle
to create a "4.6-star dud restaurant," so the design blueprint 1 STEP2/3 thresholds (4.0/4.5
stars) matched 0 records. To align with the project premise of the "4.6-star dud restaurant"
and the figures in design blueprint 1, the star was inflated into the realistic range and the
contribution of ambiance was made larger than that of food (design blueprint 2 §4 revised with
this formula).

(Note: showing divergence with data that was built to diverge is circular reasoning. On the
  slides, state explicitly that "with real data we validate through the same pipeline," and
  position the synthetic data as a demo of the pipeline's operation.)

Each review embeds the ground-truth aspect polarity directly into the **public fields aspect_***.
The simple ABSA (§5 SimpleAbsa) reads these embedded values as-is. The LLM version re-estimates
them from the text.

The tone of the wording is tied to the magnitude of the true value (= each aspect's polarity)
(_BANDS). The true value is mapped to [0,1] via q=(polarity+1)/2 and split into 4 bands:
high(>0.75)/mid(0.4-0.75)/low(0.2-0.4)/very-low(<0.2), with words randomly chosen from a
vocabulary whose tone differs per band. This lets the LLM recover the strength of the true value
from the text, producing variance on the prediction side (= Pearson does not become nan).
Non-mentioned aspects emit no words at all (only mentioned aspects are appended).
"""

# ─────────────────────────────────────────────────────────────────────────────
# WARNING - Technical debt (KNOWN ISSUE / known coupling) - recorded 2026-06-20, unfixed (intentionally deferred)
#
# synth shares and imports config/districts.py (DISTRICTS) and config/cuisines.py (CUISINES),
# which are meant **for real data collection**. As a result, editing these for the sake of the
# real-collection scope changes the synthetic data distribution -- an unnecessary coupling (a
# side effect that is not the design intent).
#   - districts: via DISTRICTS[i % len] and the tourist tag, is_tourist->ambiance->star->FQS
#                shift deterministically (the random sequence is unchanged, but the derived
#                values via the tag change).
#   - cuisines : when the length of the list passed to rng.choice(CUISINES) changes, **the random
#                stream itself shifts** (a larger impact than districts).
#   Concrete example: when districts was expanded 14->20 for real collection in stage 2, the
#         synthetic evaluation numbers changed (e.g. divergence_report STEP2 Pearson r=0.226 -> 0.351).
#
# Correct design: synth should not depend on the real-collection lists and should have its own
#   **fixed synth-only lists** (e.g. SYNTH_DISTRICTS / SYNTH_CUISINES, or inject via
#   generate(districts=..., cuisines=...)).
# In this project the focus has shifted to real-data evaluation and synth has served its purpose,
# so it is not fixed now (to avoid changing the numbers again).
# **If synth is reused in the future, perform the decoupling above first.**
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import numpy as np

from config.cuisines import CUISINES
from config.districts import DISTRICTS
from ingest.schema import Place, Review

# Reference date for synthetic publish_time (fixed for determinism; independent of time_decay's "now")
REF_DATE = datetime(2026, 6, 20, tzinfo=timezone.utc)
MAX_AGE_DAYS = 1095  # Reviews are spread over roughly the past 3 years

# District tourist tag -> probability of being a tourist area
_TOURIST_P = {True: 0.85, False: 0.15, None: 0.5}

# Aspect mention templates (tone varies per true-value band so the LLM can recover the strength).
# Multiple options per band, chosen randomly -> the wording does not become monotonous.
_BANDS = {
    "food": {
        "high": ["the food was outstanding", "incredible flavors, the best I've had",
                 "absolutely delicious, perfectly cooked", "exceptional dishes, a real highlight"],
        "mid":  ["the food was good and satisfying", "solid, enjoyable dishes",
                 "decent food, tasty enough", "nice cooking, pretty good overall"],
        "low":  ["the food was okay, nothing special", "average dishes, a bit bland",
                 "fine but uninspired food", "mediocre and forgettable"],
        "vlow": ["the food was disappointing", "bland and overcooked, wouldn't return",
                 "tasteless dishes, a real letdown", "poor food for what it is"],
    },
    "service": {
        "high": ["staff were attentive and genuinely kind", "outstanding, warm service",
                 "the team went above and beyond"],
        "mid":  ["service was friendly and fine", "decent, helpful staff",
                 "good enough service"],
        "low":  ["service was slow and a bit careless", "indifferent staff",
                 "okay service, nothing more"],
        "vlow": ["rude and neglectful service", "we were ignored by the waiters",
                 "dismissive, terrible staff"],
    },
    "ambiance": {
        "high": ["a lovely terrace with a beautiful atmosphere", "stunning views and a great vibe",
                 "gorgeous, cozy setting"],
        "mid":  ["a pleasant atmosphere", "a nice enough setting",
                 "comfortable, decent vibe"],
        "low":  ["a bit cramped and noisy", "dull, forgettable decor",
                 "fairly average atmosphere"],
        "vlow": ["cramped, loud and unpleasant", "tacky tourist-trap decor",
                 "an uncomfortable, charmless room"],
    },
    "price": {  # high polarity = good value for money
        "high": ["great value for money", "very fair prices for the quality",
                 "honestly a bargain"],
        "mid":  ["reasonable prices", "fair enough for what it is",
                 "decent value"],
        "low":  ["a little pricey for what you get", "slightly overpriced",
                 "not the best value"],
        "vlow": ["badly overpriced", "expensive tourist prices, not worth it",
                 "way too costly for the quality"],
    },
}


def _band(polarity: float) -> str:
    """Map polarity[-1,1] to q=(p+1)/2 and return the true-value band (high/mid/low/very-low)."""
    q = (polarity + 1.0) / 2.0
    if q > 0.75:
        return "high"
    if q > 0.4:
        return "mid"
    if q > 0.2:
        return "low"
    return "vlow"


def _sentiment_text(aspect: str, polarity: float, rng: np.random.Generator) -> str:
    # rng.choice is called exactly once (invoked after the numeric true value is fixed, so the rng stream stays consistent)
    return str(rng.choice(_BANDS[aspect][_band(polarity)]))


def _mention(prob: float, rng: np.random.Generator) -> bool:
    return bool(rng.random() < prob)


def _polarity_from(center: float, rng: np.random.Generator, scale: float = 0.25) -> float:
    """Add noise around center and clip to [-1, 1]."""
    return float(np.clip(center + rng.normal(0.0, scale), -1.0, 1.0))


def _iso(days_ago: float) -> str:
    return (REF_DATE - timedelta(days=days_ago)).isoformat()


def generate(
    n_places: int = 120,
    seed: int = 42,
    reviews_per_place: Tuple[int, int] = (5, 25),
) -> Tuple[List[Place], List[Review]]:
    """Return synthetic (places, reviews). The reviews' aspect_* already embed the ground-truth."""
    rng = np.random.default_rng(seed)
    places: List[Place] = []
    reviews: List[Review] = []

    for i in range(n_places):
        district = DISTRICTS[i % len(DISTRICTS)]
        cuisine = str(rng.choice(CUISINES))

        # --- Latent variables ---
        true_food_quality = float(rng.beta(2, 2))                 # 0-1 (true food quality)
        is_tourist = bool(rng.random() < _TOURIST_P[district["tourist"]])
        # "Non-food appeal" such as ambiance, photogenic looks, terraces, etc. Higher in tourist areas. 0-1.
        ambiance = (float(rng.uniform(0.3, 1.0)) if is_tourist
                    else float(rng.uniform(0.0, 0.35)))

        # --- Aggregated star (inflates in an ambiance-driven way; Google's real inflation band ~3.4-4.9) ---
        appeal = 0.35 * true_food_quality + 0.65 * ambiance
        star = float(np.clip(3.4 + 1.7 * appeal + rng.normal(0.0, 0.18), 3.0, 5.0))

        food_mention_prob = 0.7 - 0.4 * is_tourist               # §4
        ambiance_mention_prob = 0.3 + 0.5 * is_tourist           # the more touristy, the more ambiance is talked about
        service_mention_prob = 0.5
        price_mention_prob = 0.3 + 0.3 * is_tourist

        review_count = int(rng.integers(15, 800))
        place_id = f"synth_{i:04d}"
        places.append(Place(
            place_id=place_id,
            name=f"{cuisine.title()} Place {i}",
            star_rating=round(star, 2),
            review_count=review_count,
            cuisine=cuisine,
            price_level=str(rng.choice(["PRICE_LEVEL_INEXPENSIVE",
                                        "PRICE_LEVEL_MODERATE",
                                        "PRICE_LEVEL_EXPENSIVE"])),
            lat=41.39 + float(rng.normal(0, 0.02)),
            lng=2.16 + float(rng.normal(0, 0.02)),
            district=district["name"],
            is_tourist_area=is_tourist,
            # Expose the latent variables solely for eval-label generation (just passing the
            #   existing values as-is; generation logic, numbers, and rng are unchanged. Never used
            #   in FQS computation = eval/proxy_labels only).
            true_food_quality=true_food_quality,
            true_ambiance=ambiance,
        ))

        # --- Individual reviews ---
        n_rev = int(rng.integers(reviews_per_place[0], reviews_per_place[1] + 1))
        for j in range(n_rev):
            # per-review star: varies around the aggregated star
            r_rating = int(np.clip(round(star + rng.normal(0, 0.6)), 1, 5))

            af = aser = aamb = apr = None
            parts: List[str] = []

            if _mention(food_mention_prob, rng):
                af = _polarity_from(2 * true_food_quality - 1, rng)
                parts.append(_sentiment_text("food", af, rng))
            if _mention(service_mention_prob, rng):
                aser = _polarity_from(rng.uniform(-0.3, 0.6), rng)
                parts.append(_sentiment_text("service", aser, rng))
            if _mention(ambiance_mention_prob, rng):
                aamb = _polarity_from(2 * ambiance - 0.4, rng)  # higher ambiance -> better impression
                parts.append(_sentiment_text("ambiance", aamb, rng))
            if _mention(price_mention_prob, rng):
                apr = _polarity_from(rng.uniform(-0.6, 0.3) if is_tourist
                                     else rng.uniform(-0.2, 0.5), rng)
                parts.append(_sentiment_text("price", apr, rng))

            if not parts:  # force at least one aspect to be mentioned (avoid empty reviews)
                aser = _polarity_from(0.0, rng)
                parts.append(_sentiment_text("service", aser, rng))

            reviews.append(Review(
                place_id=place_id,
                review_id=f"{place_id}_r{j:03d}",
                rating=r_rating,
                text=". ".join(parts) + ".",
                lang="en",
                author_id=f"user_{int(rng.integers(0, 5000)):05d}",
                publish_time=_iso(float(rng.uniform(0, MAX_AGE_DAYS))),
                has_photo=bool(rng.random() < 0.4),
                photo_count=int(rng.integers(0, 4)),
                aspect_food=af,
                aspect_service=aser,
                aspect_ambiance=aamb,
                aspect_price=apr,
            ))

    return places, reviews


if __name__ == "__main__":
    places, reviews = generate(n_places=120, seed=42)
    tourist = [p for p in places if p.is_tourist_area]
    local = [p for p in places if not p.is_tourist_area]
    food_mentions = sum(r.aspect_food is not None for r in reviews)
    print(f"synth.py OK: {len(places)} places, {len(reviews)} reviews")
    print(f"  tourist={len(tourist)} local={len(local)}")
    print(f"  mean star tourist={np.mean([p.star_rating for p in tourist]):.2f} "
          f"local={np.mean([p.star_rating for p in local]):.2f}")
    print(f"  food mention rate={food_mentions / len(reviews):.2%}")

    # --- Check wording tone per band (food): one review per band with a distinct true value ---
    print("\n  [food] wording tone per true-value band (aspect_food=truth / text):")
    seen = set()
    for r in sorted((x for x in reviews if x.aspect_food is not None),
                    key=lambda x: x.aspect_food):  # low -> high order
        b = _band(r.aspect_food)
        if b in seen:
            continue
        seen.add(b)
        food_part = next((p for p in r.text.split(". ") if "food" in p or "dish" in p
                          or "flavor" in p or "cook" in p or "delicious" in p), r.text)
        print(f"    {b:5} truth={r.aspect_food:+.2f}  «{food_part.strip().rstrip('.')}»")
        if len(seen) == 4:
            break
    # Non-mention check: no food words appear in reviews that do not mention food
    food_words = ("food", "dish", "flavor", "cook", "delicious", "paella", "tasteless",
                  "bland", "overcooked")
    leak = [r for r in reviews if r.aspect_food is None
            and any(w in r.text.lower() for w in food_words)]
    print(f"  food-word leak into food-non-mention reviews: {len(leak)} (should be 0)")
