"""Auto-generate the figures for Blueprint 1 STEP2-4 (Module: analysis).

  Figure 1: star vs FQS scatter plot (with correlation, tourist traps in red)   <- STEP2
  Figure 2: bar chart of aspect mention rates (stratified by tourist/local)      <- STEP3
  Figure 3: before/after re-ranking table (rank delta, with arrows)             <- STEP4

Runs synth -> absa -> fqs -> rerank end-to-end on synthetic data and saves 3 PNGs to reports/.

Usage:
  python -m analysis.divergence_report
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # no GUI needed; file output only
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import pearsonr, spearmanr

from ingest.schema import Place, Review
from ingest.synth import generate
from nlp.absa import get_analyzer
from rerank.reranker import movers, rerank
from scoring.fqs import score_places
from scoring.weights import Weights

ASPECTS = ("food", "service", "ambiance", "price")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

# Blueprint 1 thresholds (literals). Since matches can be few for some data, the count is also shown.
TRAP_STAR_THRESHOLD = 4.5   # STEP2: "star >= 4.5 yet bottom 50% on FQS" = tourist trap
MIN_STAR_STEP3 = 4.0        # STEP3: target reviews of "places with star >= 4.0"


# ---------------------------------------------------------------- Figure 1: scatter plot
def fig1_scatter(places: List[Place], out: str) -> dict:
    scored = [p for p in places if p.fqs is not None]
    star = np.array([p.star_rating for p in scored])
    fqs = np.array([p.fqs for p in scored])
    pear = pearsonr(star, fqs)
    spear = spearmanr(star, fqs)

    fqs_median = float(np.median(fqs))
    is_trap = [(p.star_rating >= TRAP_STAR_THRESHOLD and p.fqs < fqs_median)
               for p in scored]
    n_trap = sum(is_trap)

    fig, ax = plt.subplots(figsize=(7.5, 6))
    normal = [p for p, t in zip(scored, is_trap) if not t]
    traps = [p for p, t in zip(scored, is_trap) if t]
    ax.scatter([p.star_rating for p in normal], [p.fqs for p in normal],
               c="#4C72B0", alpha=0.6, s=40, label="restaurants")
    if traps:
        ax.scatter([p.star_rating for p in traps], [p.fqs for p in traps],
                   c="#C44E52", alpha=0.9, s=70, edgecolors="black",
                   label=f"tourist trap (star>={TRAP_STAR_THRESHOLD} & FQS<median)")
    ax.axhline(fqs_median, color="grey", ls="--", lw=0.8, alpha=0.7)
    ax.set_xlabel("Google star rating")
    ax.set_ylabel("Food Quality Score (FQS)")
    ax.set_title("Star vs Food Quality — divergence\n"
                 f"Pearson r={pear.statistic:.3f}  Spearman rho={spear.statistic:.3f}"
                 f"  (n={len(scored)}, traps={n_trap})")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return {"pearson": pear.statistic, "spearman": spear.statistic,
            "n": len(scored), "n_trap": n_trap}


# ------------------------------------------------ Figure 2: aspect mention rate (stratified)
def _mention_rates(reviews: List[Review]) -> Dict[str, float]:
    if not reviews:
        return {a: 0.0 for a in ASPECTS}
    return {a: sum(getattr(r, f"aspect_{a}") is not None for r in reviews) / len(reviews)
            for a in ASPECTS}


def fig2_aspect_mentions(places: List[Place], reviews: List[Review], out: str) -> dict:
    by_place: Dict[str, List[Review]] = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)

    tourist_rev: List[Review] = []
    local_rev: List[Review] = []
    for p in places:
        if p.star_rating < MIN_STAR_STEP3:
            continue
        bucket = tourist_rev if p.is_tourist_area else local_rev
        bucket.extend(by_place.get(p.place_id, []))

    rt = _mention_rates(tourist_rev)
    rl = _mention_rates(local_rev)

    x = np.arange(len(ASPECTS))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.bar(x - w / 2, [rt[a] for a in ASPECTS], w, label=f"tourist area (n_rev={len(tourist_rev)})",
           color="#C44E52")
    ax.bar(x + w / 2, [rl[a] for a in ASPECTS], w, label=f"local area (n_rev={len(local_rev)})",
           color="#55A868")
    for i, a in enumerate(ASPECTS):
        ax.text(i - w / 2, rt[a] + 0.01, f"{rt[a]:.0%}", ha="center", fontsize=8)
        ax.text(i + w / 2, rl[a] + 0.01, f"{rl[a]:.0%}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(ASPECTS)
    ax.set_ylabel("share of reviews mentioning aspect")
    ax.set_ylim(0, 1)
    ax.set_title(f"Aspect mention rate in star>={MIN_STAR_STEP3} places\n"
                 f"tourist food non-mention = {1 - rt['food']:.0%}  "
                 f"vs local = {1 - rl['food']:.0%}")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return {"tourist_food_mention": rt["food"], "local_food_mention": rl["food"]}


# ------------------------------------------------ Figure 3: before/after re-ranking table
def fig3_rerank_table(places: List[Place], out: str, top: int = 8) -> dict:
    mv = movers(places, top=top)
    rows = []
    for p in mv["traps"]:   # tourist traps (star up, FQS down)
        rows.append(("TRAP", p))
    for p in mv["gems"]:    # hidden gems (star down, FQS up)
        rows.append(("GEM", p))

    col_labels = ["type", "name", "district", "cuisine",
                  "star", "FQS", "star#", "FQS#", "delta"]
    cell_text = []
    cell_colors = []
    for kind, p in rows:
        arrow = "UP" if p.rank_delta > 0 else "DOWN"
        cell_text.append([
            kind, p.name[:18], (p.district or "")[:12], (p.cuisine or "")[:10],
            f"{p.star_rating:.2f}", f"{p.fqs:.2f}" if p.fqs is not None else "-",
            str(p.star_rank), str(p.fqs_rank), f"{arrow} {p.rank_delta:+d}",
        ])
        base = "#F6D6D6" if kind == "TRAP" else "#D6F0DC"
        cell_colors.append([base] * len(col_labels))

    fig, ax = plt.subplots(figsize=(11, 0.5 + 0.42 * (len(rows) + 1)))
    ax.axis("off")
    ax.set_title("Re-ranking: star order vs FQS order (within district x cuisine)\n"
                 "GEM = star-low/FQS-high (discovered)   TRAP = star-high/FQS-low",
                 fontsize=11, pad=12)
    if cell_text:
        tbl = ax.table(cellText=cell_text, colLabels=col_labels,
                       cellColours=cell_colors, loc="center", cellLoc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8.5)
        tbl.scale(1, 1.4)
        for c in range(len(col_labels)):
            tbl[0, c].set_facecolor("#34495E")
            tbl[0, c].set_text_props(color="white", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return {"n_gems": len(mv["gems"]), "n_traps": len(mv["traps"])}


# ---------------------------------------------------------------- orchestration
def run_pipeline(n_places: int = 120, seed: int = 42,
                 weights: Weights | None = None) -> dict:
    """Run synth -> absa -> fqs -> rerank -> 3 figures end-to-end and save to reports/."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    weights = weights or Weights()
    now = datetime(2026, 6, 20, tzinfo=timezone.utc)  # fixed for deterministic figures

    places, reviews = generate(n_places=n_places, seed=seed)
    reviews = get_analyzer("simple").analyze(reviews)
    score_places(places, reviews, weights, now=now)
    rerank(places, scope="district_cuisine")

    f1 = os.path.join(REPORTS_DIR, "fig1_star_vs_fqs_scatter.png")
    f2 = os.path.join(REPORTS_DIR, "fig2_aspect_mention_rate.png")
    f3 = os.path.join(REPORTS_DIR, "fig3_rerank_before_after.png")
    s1 = fig1_scatter(places, f1)
    s2 = fig2_aspect_mentions(places, reviews, f2)
    s3 = fig3_rerank_table(places, f3)
    return {"figures": [f1, f2, f3], "fig1": s1, "fig2": s2, "fig3": s3,
            "n_places": len(places), "n_reviews": len(reviews)}


if __name__ == "__main__":
    res = run_pipeline()
    print("divergence_report.py OK — wrote 3 figures to reports/")
    for f in res["figures"]:
        exists = os.path.exists(f)
        size = os.path.getsize(f) if exists else 0
        print(f"  {'[ok]' if exists else '[MISSING]'} {os.path.relpath(f)}  ({size} bytes)")
    print(f"  STEP2 Pearson r={res['fig1']['pearson']:.3f}  "
          f"Spearman={res['fig1']['spearman']:.3f}  "
          f"traps(star>={TRAP_STAR_THRESHOLD})={res['fig1']['n_trap']}")
    print(f"  STEP3 food mention: tourist={res['fig2']['tourist_food_mention']:.0%} "
          f"local={res['fig2']['local_food_mention']:.0%}")
    print(f"  STEP4 gems={res['fig3']['n_gems']} traps={res['fig3']['n_traps']}")
