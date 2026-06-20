"""Test whether the "star vs FQS divergence" really exists on real Barcelona data (Blueprint 1 STEP2-4 applied to real data).

Unlike the synthetic case, this is not circular reasoning. If divergence appears it is
genuine evidence for the proposal; if not, the premise must be revisited — either way we
report honestly.

Steps:
  1. Restore data/raw/bcn.jsonl into Place/Review
  2. Apply aspect_* via the LLM-based ABSA (Gemini) on real text (mixed Spanish/Catalan/English)
  3. Compute FQS -> rerank
  4. Scatter (star vs FQS) + Pearson r / star histogram / tourist-vs-local stratified aspect mention rate /
     real examples of rank_delta (tourist traps and hidden gems)
  5. Rough ABSA cost estimate

Run:  python -m analysis.real_divergence_report
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import pearsonr, spearmanr

from analysis.divergence_report import fig1_scatter   # reuse the existing scatter plot (unchanged)
from ingest.places_grid import load_bcn_jsonl
from nlp.absa import ASPECTS, get_analyzer
from rerank.reranker import movers, rerank
from scoring.fqs import score_places
from scoring.weights import Weights

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
_ROOT = os.path.dirname(os.path.dirname(__file__))
BCN_ABSA = os.path.join(_ROOT, "data", "processed", "bcn_absa.jsonl")  # incremental save target for ABSA results
CHUNK = 120                         # save per chunk (interruption-resilient; ~15 batches)
NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)
PRICE_IN, PRICE_OUT = 0.10, 0.40   # USD / 1M tokens (flash-lite estimate; to be verified)


def _akey(r) -> str:
    return f"{r.place_id}|{r.review_id}"


def load_absa_cache(path: str = BCN_ABSA) -> Dict[str, dict]:
    """Read saved ABSA results into a cache (key -> aspects) to avoid re-charging."""
    cache: Dict[str, dict] = {}
    if not os.path.exists(path):
        return cache
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                cache[rec["key"]] = {a: rec.get(a) for a in ASPECTS}
            except (json.JSONDecodeError, KeyError):
                continue
    return cache


def append_absa(path: str, reviews_chunk) -> None:
    """Append ABSA-annotated reviews one per line (the unit of resume)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in reviews_chunk:
            rec = {"key": _akey(r),
                   **{a: getattr(r, f"aspect_{a}") for a in ASPECTS}}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _rep_food_review(reviews) -> str:
    food = [r for r in reviews if r.aspect_food is not None]
    if not food:
        return ""
    r = max(food, key=lambda x: len(x.text or ""))
    t = (r.text or "").replace("\n", " ")
    return t[:160] + ("…" if len(t) > 160 else "")


def star_histogram(places, out: str) -> dict:
    stars = np.array([p.star_rating for p in places if p.star_rating])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(stars, bins=np.arange(2.5, 5.05, 0.1), color="#4C72B0", edgecolor="white")
    ax.axvspan(3.0, 4.0, color="#DD8452", alpha=0.15, label="3.x band (distribution tail)")
    ax.set_xlabel("Google star rating"); ax.set_ylabel("# places")
    n3 = int(((stars >= 3.0) & (stars < 4.0)).sum())
    ax.set_title(f"Star distribution of fetched places (n={len(stars)})  "
                 f"| 3.0-3.9 band: {n3} places")
    ax.legend()
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)
    return {"n": len(stars), "n_3x": n3, "min": float(stars.min()), "max": float(stars.max())}


def stratified_aspect(places, reviews, out: str) -> dict:
    """Aspect mention rate for tourist (True) vs local (False). Mixed (None=Eixample) is excluded."""
    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)
    groups = {"tourist": [], "local": []}
    for p in places:
        if p.is_tourist_area is True:
            groups["tourist"].extend(by_place.get(p.place_id, []))
        elif p.is_tourist_area is False:
            groups["local"].extend(by_place.get(p.place_id, []))

    def rates(revs):
        if not revs:
            return {a: float("nan") for a in ASPECTS}
        return {a: sum(getattr(r, f"aspect_{a}") is not None for r in revs) / len(revs)
                for a in ASPECTS}

    rt, rl = rates(groups["tourist"]), rates(groups["local"])
    x = np.arange(len(ASPECTS)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.bar(x - w / 2, [rt[a] for a in ASPECTS], w, color="#C44E52",
           label=f"tourist districts (n_rev={len(groups['tourist'])})")
    ax.bar(x + w / 2, [rl[a] for a in ASPECTS], w, color="#55A868",
           label=f"local districts (n_rev={len(groups['local'])})")
    for i, a in enumerate(ASPECTS):
        if rt[a] == rt[a]:
            ax.text(i - w / 2, rt[a] + 0.01, f"{rt[a]:.0%}", ha="center", fontsize=8)
        if rl[a] == rl[a]:
            ax.text(i + w / 2, rl[a] + 0.01, f"{rl[a]:.0%}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(ASPECTS); ax.set_ylim(0, 1)
    ax.set_ylabel("share of reviews mentioning aspect (REAL data)")
    ax.set_title("Aspect mention rate: tourist vs local districts (Barcelona, real)")
    ax.legend(); ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)
    return {"tourist": rt, "local": rl,
            "n_tourist_rev": len(groups["tourist"]), "n_local_rev": len(groups["local"])}


def main() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    places, reviews = load_bcn_jsonl()
    print(f"loaded REAL data: {len(places)} places, {len(reviews)} reviews", flush=True)

    # 2) LLM-based ABSA on real text (save per chunk = resume on interruption without re-charging)
    cache = load_absa_cache(BCN_ABSA)
    remaining = []
    applied = 0
    for r in reviews:
        c = cache.get(_akey(r))
        if c is not None:
            for a in ASPECTS:
                setattr(r, f"aspect_{a}", c[a])
            applied += 1
        else:
            remaining.append(r)
    print(f"ABSA resume: {applied} already cached, {len(remaining)} newly processed "
          f"(saved to {os.path.relpath(BCN_ABSA)})", flush=True)

    analyzer = get_analyzer("gemini")
    usage = {"prompt": 0, "output": 0, "total": 0}
    n_failed = 0
    for i in range(0, len(remaining), CHUNK):
        chunk = remaining[i:i + CHUNK]
        analyzer.analyze(chunk)               # with timeout/retry
        append_absa(BCN_ABSA, chunk)          # save immediately (interruption-resilient)
        u = getattr(analyzer, "total_usage", {}) or {}
        for k in usage:
            usage[k] += u.get(k, 0)
        n_failed += getattr(analyzer, "n_failed", 0)
        print(f"  ABSA progress: {min(i + CHUNK, len(remaining))}/{len(remaining)} processed and saved",
              flush=True)

    n_food = sum(r.aspect_food is not None for r in reviews)
    print(f"ABSA done: food mentions {n_food}/{len(reviews)} reviews, skipped(failed)={n_failed}",
          flush=True)

    # 3) FQS + rerank
    score_places(places, reviews, Weights(), now=NOW)
    rerank(places, scope="district_cuisine")

    # 4a) scatter + Pearson
    scored = [p for p in places if p.fqs is not None]
    star = np.array([p.star_rating for p in scored])
    fqs = np.array([p.fqs for p in scored])
    pear = pearsonr(star, fqs); spear = spearmanr(star, fqs)
    f_scatter = os.path.join(REPORTS_DIR, "real_fig1_star_vs_fqs.png")
    fig1_scatter(places, f_scatter)   # reuse the existing drawing
    f_hist = os.path.join(REPORTS_DIR, "real_star_histogram.png")
    hist = star_histogram(places, f_hist)
    f_aspect = os.path.join(REPORTS_DIR, "real_fig2_aspect_mention.png")
    strat = stratified_aspect(places, reviews, f_aspect)

    # 4b) rank_delta examples
    mv = movers(places, top=5)
    by_place = defaultdict(list)
    for r in reviews:
        by_place[r.place_id].append(r)

    print("\n================ Real-data divergence report ================")
    print(f"[STEP2] star vs FQS  Pearson r={pear.statistic:+.3f}  "
          f"Spearman={spear.statistic:+.3f}  (n={len(scored)})")
    print(f"        On synthetic data r=0.226. If real-data r is at or below this, the divergence is real.")
    print(f"[star dist] n={hist['n']}  range=[{hist['min']:.1f},{hist['max']:.1f}]  "
          f"3.0-3.9 band={hist['n_3x']} places (tail of distribution)")
    print(f"[STEP3] food mention rate  tourist={strat['tourist']['food']:.0%} vs local={strat['local']['food']:.0%}"
          f"  | ambiance tourist={strat['tourist']['ambiance']:.0%} vs local={strat['local']['ambiance']:.0%}"
          f"  | price tourist={strat['tourist']['price']:.0%} vs local={strat['local']['price']:.0%}")

    print("\n[STEP4] Tourist traps (high star, low FQS):")
    for p in mv["traps"][:4]:
        print(f"  🔻 {p.name[:34]:34} ⭐{p.star_rating} 🍽FQS{p.fqs:+.2f} "
              f"(star#{p.star_rank}->fqs#{p.fqs_rank}, Δ{p.rank_delta}) [{p.cuisine}/{p.district}]")
        print(f"      representative food: {_rep_food_review(by_place[p.place_id])!r}")
    print("\n[STEP4] Hidden gems (low star, high FQS):")
    for p in mv["gems"][:4]:
        print(f"  🔺 {p.name[:34]:34} ⭐{p.star_rating} 🍽FQS{p.fqs:+.2f} "
              f"(star#{p.star_rank}->fqs#{p.fqs_rank}, Δ{p.rank_delta}) [{p.cuisine}/{p.district}]")
        print(f"      representative food: {_rep_food_review(by_place[p.place_id])!r}")

    # 5) ABSA cost
    print("\n[ABSA cost]")
    if usage.get("total"):
        per = usage["total"] / len(reviews)
        cost = (usage["prompt"] * PRICE_IN + usage["output"] * PRICE_OUT) / 1e6
        print(f"  measured tokens: prompt={usage['prompt']} out={usage['output']} "
              f"total={usage['total']}  ({per:.0f}/review)")
        print(f"  estimated cost: ${cost:.4f} ({len(reviews)} reviews, flash-lite rate "
              f"in${PRICE_IN}/out${PRICE_OUT} per 1M; to be verified)")
    else:
        print("  usage unavailable.")

    print("\nfigures:", os.path.relpath(f_scatter), "/", os.path.relpath(f_hist),
          "/", os.path.relpath(f_aspect))
    # An honest verdict cue at the end
    verdict = ("divergence present (supports the proposal's premise)" if pear.statistic < 0.5
               else "divergence weak (premise needs revisiting)")
    print(f"\n>>> Provisional verdict: Pearson r={pear.statistic:+.3f} -> {verdict} (real data = not circular reasoning)")


if __name__ == "__main__":
    main()
