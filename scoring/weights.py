"""Design 2 §6: weights for the signals used in FQS computation.

Designed so that each signal can be **toggled ON/OFF via a flag** for ablation
(Design 1 §3-C).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Weights:
    half_life_days: int = 365            # ③ time decay: weight halves every year
    use_reviewer_weight: bool = False    # ② reviewer credibility (True only for McAuley)
    reviewer_food_focus_boost: float = 1.5
    # ④ per-cuisine normalization. Design 2 §6 calls it unconditionally inside
    #    compute_fqs, but we make it an explicit flag to allow ablation
    #    (same intent, default True).
    normalize_by_cuisine: bool = True


if __name__ == "__main__":
    w = Weights()
    assert w.half_life_days == 365 and w.normalize_by_cuisine is True
    off = Weights(half_life_days=10**9, normalize_by_cuisine=False)
    print("weights.py OK:", w)
    print("  ablation example (no decay, no norm):", off)
