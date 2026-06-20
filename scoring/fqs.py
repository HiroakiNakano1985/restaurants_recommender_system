"""Design 2 §6: Module C — Food Quality Score (FQS) computation.

A place's FQS = weighted average of the food-aspect sentiment over reviews that
mention food.
Weight = time decay (③) × reviewer credibility (②, McAuley only).
Per-cuisine normalization (④) is applied in a second pass once the raw FQS of all
places is available (it needs per-cuisine statistics, so it was moved from the
call site in Design 2 §6 into the orchestration layer).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from ingest.schema import Place, Review
from scoring.weights import Weights


def time_decay(publish_time: Optional[str], half_life_days: int,
               now: Optional[datetime] = None) -> float:
    """③ Time decay: weight halves for every half_life of age. Returns 1.0 if time is unknown."""
    if not publish_time:
        return 1.0
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat(publish_time)
    except ValueError:
        return 1.0
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - t).total_seconds() / 86400.0)
    return float(0.5 ** (age_days / half_life_days))


def reviewer_weight(author_id: Optional[str], weights: Weights) -> float:
    """② Reviewer credibility. Enabled only for McAuley (where author history exists).

    Synthetic/Places data has no history, so use_reviewer_weight=False → 1.0.
    Once reviewer_profile.py returns a food-focus score in the future, apply a
    boost here.
    """
    if not weights.use_reviewer_weight:
        return 1.0
    # TODO(McAuley): pull the food-focus score from reviewer_profile and boost. Neutral for now.
    return 1.0


def weighted_mean(values: Sequence[float], wts: Sequence[float]) -> Optional[float]:
    total_w = sum(wts)
    if total_w <= 0:
        return None
    return float(sum(v * w for v, w in zip(values, wts)) / total_w)


def compute_fqs_raw(place_reviews: List[Review], weights: Weights,
                    now: Optional[datetime] = None) -> Optional[float]:
    """Raw FQS for a single place (before cuisine normalization). None if food is never mentioned."""
    values: List[float] = []
    wts: List[float] = []
    for r in place_reviews:
        if r.aspect_food is None:          # exclude reviews that don't mention food (§6)
            continue
        w = 1.0
        w *= time_decay(r.publish_time, weights.half_life_days, now)  # ③
        w *= reviewer_weight(r.author_id, weights)                    # ②
        values.append(r.aspect_food)
        wts.append(w)
    if not values:
        return None
    return weighted_mean(values, wts)


def _normalize_by_cuisine(places: List[Place]) -> None:
    """④ Per-cuisine normalization: subtract the per-cuisine baseline (mean) and add back the global mean.

    Uses mean-centering rather than z-score —— this removes only the cross-cuisine
    bias (the difference in star baselines between, e.g., sushi vs. tapas) while
    preserving the FQS scale (≈[-1,1]) and within-place variance, for interpretability.
    """
    by_cuisine: Dict[Optional[str], List[Place]] = defaultdict(list)
    scored = [p for p in places if p.fqs is not None]
    if not scored:
        return
    global_mean = sum(p.fqs for p in scored) / len(scored)
    for p in scored:
        by_cuisine[p.cuisine].append(p)
    for group in by_cuisine.values():
        c_mean = sum(p.fqs for p in group) / len(group)
        for p in group:
            p.fqs = round(p.fqs - c_mean + global_mean, 4)


def score_places(places: List[Place], reviews: List[Review], weights: Weights,
                 now: Optional[datetime] = None) -> List[Place]:
    """Compute FQS for all places and store it in place.fqs (2 passes: raw → cuisine normalization)."""
    by_place: Dict[str, List[Review]] = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)
    for p in places:
        raw = compute_fqs_raw(by_place.get(p.place_id, []), weights, now)
        p.fqs = None if raw is None else round(raw, 4)
    if weights.normalize_by_cuisine:
        _normalize_by_cuisine(places)
    return places


if __name__ == "__main__":
    from ingest.synth import generate
    from nlp.absa import get_analyzer

    places, reviews = generate(n_places=120, seed=42)
    reviews = get_analyzer("simple").analyze(reviews)

    # monotonicity check for time_decay
    assert time_decay("2026-06-20T00:00:00+00:00", 365,
                      now=datetime(2026, 6, 20, tzinfo=timezone.utc)) == 1.0
    older = time_decay("2025-06-20T00:00:00+00:00", 365,
                       now=datetime(2026, 6, 20, tzinfo=timezone.utc))
    assert abs(older - 0.5) < 1e-6, older  # 1 half-life

    score_places(places, reviews, Weights(),
                 now=datetime(2026, 6, 20, tzinfo=timezone.utc))
    scored = [p for p in places if p.fqs is not None]
    print(f"fqs.py OK: {len(scored)}/{len(places)} places scored")
    print(f"  FQS range: [{min(p.fqs for p in scored):.3f}, "
          f"{max(p.fqs for p in scored):.3f}]")
    import numpy as np
    fqs = np.array([p.fqs for p in scored])
    star = np.array([p.star_rating for p in scored])
    print(f"  Pearson(star, FQS) = {np.corrcoef(star, fqs)[0, 1]:.3f} "
          f"(the lower it is, the stronger the divergence)")
