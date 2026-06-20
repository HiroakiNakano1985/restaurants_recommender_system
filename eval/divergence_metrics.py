"""Real-data in-house metrics: quantify "stars saturate at 4.5 and lose discriminative power /
FQS restores discriminative power", without external labels, using only the existing 652-place
real Barcelona data (an alternative strategy to Blueprint 1 §3).

Maps to the three perspectives of the assignment:
  A. Technical     ... quantify star saturation / FQS discrimination / star-tie resolution rate (discrimination power)
  B. User-centered ... choice resolution / explainability
  C. Business      ... hidden gems / absolute traps / rank churn

WARNING: honesty disclosure (also printed at the end of the report):
  - These show that "FQS makes a *different* discrimination than the star", not a proof that
    "FQS is truly more correct". Final validation requires external labels (expert guides, etc.) = future work.
  - External validation with Michelin stars was attempted, but with 4 matches out of 652 places and a
    mismatch with the proposed target (casual good-food places), it was abandoned.
  - Data limits: at most 5 reviews per place / selection bias of Google's relevance-top reviews.

The scoring (fqs/rerank) logic is not changed, only called. Separate from the synthetic evaluation (eval/run_eval.py).
Run:  python -m eval.divergence_metrics
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import kendalltau, spearmanr

from analysis.real_divergence_report import _akey, load_absa_cache
from ingest.places_grid import load_bcn_jsonl
from nlp.absa import ASPECTS
from rerank.reranker import group_by
from scoring.fqs import score_places
from scoring.weights import Weights

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)

# thresholds (all parameters; documented in the report)
TIE_EPS = (0.1, 0.2, 0.5)     # multiple |ΔFQS| thresholds for "FQS made a meaningful difference"
GEM_STAR_MAX = 4.4            # hidden gem: star at or below this
TRAP_STAR_MIN = 4.6          # trap: star at or above this (FQS judged absolutely by the 25/75 percentile)


# ---------------------------------------------------------------- data preparation
def load_scored_real(weights: Optional[Weights] = None):
    """Read bcn.jsonl + cached ABSA, compute FQS + rerank, and return (only calls existing logic)."""
    places, reviews = load_bcn_jsonl()
    cache = load_absa_cache()
    applied = 0
    for r in reviews:
        c = cache.get(_akey(r))
        if c is not None:
            for a in ASPECTS:
                setattr(r, f"aspect_{a}", c[a])
            applied += 1
    score_places(places, reviews, weights or Weights(), now=NOW)
    from rerank.reranker import rerank
    rerank(places, scope="district_cuisine")
    return places, reviews, applied


def _entropy_bits(values: np.ndarray, binwidth: float) -> Tuple[float, float, int]:
    """Shannon entropy (bits), perplexity (= effective number of levels = 2^H), and number of bins used."""
    b = np.round(values / binwidth).astype(int)
    _, counts = np.unique(b, return_counts=True)
    p = counts / counts.sum()
    H = float(-(p * np.log2(p)).sum())
    return H, float(2 ** H), len(counts)


# ============================================================ A. Technical
def technical_metrics(places) -> dict:
    scored = [p for p in places if p.fqs is not None]
    star = np.array([p.star_rating for p in scored], dtype=float)
    fqs = np.array([p.fqs for p in scored], dtype=float)

    # 1) star saturation
    star_H, star_eff, star_bins = _entropy_bits(star, 0.1)
    frac_40 = float((star >= 4.0).mean())
    frac_45 = float((star >= 4.5).mean())

    # 2) FQS discrimination (normalize to a common [0,1] scale and compare variance/range)
    star_n = (star - 1) / 4.0
    fqs_n = (np.clip(fqs, -1, 1) + 1) / 2.0
    spread = {
        "star": {"std_raw": float(star.std()), "range_raw": (float(star.min()), float(star.max())),
                 "std_norm01": float(star_n.std()), "range_norm01": float(star_n.max() - star_n.min())},
        "fqs": {"std_raw": float(fqs.std()), "range_raw": (float(fqs.min()), float(fqs.max())),
                "std_norm01": float(fqs_n.std()), "range_norm01": float(fqs_n.max() - fqs_n.min())},
    }

    # 3) star-tie resolution rate: equal star = indistinguishable pairs. Fraction of those where FQS makes a |Δ|>=eps difference.
    by_star: Dict[float, List[float]] = defaultdict(list)
    for p in scored:
        by_star[p.star_rating].append(p.fqs)
    total_pairs = len(scored) * (len(scored) - 1) // 2
    tied_pairs = 0
    tied_absdiffs: List[float] = []
    for vals in by_star.values():
        k = len(vals)
        if k < 2:
            continue
        tied_pairs += k * (k - 1) // 2
        for a, b in combinations(vals, 2):
            tied_absdiffs.append(abs(a - b))
    tied_absdiffs_arr = np.array(tied_absdiffs) if tied_absdiffs else np.array([0.0])
    sep = {eps: float((tied_absdiffs_arr >= eps).mean()) for eps in TIE_EPS}

    return {
        "n": len(scored),
        "saturation": {"star_entropy_bits": star_H, "star_effective_levels": star_eff,
                       "star_used_bins": star_bins, "frac>=4.0": frac_40, "frac>=4.5": frac_45,
                       "star_std": float(star.std())},
        "spread": spread,
        "tie_resolution": {
            "tied_pairs_frac": tied_pairs / total_pairs if total_pairs else float("nan"),
            "tied_pairs": tied_pairs, "total_pairs": total_pairs,
            "fqs_separates_frac": sep,        # eps -> fraction
            "median_absdiff_among_tied": float(np.median(tied_absdiffs_arr)),
        },
    }


# ============================================================ B. User-centered
def user_metrics(places, reviews) -> dict:
    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)

    # 4) choice resolution: star range vs FQS range within the same district x cuisine (common [0,1])
    groups = group_by(places, "district_cuisine")
    star_ranges, fqs_ranges = [], []
    for g in groups.values():
        gg = [p for p in g if p.fqs is not None]
        if len(gg) < 3:
            continue
        s = np.array([p.star_rating for p in gg]); f = np.array([p.fqs for p in gg])
        star_ranges.append((s.max() - s.min()) / 4.0)
        fqs_ranges.append((np.clip(f, -1, 1).max() - np.clip(f, -1, 1).min()) / 2.0)

    # representative example: Gràcia tapas (all places + a spotlight on "the FQS spread among same-star places")
    example = None
    for g in groups.values():
        gg = [p for p in g if p.fqs is not None]
        if gg and gg[0].district == "Gràcia" and gg[0].cuisine == "tapas":
            from collections import Counter
            members = sorted([(p.name, p.star_rating, round(p.fqs, 2)) for p in gg],
                             key=lambda x: -x[2])
            modal_star = Counter(p.star_rating for p in gg).most_common(1)[0][0]
            same = [p.fqs for p in gg if p.star_rating == modal_star]
            example = {"members": members, "n": len(gg),
                       "spotlight": {"star": modal_star, "n": len(same),
                                     "fqs_min": round(min(same), 2),
                                     "fqs_max": round(max(same), 2)}}
            break

    # 5) explainability: fraction of places where FQS can carry a "food-mention rate + representative review"
    explainable = 0
    for p in places:
        if p.fqs is None:
            continue
        if any(r.aspect_food is not None for r in by_place.get(p.place_id, [])):
            explainable += 1
    n_scored = sum(1 for p in places if p.fqs is not None)

    return {
        "choice_resolution": {
            "groups_used": len(star_ranges),
            "mean_star_range_norm01": float(np.mean(star_ranges)) if star_ranges else float("nan"),
            "mean_fqs_range_norm01": float(np.mean(fqs_ranges)) if fqs_ranges else float("nan"),
            "example_gracia_tapas": example,
        },
        "explainability": {
            "explainable_frac": explainable / n_scored if n_scored else float("nan"),
            "explainable": explainable, "n_scored": n_scored,
        },
    }


# ============================================================ C. Business
def business_metrics(places) -> dict:
    scored = [p for p in places if p.fqs is not None]
    fqs = np.array([p.fqs for p in scored])
    q25, q75 = float(np.percentile(fqs, 25)), float(np.percentile(fqs, 75))

    # 6) hidden gem: star at or below median (<=4.4) and FQS in the top (>=75th pct)
    gems = [p for p in scored if p.star_rating <= GEM_STAR_MAX and p.fqs >= q75]
    gems.sort(key=lambda p: -p.fqs)
    # 7) absolute trap: high star (>=4.6) and low FQS (<=25th pct)  <- distinct from the relative trap within a small group
    traps = [p for p in scored if p.star_rating >= TRAP_STAR_MIN and p.fqs <= q25]
    traps.sort(key=lambda p: p.fqs)

    # 8) rank churn: correlation between star rank and FQS rank (lower = more distinct information)
    star = np.array([p.star_rating for p in scored]); fq = np.array([p.fqs for p in scored])
    tau = float(kendalltau(star, fq).statistic)
    rho = float(spearmanr(star, fq).statistic)
    star_rank = (-star).argsort().argsort() + 1
    fqs_rank = (-fq).argsort().argsort() + 1
    moves = np.abs(star_rank - fqs_rank)
    n = len(scored)

    return {
        "fqs_q25": q25, "fqs_q75": q75,
        "hidden_gems": {"count": len(gems),
                        "examples": [(p.name, p.star_rating, round(p.fqs, 2), p.district, p.cuisine)
                                     for p in gems[:6]]},
        "absolute_traps": {"count": len(traps),
                           "examples": [(p.name, p.star_rating, round(p.fqs, 2), p.district, p.cuisine)
                                        for p in traps[:6]]},
        "rank_churn": {"kendall_tau": tau, "spearman_rho": rho,
                       "frac_move>=10pct": float((moves >= 0.10 * n).mean()),
                       "frac_move>=25pct": float((moves >= 0.25 * n).mean()),
                       "star_rank": star_rank, "fqs_rank": fqs_rank},
    }


# ============================================================ figures
def make_figures(places, tech, biz) -> List[str]:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    scored = [p for p in places if p.fqs is not None]
    star = np.array([p.star_rating for p in scored])
    fqs = np.array([p.fqs for p in scored])
    out = []

    # fig1: histogram of star vs FQS (saturation vs spread)
    f1 = os.path.join(REPORTS_DIR, "divmetric_fig1_saturation.png")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].hist(star, bins=np.arange(2.0, 5.05, 0.1), color="#4C72B0", edgecolor="white")
    ax[0].set_title(f"Google star (saturated)\nstd={star.std():.3f}, effective levels="
                    f"{tech['saturation']['star_effective_levels']:.1f}")
    ax[0].set_xlabel("star")
    ax[1].hist(fqs, bins=20, color="#55A868", edgecolor="white")
    ax[1].set_title(f"FQS (spread)\nstd={fqs.std():.3f}, range "
                    f"[{fqs.min():.2f},{fqs.max():.2f}]")
    ax[1].set_xlabel("FQS")
    fig.suptitle("Saturation vs discrimination (real Barcelona, n=%d)" % len(scored))
    fig.tight_layout(); fig.savefig(f1, dpi=130); plt.close(fig); out.append(f1)

    # fig2: spread comparison on normalized [0,1] (violin)
    f2 = os.path.join(REPORTS_DIR, "divmetric_fig2_spread_norm.png")
    star_n = (star - 1) / 4.0; fqs_n = (np.clip(fqs, -1, 1) + 1) / 2.0
    fig, ax = plt.subplots(figsize=(6.5, 5))
    parts = ax.violinplot([star_n, fqs_n], showmeans=True, showextrema=True)
    ax.set_xticks([1, 2]); ax.set_xticklabels(["Google star", "FQS"])
    ax.set_ylabel("normalized to [0,1] (same scale)")
    ax.set_title("Same [0,1] scale: star compressed vs FQS spread\n"
                 f"std star={star_n.std():.3f}  vs  FQS={fqs_n.std():.3f}")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(f2, dpi=130); plt.close(fig); out.append(f2)

    # fig3: tie resolution -- |ΔFQS| distribution for star-tied pairs
    f3 = os.path.join(REPORTS_DIR, "divmetric_fig3_tie_resolution.png")
    by_star = defaultdict(list)
    for p in scored:
        by_star[p.star_rating].append(p.fqs)
    diffs = [abs(a - b) for vals in by_star.values() if len(vals) > 1
             for a, b in combinations(vals, 2)]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.hist(diffs, bins=30, color="#8172B3", edgecolor="white")
    ymax = ax.get_ylim()[1]
    for i, eps in enumerate(TIE_EPS):
        frac = tech["tie_resolution"]["fqs_separates_frac"][eps]
        ax.axvline(eps, ls="--", color="#C44E52")
        ax.text(eps + 0.03, ymax * (0.92 - i * 0.09), f"|Δ|>={eps}: {frac:.0%}",
                color="#C44E52", fontsize=8.5)
    ax.set_xlabel("|ΔFQS| between star-tied store pairs")
    ax.set_ylabel("# pairs")
    ax.set_title("Star-tied pairs: how much FQS separates them\n"
                 f"{tech['tie_resolution']['tied_pairs_frac']:.0%} of all pairs share the SAME star")
    fig.tight_layout(); fig.savefig(f3, dpi=130); plt.close(fig); out.append(f3)

    # fig4: rank churn scatter plot
    f4 = os.path.join(REPORTS_DIR, "divmetric_fig4_rank_churn.png")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(biz["rank_churn"]["star_rank"], biz["rank_churn"]["fqs_rank"],
               c="#4C72B0", alpha=0.5, s=18)
    lim = len(scored)
    ax.plot([1, lim], [1, lim], "grey", ls="--", lw=0.8)
    ax.set_xlabel("rank by Google star"); ax.set_ylabel("rank by FQS")
    ax.set_title(f"Rank churn: star-rank vs FQS-rank\n"
                 f"Kendall tau={biz['rank_churn']['kendall_tau']:.3f}  "
                 f"Spearman={biz['rank_churn']['spearman_rho']:.3f} (low=new info)")
    fig.tight_layout(); fig.savefig(f4, dpi=130); plt.close(fig); out.append(f4)
    return out


HONESTY = (
    "[Honesty disclosure]\n"
    "  1) What these metrics show is that 'FQS makes a *different* discrimination than the star', not\n"
    "     that 'FQS is truly more correct'. The latter needs external labels (expert guides, etc.) for\n"
    "     final validation (future work).\n"
    "  2) External labels (Michelin stars) were attempted, but with 4 matches out of 652 places and a\n"
    "     mismatch with the proposed target (casual good-food places), this was abandoned.\n"
    "  3) Data limits: at most 5 reviews per place (Places constraint) / selection bias of Google's\n"
    "     relevance-top reviews. The restricted star range (almost every place ~4.5) also affects the metrics.\n"
    "  4) FQS ceiling: because Google's top reviews skew toward praise, the top places in each group\n"
    "     saturate FQS near +1 and discrimination dulls. FQS is effective at 'sorting the tied middle-to-lower\n"
    "     places'. Also, cuisine normalization (mean centering) rarely makes FQS slightly exceed ±1\n"
    "     (left unclipped and shown raw for transparency)."
)


def main() -> None:
    places, reviews, applied = load_scored_real()
    n_scored = sum(1 for p in places if p.fqs is not None)
    print(f"REAL data: {len(places)} places ({n_scored} with FQS), {len(reviews)} reviews, "
          f"absa applied={applied}")

    tech = technical_metrics(places)
    usr = user_metrics(places, reviews)
    biz = business_metrics(places)

    print("\n================= A. TECHNICAL =================")
    s = tech["saturation"]
    print(f"[star saturation] std={s['star_std']:.3f}  entropy={s['star_entropy_bits']:.2f}bit  "
          f"effective levels={s['star_effective_levels']:.1f} (the 5-point scale is effectively only this many)  "
          f"bins used={s['star_used_bins']}")
    print(f"           fraction star>=4.0={s['frac>=4.0']:.0%}  star>=4.5={s['frac>=4.5']:.0%}")
    sp = tech["spread"]
    print(f"[spread comparison / common [0,1]] star: std={sp['star']['std_norm01']:.3f} "
          f"range={sp['star']['range_norm01']:.2f}  |  "
          f"FQS: std={sp['fqs']['std_norm01']:.3f} range={sp['fqs']['range_norm01']:.2f}")
    print(f"           (raw range: star {sp['star']['range_raw']}  FQS {sp['fqs']['range_raw']})")
    tr = tech["tie_resolution"]
    print(f"[star-tie resolution] {tr['tied_pairs_frac']:.0%} of all pairs are indistinguishable by equal star "
          f"({tr['tied_pairs']:,}/{tr['total_pairs']:,} pairs)")
    print(f"           fraction of those where FQS separates: " +
          "  ".join(f"|Δ|>={e}->{tr['fqs_separates_frac'][e]:.0%}" for e in TIE_EPS) +
          f"   (median |ΔFQS| among tied={tr['median_absdiff_among_tied']:.2f})")

    print("\n================= B. USER-CENTERED =================")
    cr = usr["choice_resolution"]
    print(f"[choice resolution] mean range within same district x cuisine (common [0,1]): "
          f"star={cr['mean_star_range_norm01']:.3f} vs FQS={cr['mean_fqs_range_norm01']:.3f} "
          f"({cr['groups_used']} groups) -> FQS orders within groups much more strongly")
    eg = cr["example_gracia_tapas"]
    if eg:
        sp = eg["spotlight"]
        print(f"   e.g.) Gràcia x tapas ({eg['n']} places): {sp['n']} places share the same star {sp['star']}, "
              f"and their FQS ranges {sp['fqs_min']:+.2f} to {sp['fqs_max']:+.2f} "
              f"(same star but FQS spreads widely = you can choose)")
        print("      top (food is the real deal):")
        for name, st, fq in eg["members"][:3]:
            print(f"         {name[:28]:28} star {st}  FQS {fq:+.2f}")
        print("      bottom (low food rating even in the same area and cuisine):")
        for name, st, fq in eg["members"][-3:]:
            print(f"         {name[:28]:28} star {st}  FQS {fq:+.2f}")
    ex = usr["explainability"]
    print(f"[explainability] places where FQS can carry a 'food-mention rate + representative review' = "
          f"{ex['explainable']}/{ex['n_scored']} = {ex['explainable_frac']:.0%}")

    print("\n================= C. BUSINESS =================")
    g = biz["hidden_gems"]; t = biz["absolute_traps"]
    print(f"[hidden gems] star<= {GEM_STAR_MAX} and FQS>=75th pct({biz['fqs_q75']:+.2f}): {g['count']} places")
    for name, st, fq, d, c in g["examples"]:
        print(f"   GEM {name[:28]:28} star {st} FQS {fq:+.2f} [{c}/{d}]")
    print(f"[absolute traps] star>= {TRAP_STAR_MIN} and FQS<=25th pct({biz['fqs_q25']:+.2f}): {t['count']} places"
          f" (an 'absolute' definition distinct from the relative trap within a small group)")
    for name, st, fq, d, c in t["examples"]:
        print(f"   TRAP {name[:28]:28} star {st} FQS {fq:+.2f} [{c}/{d}]")
    rc = biz["rank_churn"]
    print(f"[rank churn] Kendall tau={rc['kendall_tau']:.3f}  Spearman={rc['spearman_rho']:.3f}"
          f" (low = not a rehash of the star = distinct information)  "
          f"places moving >=10% of the total={rc['frac_move>=10pct']:.0%} / >=25%={rc['frac_move>=25pct']:.0%}")

    figs = make_figures(places, tech, biz)
    print("\nfigures:", ", ".join(os.path.relpath(f) for f in figs))
    print("\n" + HONESTY)


if __name__ == "__main__":
    main()
