"""Generate the ANONYMIZED real-data file the public Streamlit app reads.

Reads the LOCAL, gitignored raw data (data/raw/bcn.jsonl + data/processed/bcn_absa.jsonl),
recomputes FQS / rerank / per-aspect scores, and writes ONLY non-personal fields to
app/public_data/bcn_real_public.csv (which IS committed).

PRIVACY / ToS: review *text* and author *names* are personal data (GDPR) and subject to Google
Places caching limits — they are **dropped here and never published**. Published fields are place
facts (name, location, cuisine, price, star, review count — shown with Google attribution in the
app) plus our own derived scores (FQS, per-aspect sentiment, food-mention rate = an aggregate
count). This generator needs the local raw data and CANNOT run on Streamlit Cloud — it is a one-off
run by the maintainer; the committed CSV is the only thing the deployed app uses.

Run locally:  python -m tools.make_public_real_data
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import datetime, timezone

from ingest.places_grid import load_bcn_jsonl
from nlp.absa import ASPECTS
from rerank.personalize import compute_aspect_scores
from rerank.reranker import rerank
from scoring.fqs import score_places
from scoring.weights import Weights

NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "public_data",
                   "bcn_real_public.csv")

# Columns that are SAFE to publish (no review text, no author names).
COLUMNS = [
    "place_id", "name", "district", "cuisine", "price_level", "is_tourist_area",
    "star_rating", "review_count", "fqs", "star_rank", "fqs_rank", "rank_delta",
    "lat", "lng", "food_mention_rate", "n_reviews",
    "aspect_food", "aspect_service", "aspect_ambiance", "aspect_price",
]
# Hard block-list: these must NEVER appear in the public file.
FORBIDDEN = {"text", "author_name", "author_id", "rep_review", "review_id", "relative_time"}


def main() -> None:
    from analysis.real_divergence_report import load_absa_cache, _akey

    places, reviews = load_bcn_jsonl()
    cache = load_absa_cache()
    for r in reviews:
        c = cache.get(_akey(r))
        if c is not None:
            for a in ASPECTS:
                setattr(r, f"aspect_{a}", c[a])

    score_places(places, reviews, Weights(), now=NOW)
    rerank(places, scope="district_cuisine")
    aspect_scores = compute_aspect_scores(places, reviews, now=NOW)

    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)

    assert not (set(COLUMNS) & FORBIDDEN), "a forbidden (personal-data) column slipped into COLUMNS"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n = 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for p in places:
            if p.fqs is None:                 # no food signal -> not useful for the demo
                continue
            prevs = by_place.get(p.place_id, [])
            n_food = sum(1 for r in prevs if r.aspect_food is not None)
            sc = aspect_scores.get(p.place_id, {})
            w.writerow({
                "place_id": p.place_id, "name": p.name, "district": p.district,
                "cuisine": p.cuisine, "price_level": p.price_level,
                "is_tourist_area": p.is_tourist_area, "star_rating": p.star_rating,
                "review_count": p.review_count, "fqs": p.fqs, "star_rank": p.star_rank,
                "fqs_rank": p.fqs_rank, "rank_delta": p.rank_delta,
                "lat": round(p.lat, 6), "lng": round(p.lng, 6),
                "food_mention_rate": round(n_food / len(prevs), 4) if prevs else 0.0,
                "n_reviews": len(prevs),
                "aspect_food": sc.get("food"), "aspect_service": sc.get("service"),
                "aspect_ambiance": sc.get("ambiance"), "aspect_price": sc.get("price"),
            })
            n += 1

    print(f"wrote {n} anonymized places -> {os.path.relpath(OUT)}")
    print(f"published columns (NO review text / author): {COLUMNS}")


if __name__ == "__main__":
    main()
