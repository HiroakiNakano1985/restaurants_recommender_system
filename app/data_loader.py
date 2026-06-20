"""Thin data loader for the Streamlit demo UI (§8).

Its only job is to "read the existing pipeline's outputs and hand them to the UI". It builds a
DataFrame by **only calling the existing functions** — the synth / ABSA / fqs / rerank / eval
logic is never changed.

Right now there are no persisted artifacts (e.g. Parquet under data/processed) yet, so it runs
the synthetic pipeline in memory to produce the data (cached with st.cache_data). Once real data
is available, only the generation block inside `build_dataset` needs to be swapped for a Parquet
read — the UI stays unchanged.

The weight sliders (half_life / cuisine normalization) trigger a **live recompute** (cheap for
~120 stores). This lets the demo show "changing the weights moves the FQS ranking". The recompute
just calls the existing score_places / rerank — no logic change.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import streamlit as st
    cache = st.cache_data
except Exception:                      # fallback so it also works without streamlit (unit tests)
    def cache(func=None, **_kw):
        return func if func else (lambda f: f)

from ingest.synth import generate
from nlp.absa import get_analyzer
from rerank.personalize import compute_aspect_scores
from rerank.reranker import rerank
from scoring.fqs import score_places
from scoring.weights import Weights

NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)   # fixed for determinism
ASPECTS = ("food", "service", "ambiance", "price")


def _food_mention_rate(reviews) -> float:
    if not reviews:
        return 0.0
    return sum(r.aspect_food is not None for r in reviews) / len(reviews)


def _representative_food_review(reviews, place_fqs: Optional[float]) -> Optional[dict]:
    """Return the food-mentioning review closest to the store's FQS as its representative (explainability)."""
    food_revs = [r for r in reviews if r.aspect_food is not None]
    if not food_revs:
        return None
    target = place_fqs if place_fqs is not None else 0.0
    best = min(food_revs, key=lambda r: abs(r.aspect_food - target))
    return {"text": best.text, "rating": best.rating, "aspect_food": best.aspect_food,
            "publish_time": best.publish_time}


@cache(show_spinner=False)
def build_dataset(
    n_places: int = 120,
    seed: int = 42,
    half_life_days: int = 365,
    normalize_by_cuisine: bool = True,
    scope: str = "district_cuisine",
    source: str = "synthetic",
) -> Tuple[pd.DataFrame, Dict[str, List[dict]], list, dict]:
    """Return (places_df, reviews_by_place, places, aspect_scores). `source` is the real-data swap point.

    `places` (Place objects with FQS/rank filled) and `aspect_scores`
    ({place_id: {food/service/ambiance/price: score}}) are returned so the UI can call
    rerank.personalize.personalize() (Layer 2) directly with the precomputed aspect scores.

    source="synthetic": run the synthetic pipeline in memory (current)
    source="parquet"  : read the artifacts under data/processed (just add this once real data exists)
    """
    if source != "synthetic":
        raise NotImplementedError(
            "Real-data loading (Parquet) will be added to this function after real data is fetched. "
            "The UI only depends on the shape of this function's return value, so it needs no change."
        )

    # --- existing pipeline (logic unchanged; only called) ---
    places, reviews = generate(n_places=n_places, seed=seed)
    get_analyzer("simple").analyze(reviews)
    weights = Weights(half_life_days=half_life_days,
                      normalize_by_cuisine=normalize_by_cuisine)
    score_places(places, reviews, weights, now=NOW)
    rerank(places, scope=scope)
    # Layer-2 input: per-aspect scores (same aggregation as FQS; food == place.fqs)
    aspect_scores = compute_aspect_scores(places, reviews, weights, now=NOW)

    by_place: Dict[str, list] = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)

    rows = []
    reviews_by_place: Dict[str, List[dict]] = {}
    for p in places:
        prevs = by_place.get(p.place_id, [])
        rep = _representative_food_review(prevs, p.fqs)
        rows.append({
            "place_id": p.place_id,
            "name": p.name,
            "district": p.district,
            "cuisine": p.cuisine,
            "price_level": p.price_level,
            "is_tourist_area": p.is_tourist_area,
            "star_rating": p.star_rating,
            "fqs": p.fqs,
            "star_rank": p.star_rank,
            "fqs_rank": p.fqs_rank,
            "rank_delta": p.rank_delta,
            "review_count": p.review_count,
            "lat": p.lat,
            "lng": p.lng,
            "food_mention_rate": _food_mention_rate(prevs),
            "n_reviews": len(prevs),
            "rep_review": rep["text"] if rep else None,
            "rep_rating": rep["rating"] if rep else None,
        })
        reviews_by_place[p.place_id] = [
            {"text": r.text, "rating": r.rating,
             **{f"aspect_{a}": getattr(r, f"aspect_{a}") for a in ASPECTS}}
            for r in prevs
        ]
    df = pd.DataFrame(rows)
    return df, reviews_by_place, places, aspect_scores


def classify(rank_delta: Optional[int]) -> str:
    """Store type from rank_delta. >0 = discovered gem, <0 = tourist trap, 0 = no change."""
    if rank_delta is None:
        return "neutral"
    if rank_delta > 0:
        return "gem"
    if rank_delta < 0:
        return "trap"
    return "neutral"


if __name__ == "__main__":
    # Unit test (works even without streamlit)
    df, rbp, places, asc = build_dataset()
    assert len(df) == 120 and "fqs" in df.columns and len(places) == 120 and len(asc) == 120
    # The sort-axis toggle must reshuffle the ranking
    by_star = list(df.sort_values("star_rating", ascending=False)["place_id"])
    by_fqs = list(df.sort_values("fqs", ascending=False)["place_id"])
    assert by_star != by_fqs, "star order and FQS order are identical (toggle would be meaningless)"
    n_trap = (df["rank_delta"] < 0).sum()
    n_gem = (df["rank_delta"] > 0).sum()
    # Changing the weights must change FQS
    df2, _, _, _ = build_dataset(normalize_by_cuisine=False)
    changed = (df.set_index("place_id")["fqs"] !=
               df2.set_index("place_id")["fqs"]).any()
    print(f"data_loader.py OK: {len(df)} places, "
          f"top star!=fqs order={by_star[:3]!=by_fqs[:3]}")
    print(f"  traps={n_trap} gems={n_gem}  weight-change alters FQS={bool(changed)}")
    print(f"  sample card: {df.iloc[0]['name']} star={df.iloc[0]['star_rating']} "
          f"fqs={df.iloc[0]['fqs']} food_mention={df.iloc[0]['food_mention_rate']:.0%}")
