"""Blueprint 2 §7: Module D — re-ranking + rank delta.

Within the same area and same cuisine, compare the star order against the
FQS order and assign star_rank / fqs_rank / rank_delta to each place.

    rank_delta = star_rank - fqs_rank
    rank_delta > 0 : low on stars but rises on FQS = hidden gem
    rank_delta < 0 : high on stars but falls on FQS = tourist trap
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from ingest.schema import Place

Scope = str


def _group_key(p: Place, scope: Scope) -> Tuple:
    if scope == "district_cuisine":
        return (p.district, p.cuisine)
    if scope == "district":
        return (p.district,)
    if scope == "cuisine":
        return (p.cuisine,)
    if scope == "global":
        return ("__all__",)
    raise ValueError(f"unknown scope: {scope}")


def group_by(places: List[Place], scope: Scope) -> Dict[Tuple, List[Place]]:
    groups: Dict[Tuple, List[Place]] = defaultdict(list)
    for p in places:
        groups[_group_key(p, scope)].append(p)
    return groups


def _assign_ranks(group: List[Place], key: Callable[[Place], float], attr: str) -> None:
    """Assign ranks 1..N in descending key order to attr (tie-broken by place_id, stable sort)."""
    ordered = sorted(group, key=lambda p: (-key(p), p.place_id))
    for rank, p in enumerate(ordered, start=1):
        setattr(p, attr, rank)


def rerank(places: List[Place], scope: Scope = "district_cuisine") -> List[Place]:
    """Compare star order and FQS order within the same area and cuisine, assigning rank_delta.

    Places with FQS == None (no food mention) are treated as lowest-ranked (-inf).
    """
    for group in group_by(places, scope).values():
        _assign_ranks(group, lambda p: p.star_rating, "star_rank")
        _assign_ranks(group, lambda p: (p.fqs if p.fqs is not None else float("-inf")),
                      "fqs_rank")
        for p in group:
            p.rank_delta = p.star_rank - p.fqs_rank
    return places


def movers(places: List[Place], top: int = 10) -> Dict[str, List[Place]]:
    """Extract places with the largest/smallest rank_delta (for the before/after table and Figure 3)."""
    ranked = [p for p in places if p.rank_delta is not None]
    by_up = sorted(ranked, key=lambda p: (-p.rank_delta, p.place_id))
    by_down = sorted(ranked, key=lambda p: (p.rank_delta, p.place_id))
    return {
        "gems": [p for p in by_up if p.rank_delta > 0][:top],     # hidden gems
        "traps": [p for p in by_down if p.rank_delta < 0][:top],  # tourist traps
    }


if __name__ == "__main__":
    from datetime import datetime, timezone

    from ingest.synth import generate
    from nlp.absa import get_analyzer
    from scoring.fqs import score_places
    from scoring.weights import Weights

    places, reviews = generate(n_places=120, seed=42)
    reviews = get_analyzer("simple").analyze(reviews)
    score_places(places, reviews, Weights(),
                 now=datetime(2026, 6, 20, tzinfo=timezone.utc))
    rerank(places, scope="district_cuisine")

    # Consistency check: within each group the ranks form a permutation of 1..N
    for key, group in group_by(places, "district_cuisine").items():
        n = len(group)
        assert sorted(p.star_rank for p in group) == list(range(1, n + 1))
        assert sorted(p.fqs_rank for p in group) == list(range(1, n + 1))
        for p in group:
            assert p.rank_delta == p.star_rank - p.fqs_rank

    mv = movers(places, top=5)
    print(f"rerank.py OK: {len(places)} places ranked within district×cuisine")
    print(f"  gems (star down, FQS up): {len(mv['gems'])}  traps (star up, FQS down): {len(mv['traps'])}")
    for p in mv["traps"][:3]:
        print(f"   TRAP {p.name[:24]:24} star#{p.star_rank} -> fqs#{p.fqs_rank} "
              f"(delta {p.rank_delta})  star={p.star_rating} fqs={p.fqs}")
