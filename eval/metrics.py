"""Blueprint 2 §9 / Blueprint 1 §3-B,3-C: evaluation metrics (star ranking vs FQS ranking).

Against the proxy ground truth (set of listed places), compare the ranking quality of the
star order and the FQS order side by side.

  - Precision@K / Recall@K / NDCG@K (K=5,10,20)
  - AUC (as binary classification of listed/not-listed; computed via Mann-Whitney U, no added dependency)
  - The return value is {"star": {...}, "fqs": {...}} so the two can be compared directly
  - Scope: both global evaluation and within-group evaluation (same district x cuisine, Blueprint 2 §7)
  - ablation: turn each signal of Weights ON/OFF one at a time and tabulate how the FQS metrics move

WARNING: true_food_quality is never used here (labels are supplied separately by proxy_labels).
  FQS is used as-is, as computed from aspect_food by scoring/fqs.py.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ingest.schema import Place
from rerank.reranker import group_by            # reuse existing grouping (do not change)
from scoring.fqs import score_places            # used for re-scoring in ablation
from scoring.weights import Weights

NEG_INF = float("-inf")


# ---------------------------------------------------------------- low-level metrics
def _score(p: Place, attr: str) -> float:
    v = getattr(p, attr)
    if v is None:                 # FQS not computed (places with no food mention) ranked last
        return NEG_INF
    return float(v)


def rank_desc(places: List[Place], attr: str) -> List[Place]:
    """Descending by score (ties stabilized by place_id)."""
    return sorted(places, key=lambda p: (-_score(p, attr), p.place_id))


def precision_at_k(ranked_ids: Sequence[str], labels: Set[str], k: int) -> float:
    if k <= 0:
        return float("nan")
    hits = sum(1 for pid in ranked_ids[:k] if pid in labels)
    return hits / k


def recall_at_k(ranked_ids: Sequence[str], labels: Set[str], k: int) -> float:
    total = sum(1 for pid in ranked_ids if pid in labels)  # number of listed places in the pool
    if total == 0:
        return float("nan")
    hits = sum(1 for pid in ranked_ids[:k] if pid in labels)
    return hits / total


def ndcg_at_k(ranked_ids: Sequence[str], labels: Set[str], k: int) -> float:
    rels = [1 if pid in labels else 0 for pid in ranked_ids[:k]]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
    n_pos = sum(1 for pid in ranked_ids if pid in labels)
    ideal = min(k, n_pos)
    idcg = sum(1 / math.log2(i + 2) for i in range(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def roc_auc(scores: Sequence[float], y_true: Sequence[bool]) -> float:
    """AUC = P(score(pos) > score(neg)). Mann-Whitney U (ties handled with average rank)."""
    n = len(scores)
    n_pos = sum(1 for y in y_true if y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = sorted(range(n), key=lambda i: scores[i])   # ascending
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0                # 1-based average rank
        for t in range(i, j + 1):
            ranks[order[t]] = avg_rank
        i = j + 1
    sum_pos = sum(ranks[i] for i in range(n) if y_true[i])
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


# ---------------------------------------------------------------- evaluate (per pool)
def evaluate(places: List[Place], labels: Set[str],
             ks: Tuple[int, ...] = (5, 10, 20), cap_k: bool = False) -> Dict:
    """Evaluate star and fqs side by side. If cap_k=True, round K down to the pool size (for small groups)."""
    n = len(places)
    n_pos = sum(1 for p in places if p.place_id in labels)
    out: Dict[str, Dict] = {}
    for scorer, attr in (("star", "star_rating"), ("fqs", "fqs")):
        ranked = rank_desc(places, attr)
        ids = [p.place_id for p in ranked]
        scores = [_score(p, attr) for p in ranked]
        y = [p.place_id in labels for p in ranked]
        d: Dict[str, float] = {}
        for k in ks:
            keff = min(k, n) if cap_k else k
            d[f"precision@{k}"] = precision_at_k(ids, labels, keff)
            d[f"recall@{k}"] = recall_at_k(ids, labels, keff)
            d[f"ndcg@{k}"] = ndcg_at_k(ids, labels, keff)
        d["auc"] = roc_auc(scores, y)
        out[scorer] = d
    out["_meta"] = {"n": n, "n_positive": n_pos, "ks": list(ks)}
    return out


def evaluate_grouped(places: List[Place], labels: Set[str],
                     scope: str = "district_cuisine",
                     ks: Tuple[int, ...] = (5, 10, 20)) -> Dict:
    """Evaluate within the same district x cuisine and macro-average over groups that contain a listed place."""
    groups = group_by(places, scope)
    acc = {"star": defaultdict(list), "fqs": defaultdict(list)}
    used = 0
    for g in groups.values():
        if not any(p.place_id in labels for p in g):   # exclude groups with zero listed places
            continue
        used += 1
        res = evaluate(g, labels, ks, cap_k=True)
        for scorer in ("star", "fqs"):
            for m, v in res[scorer].items():
                if v == v:                              # exclude NaN
                    acc[scorer][m].append(v)
    out: Dict[str, Dict] = {"star": {}, "fqs": {}}
    for scorer in ("star", "fqs"):
        for m, vs in acc[scorer].items():
            out[scorer][m] = sum(vs) / len(vs) if vs else float("nan")
    out["_meta"] = {"scope": scope, "groups_used": used,
                    "groups_total": len(groups), "ks": list(ks)}
    return out


def evaluate_both(places: List[Place], labels: Set[str],
                  ks: Tuple[int, ...] = (5, 10, 20),
                  scope: str = "district_cuisine") -> Dict:
    """Return both global and within-group evaluation (pick the primary metric after seeing the results)."""
    return {
        "global": evaluate(places, labels, ks),
        "grouped": evaluate_grouped(places, labels, scope, ks),
    }


# ---------------------------------------------------------------- ablation
# Blueprint 2 §6 / Blueprint 1 §3-C: remove each signal one at a time, recompute FQS, and observe how the metrics change.
ABLATIONS: List[Tuple[str, Dict]] = [
    ("full",                {}),
    ("no_time_decay",       {"half_life_days": 10 ** 9}),
    ("no_cuisine_norm",     {"normalize_by_cuisine": False}),
    ("no_reviewer_weight",  {"use_reviewer_weight": False}),  # already inert in synth
]


def ablation_table(places: List[Place], reviews, base_weights: Weights,
                   labels: Set[str], ks: Tuple[int, ...] = (5, 10, 20),
                   now=None) -> List[Dict]:
    """For each ablation config, recompute FQS -> global evaluation. Return representative metrics as a table.

    labels are fixed (derived from true_food_quality and independent of the weights).
    """
    rows = []
    from dataclasses import replace
    for name, override in ABLATIONS:
        w = replace(base_weights, **override)
        score_places(places, reviews, w, now=now)     # overwrite-recompute FQS (use fqs.py unchanged)
        res = evaluate(places, labels, ks)
        rows.append({
            "config": name,
            "fqs_auc": res["fqs"]["auc"],
            "fqs_recall@10": res["fqs"]["recall@10"],
            "fqs_ndcg@10": res["fqs"]["ndcg@10"],
            "fqs_precision@10": res["fqs"]["precision@10"],
            "weights": w,
        })
    return rows


if __name__ == "__main__":
    # minimal smoke test (synthetic data + synthetic labels)
    from datetime import datetime, timezone

    from eval.proxy_labels import get_proxy_labels
    from ingest.synth import generate
    from nlp.absa import get_analyzer

    places, reviews = generate(n_places=120, seed=42)
    get_analyzer("simple").analyze(reviews)
    score_places(places, reviews, Weights(),
                 now=datetime(2026, 6, 20, tzinfo=timezone.utc))
    labels = get_proxy_labels(places, source="synthetic", top_frac=0.2)

    # metric sanity: AUC in [0,1], ~0.5 if random
    res = evaluate(places, labels, ks=(5, 10, 20))
    assert 0.0 <= res["star"]["auc"] <= 1.0 and 0.0 <= res["fqs"]["auc"] <= 1.0
    # a perfect ranking should give NDCG@k=1 (verified on a degenerate case using FQS itself as the label)
    self_lbl = {p.place_id for p in rank_desc(places, "fqs")[:10]}
    assert abs(ndcg_at_k([p.place_id for p in rank_desc(places, "fqs")],
                         self_lbl, 10) - 1.0) < 1e-9
    print("metrics.py OK")
    print(f"  AUC  star={res['star']['auc']:.3f}  fqs={res['fqs']['auc']:.3f}")
    print(f"  R@10 star={res['star']['recall@10']:.3f}  fqs={res['fqs']['recall@10']:.3f}")
