"""Layer 2 of the recommender: preference-weighted aspect scoring (Blueprint 2 §5).

  - Layer 1 (existing): de-biasing. FQS extracts food-only quality from reviews. Shared by all users.
  - Layer 2 (this file): personalization. The ABSA-derived per-aspect sentiments
    (food / service / ambiance / price) are aggregated per store, and each user supplies aspect
    weights, so a "food-first" user and an "ambiance-matters" user get *different* recommendations.

Content-based only. Collaborative filtering is intentionally NOT implemented: the Google Places API
does not expose reviewer identity (author_id), so a user x item matrix cannot be built (this
constraint is noted in Blueprint 1 §1).

Design notes (deliberate, reversible):
  - `food_score` = the already-computed, cuisine-normalized `place.fqs`. Using it (rather than
    recomputing) guarantees the sanity property: weights = {food: 1.0} reproduces the FQS order.
  - service / ambiance / price scores use the SAME review aggregation as FQS — a time-decay
    weighted mean over reviews that mention the aspect (unmentioned -> None -> excluded) — via the
    public helpers in scoring/fqs.py. No cuisine normalization for non-food aspects (the cuisine
    baseline is a food-quality concern). scoring/fqs.py itself is NOT modified.
  - Sparse aspects: each store's personalized score is a weighted mean RENORMALIZED over the
    aspects actually present, so a store missing (say) ambiance reviews is scored on its remaining
    weighted aspects rather than penalized to zero. A store is excluded only if none of the
    weighted aspects are present.

FQS is consumed as-is; ABSA / FQS / the existing Layer-1 rerank are not modified.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from ingest.schema import Place
from scoring.fqs import reviewer_weight, time_decay, weighted_mean
from scoring.weights import Weights

ASPECTS = ("food", "service", "ambiance", "price")

# Google price-level enum -> ordinal, so "max_price_level" can be compared.
_PRICE_ORDER = {"FREE": 0, "INEXPENSIVE": 1, "MODERATE": 2, "EXPENSIVE": 3, "VERY_EXPENSIVE": 4}


@dataclass
class Rec:
    """One personalized recommendation: the place, its blended score, and the breakdown."""
    place: Place
    score: float
    aspect_scores: Dict[str, Optional[float]]   # per-aspect aggregated score (None if unmentioned)
    contributions: Dict[str, float]             # effective_weight x aspect_score (sums to `score`)
    weights: Dict[str, float]                   # normalized weights actually used


# ---------------------------------------------------------------- aspect aggregation
def _aggregate_aspect(reviews, aspect: str, weights: Weights, now) -> Optional[float]:
    """Same aggregation as FQS, for an arbitrary aspect: time-decay weighted mean of the
    mentioned reviews (None excluded). Returns None if no review mentions the aspect."""
    values: List[float] = []
    wts: List[float] = []
    for r in reviews:
        v = getattr(r, f"aspect_{aspect}")
        if v is None:
            continue
        w = time_decay(r.publish_time, weights.half_life_days, now) * reviewer_weight(r.author_id, weights)
        values.append(v)
        wts.append(w)
    if not values:
        return None
    return weighted_mean(values, wts)


def compute_aspect_scores(places: List[Place], reviews, weights: Optional[Weights] = None,
                          now=None) -> Dict[str, Dict[str, Optional[float]]]:
    """Per-store {aspect: score}. `food` is overridden with place.fqs (cuisine-normalized) so that
    weights={food:1.0} reproduces the FQS ranking exactly."""
    weights = weights or Weights()
    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for p in places:
        prevs = by_place.get(p.place_id, [])
        sc = {a: _aggregate_aspect(prevs, a, weights, now) for a in ASPECTS}
        sc["food"] = p.fqs                       # keep food == the project's de-biased FQS
        out[p.place_id] = sc
    return out


# ---------------------------------------------------------------- weighting / scoring
def _normalize_weights(w: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Normalize aspect weights to sum 1 (negatives clipped). Empty/zero -> food-only (= FQS)."""
    default = {"food": 1.0, "service": 0.0, "ambiance": 0.0, "price": 0.0}
    if not w:
        return default
    clean = {a: max(0.0, float(w.get(a, 0.0))) for a in ASPECTS}
    total = sum(clean.values())
    if total <= 0:
        return default
    return {a: clean[a] / total for a in ASPECTS}


def _personal_score(scores: Dict[str, Optional[float]], nweights: Dict[str, float]):
    """Weighted mean over the aspects that are both weighted (>0) and present (not None),
    renormalizing the weights over what is present. Returns (score, contributions) or (None, {})."""
    present = [(a, nweights[a], scores.get(a)) for a in ASPECTS
               if nweights.get(a, 0.0) > 0 and scores.get(a) is not None]
    den = sum(w for _, w, _ in present)
    if den <= 0:
        return None, {}
    contributions = {a: (w / den) * s for a, w, s in present}
    return sum(contributions.values()), contributions


# ---------------------------------------------------------------- filters
def _price_ord(price_level: Optional[str]) -> Optional[int]:
    if not price_level:
        return None
    return _PRICE_ORDER.get(price_level.upper().replace("PRICE_LEVEL_", ""))


def _passes_filters(p: Place, prefs: Dict) -> bool:
    cuisines = prefs.get("cuisines")
    districts = prefs.get("districts")
    min_star = prefs.get("min_star")
    max_price = _price_ord(prefs.get("max_price_level")) if prefs.get("max_price_level") else None
    if cuisines and p.cuisine not in cuisines:
        return False
    if districts and p.district not in districts:
        return False
    if min_star is not None and (p.star_rating is None or p.star_rating < min_star):
        return False
    if max_price is not None:
        po = _price_ord(p.price_level)
        if po is not None and po > max_price:    # keep unknown price (po is None)
            return False
    return True


# ---------------------------------------------------------------- main entry
def personalize(places: List[Place], prefs: Optional[Dict] = None,
                aspect_scores: Optional[Dict] = None, reviews=None,
                top_n: int = 10) -> List[Rec]:
    """Layer 2: filter by `prefs`, score each survivor by the weighted blend of its aspect scores,
    and return the top_n as `Rec` objects (ordered by personalized score, desc).

    prefs (all keys optional; empty prefs => every place by FQS == Layer 1):
        "weights":         {food,service,ambiance,price} -> normalized to sum 1 (default food=1.0)
        "cuisines":        list[str]
        "districts":       list[str]
        "max_price_level": str    (e.g. "MODERATE"; unknown-price places are kept)
        "min_star":        float

    Aspect scores source (in priority order): `aspect_scores` map -> computed from `reviews` ->
    food-only from place.fqs (when neither is given, only the food weight is usable).
    """
    prefs = prefs or {}
    nw = _normalize_weights(prefs.get("weights"))
    if aspect_scores is None:
        if reviews is not None:
            aspect_scores = compute_aspect_scores(places, reviews)
        else:
            aspect_scores = {p.place_id: {"food": p.fqs} for p in places}

    recs: List[Rec] = []
    for p in places:
        if not _passes_filters(p, prefs):
            continue
        sc = aspect_scores.get(p.place_id, {})
        score, contrib = _personal_score(sc, nw)
        if score is None:                        # no weighted aspect present -> not recommendable
            continue
        recs.append(Rec(p, score, sc, contrib, nw))
    recs.sort(key=lambda r: (-r.score, r.place.place_id))
    return recs[:top_n]


if __name__ == "__main__":
    # Self-check on synthetic data: sanity (food=1.0 == FQS) + persona separation.
    from datetime import datetime, timezone

    from ingest.synth import generate
    from nlp.absa import get_analyzer
    from scoring.fqs import score_places

    places, reviews = generate(n_places=200, seed=42)
    get_analyzer("simple").analyze(reviews)
    score_places(places, reviews, Weights(),
                 now=datetime(2026, 6, 20, tzinfo=timezone.utc))
    asc = compute_aspect_scores(places, reviews,
                                now=datetime(2026, 6, 20, tzinfo=timezone.utc))

    # aspect coverage (sparsity check)
    cov = {a: sum(1 for p in places if asc[p.place_id][a] is not None) for a in ASPECTS}
    print("aspect coverage (places with a non-None score):",
          {a: f"{cov[a]}/{len(places)}" for a in ASPECTS})

    # 1) SANITY: weights food=1.0 must reproduce the FQS order
    food_only = personalize(places, {"weights": {"food": 1.0}}, aspect_scores=asc, top_n=10)
    fqs_order = sorted((p for p in places if p.fqs is not None),
                       key=lambda p: (-p.fqs, p.place_id))[:10]
    assert [r.place.place_id for r in food_only] == [p.place_id for p in fqs_order], \
        "food=1.0 did NOT reproduce FQS order"
    print("SANITY OK: weights{food:1.0} == FQS order")

    # 2) ambiance-first vs food-first -> different top places
    food_first = personalize(places, {"weights": {"food": 1.0}}, aspect_scores=asc, top_n=10)
    amb_first = personalize(places, {"weights": {"ambiance": 1.0}}, aspect_scores=asc, top_n=10)
    top_f = [r.place.place_id for r in food_first[:5]]
    top_a = [r.place.place_id for r in amb_first[:5]]
    print(f"food-first top5 != ambiance-first top5: {top_f != top_a}")
    assert top_f != top_a

    # 3) realistic personas
    personas = {
        "food-first, cheap": {"weights": {"food": 0.8, "price": 0.2},
                              "max_price_level": "MODERATE"},
        "ambiance matters":  {"weights": {"food": 0.4, "ambiance": 0.4, "service": 0.2}},
    }
    for label, prefs in personas.items():
        recs = personalize(places, prefs, aspect_scores=asc, top_n=3)
        print(f"\n[{label}] weights={recs[0].weights if recs else '-'}")
        for r in recs:
            br = " ".join(f"{a}:{v:+.2f}" for a, v in r.contributions.items())
            print(f"   {r.place.name[:24]:24} score {r.score:+.2f}  ({br})")
    print("\npersonalize.py OK: aspect-weighted scoring, sanity + persona separation verified")
