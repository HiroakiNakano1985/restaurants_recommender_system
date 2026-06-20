"""Verification script for the LLM-based ABSA (Gemini) (Design 2 §5).

Run:
  # production (requires GEMINI_API_KEY in .env)
  python -m nlp.verify_absa_llm --backend gemini --n 14
  # offline, harness-only check (no API key, does not call Gemini)
  python -m nlp.verify_absa_llm --backend mock --n 14

Contents:
  1) Run ABSA on part of the synthetic data + multilingual samples (English/Spanish/Catalan) and print the output JSON
  2) Consistency between the dummy version's ground truth (synthetic) and the LLM output (sign-agreement rate, Pearson correlation)
  3) Cost estimate (actual token usage → estimated cost for processing 4000 reviews)
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from ingest.schema import Review
from ingest.synth import generate
from nlp.absa import ASPECTS, LlmAbsa, get_analyzer

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# --- Cost rates (USD / 1M tokens). To be confirmed: update with the official Gemini pricing as of 2026-06 ---
# Approximate range for gemini-2.5-flash-lite. Verify actual costs against the Google AI Studio / Vertex pricing tables.
PRICE_IN_PER_1M = 0.10   # input
PRICE_OUT_PER_1M = 0.40  # output
PRICE_NOTE = "(approximate rate; to be confirmed against official Gemini pricing)"

# Processing scale assumed for the real Barcelona dataset
BCN_PLACES = 800
REVIEWS_PER_PLACE = 5
BCN_TOTAL = BCN_PLACES * REVIEWS_PER_PLACE  # 4000

# Multilingual samples (expected signs: +1 / -1 / 0 = not mentioned)
MULTILINGUAL = [
    {
        "lang": "en",
        "text": "The paella was absolutely delicious, the best I've had in years. "
                "Service was a bit slow though.",
        "expect": {"food": +1, "service": -1, "ambiance": 0, "price": 0},
    },
    {
        "lang": "es",
        "text": "La comida estaba buenísima y muy fresca, pero el sitio es muy "
                "ruidoso y bastante caro para lo que es.",
        "expect": {"food": +1, "service": 0, "ambiance": -1, "price": -1},
    },
    {
        "lang": "ca",
        "text": "El menjar deliciós i el personal molt amable. L'únic dolent és "
                "que és una mica car.",
        "expect": {"food": +1, "service": +1, "ambiance": 0, "price": -1},
    },
]


# ---------------------------------------------------------------- offline mock
class MockAbsa:
    """Offline stand-in for verifying the harness without an API key.

    Does not call Gemini; just rule-based picks up words from synth's template
    vocabulary + the multilingual samples and assigns a sign. Same interface as
    LlmAbsa. total_usage is empty (= no cost).
    """

    POS = ("delicious", "outstanding", "best", "incredible", "attentive", "great",
           "lovely", "beautiful", "value", "fair", "buenísima", "fresca", "deliciós",
           "amable")
    NEG = ("bland", "forgettable", "overcooked", "tasteless", "frozen", "microwaved",
           "disappointing", "slow", "rude", "ignored", "cramped", "noisy", "trap",
           "overpriced", "expensive", "ruidoso", "caro", "car", "dolent")
    KW = {
        "food": ("food", "dish", "paella", "flavor", "comida", "menjar", "fresca"),
        "service": ("service", "staff", "waiter", "personal", "amable"),
        "ambiance": ("terrace", "atmosphere", "vibe", "view", "decor", "noisy",
                     "cramped", "sitio", "ruidoso"),
        "price": ("value", "price", "money", "caro", "car", "expensive", "overpriced"),
    }

    def analyze(self, reviews: List[Review]) -> List[Review]:
        self.total_usage = {"prompt": 0, "output": 0, "total": 0}
        self.n_failed = 0
        for r in reviews:
            low = r.text.lower()
            for asp in ASPECTS:
                if any(k in low for k in self.KW[asp]):
                    pos = any(w in low for w in self.POS)
                    neg = any(w in low for w in self.NEG)
                    val = 0.6 if (pos and not neg) else -0.6 if (neg and not pos) else 0.1
                    setattr(r, f"aspect_{asp}", val)
                else:
                    setattr(r, f"aspect_{asp}", None)
        return reviews


def _make_analyzer(backend: str):
    if backend == "mock":
        return MockAbsa()
    return get_analyzer(backend)  # "gemini" / "simple"


# ---------------------------------------------------------------- build inputs
def build_reviews(n: int, seed: int) -> Tuple[List[Review], Dict[str, Dict[str, Optional[float]]]]:
    """n synthetic + 3 multilingual. Stash the synthetic ground truth and clear aspects to None."""
    _, syn = generate(n_places=40, seed=seed)
    syn = syn[:n]
    truth: Dict[str, Dict[str, Optional[float]]] = {}
    for r in syn:
        truth[r.review_id] = {a: getattr(r, f"aspect_{a}") for a in ASPECTS}
        for a in ASPECTS:           # clear so it's inferred from the text alone
            setattr(r, f"aspect_{a}", None)

    ml: List[Review] = []
    for i, s in enumerate(MULTILINGUAL):
        ml.append(Review(place_id="ml", review_id=f"ml_{s['lang']}_{i}",
                         rating=4, text=s["text"], lang=s["lang"]))
    return syn + ml, truth


# ---------------------------------------------------------------- reporting
def _sign(x: Optional[float]) -> int:
    if x is None:
        return 0
    return 1 if x > 0.05 else -1 if x < -0.05 else 0


def show_outputs(reviews: List[Review]) -> None:
    print("\n===== 1) ABSA output (JSON) =====")
    for r in reviews:
        out = {a: getattr(r, f"aspect_{a}") for a in ASPECTS}
        print(f"[{r.review_id}] ({r.lang or '?'}) {r.text[:70]!r}")
        print("   -> " + json.dumps(out, ensure_ascii=False))


def check_multilingual(reviews: List[Review]) -> None:
    print("\n===== (multilingual) expected sign vs predicted sign =====")
    ml = {r.review_id: r for r in reviews if r.place_id == "ml"}
    for i, s in enumerate(MULTILINGUAL):
        r = ml[f"ml_{s['lang']}_{i}"]
        row, ok = [], 0
        for a in ASPECTS:
            pred = _sign(getattr(r, f"aspect_{a}"))
            exp = s["expect"][a]
            hit = (pred == exp)
            ok += hit
            row.append(f"{a}:{exp:+d}/{pred:+d}{'' if hit else '  <-MISS'}")
        print(f"  [{s['lang']}] match {ok}/4 | " + " | ".join(row))


def check_consistency(reviews: List[Review],
                      truth: Dict[str, Dict[str, Optional[float]]]) -> None:
    print("\n===== 2) consistency with the dummy ground truth (synthetic data) =====")
    import numpy as np
    per_aspect: Dict[str, List[Tuple[float, float]]] = {a: [] for a in ASPECTS}
    sign_hit = sign_tot = 0
    for r in reviews:
        if r.review_id not in truth:
            continue
        for a in ASPECTS:
            t = truth[r.review_id][a]
            p = getattr(r, f"aspect_{a}")
            if t is None or p is None:      # compare only where both mention the aspect
                continue
            per_aspect[a].append((t, p))
            sign_tot += 1
            sign_hit += (_sign(t) == _sign(p))
    if sign_tot == 0:
        print("  No comparable pairs (is the output empty?)")
        return
    print(f"  Sign-agreement rate (all aspects, both-mentioned only): {sign_hit}/{sign_tot} "
          f"= {sign_hit / sign_tot:.0%}")
    for a in ASPECTS:
        pairs = per_aspect[a]
        if len(pairs) >= 3:
            t = np.array([x[0] for x in pairs]); p = np.array([x[1] for x in pairs])
            r_ = np.corrcoef(t, p)[0, 1] if t.std() > 0 and p.std() > 0 else float("nan")
            print(f"   {a:9} n={len(pairs):3d}  Pearson(truth,pred)={r_:+.3f}")
        else:
            print(f"   {a:9} n={len(pairs):3d}  (insufficient samples)")
    print("  Expected: if the food correlation is positive and sign agreement is high, the direction broadly matches.")


def show_cost(analyzer, n_processed: int) -> None:
    print("\n===== 3) cost estimate =====")
    usage = getattr(analyzer, "total_usage", None)
    if not usage or usage.get("total", 0) == 0:
        print("  No actual token usage (mock, or usage unavailable).")
        print(f"  Running in production (--backend gemini) estimates from measured tokens.")
        return
    per_in = usage["prompt"] / n_processed
    per_out = usage["output"] / n_processed
    per_tok = usage["total"] / n_processed
    cost_per = (per_in * PRICE_IN_PER_1M + per_out * PRICE_OUT_PER_1M) / 1e6
    print(f"  Measured: prompt={usage['prompt']} out={usage['output']} "
          f"total={usage['total']} tokens / {n_processed} reviews")
    print(f"  Per review: ~{per_tok:.0f} tokens "
          f"(in {per_in:.0f} / out {per_out:.0f})  ≈ ${cost_per:.5f} {PRICE_NOTE}")
    total_cost = cost_per * BCN_TOTAL
    print(f"  Barcelona {BCN_PLACES} places x {REVIEWS_PER_PLACE} reviews = "
          f"{BCN_TOTAL} items → estimated ${total_cost:.2f} {PRICE_NOTE}")
    print(f"  Rate settings: input ${PRICE_IN_PER_1M}/1M, output ${PRICE_OUT_PER_1M}/1M (to be confirmed)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="gemini", choices=["gemini", "mock", "simple"])
    ap.add_argument("--n", type=int, default=14, help="number of synthetic reviews")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    reviews, truth = build_reviews(args.n, args.seed)
    print(f"backend={args.backend}  reviews={len(reviews)} "
          f"(synth={len(truth)} + multilingual={len(MULTILINGUAL)})")

    analyzer = _make_analyzer(args.backend)
    analyzer.analyze(reviews)

    show_outputs(reviews)
    check_multilingual(reviews)
    check_consistency(reviews, truth)
    show_cost(analyzer, n_processed=len(reviews))


if __name__ == "__main__":
    main()
