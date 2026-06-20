"""Blueprint 1 §3-A / Blueprint 2 §9: proxy ground-truth labels (external truth for "good-food places").

Because there is no ground-truth label, places listed in expert guides serve as the
proxy ground truth for "good-food places". This module returns the set of listed
places (a set of place_id). Real labels and synthetic labels can be swapped through
**the same interface** (get_proxy_labels).

  - Real labels      : CSV in data/labels/ (a list of place_id or name for Michelin / Repsol listings)
  - Synthetic labels : treat the top X% of Place.true_food_quality as listed (for demos before real data is available)

WARNING: Synthetic labels are based on Place.true_food_quality (the latent ground truth of synth). This
  is a signal independent of the aspect_food that FQS depends on, so it avoids the "label ≈ FQS"
  circularity. However, since the synthetic data as a whole builds stars from tfq, favorable
  evaluation results are structurally inevitable. The method is proven with real labels.
"""

from __future__ import annotations

import csv
import os
from typing import Iterable, List, Optional, Set

from ingest.schema import Place


# ---------------------------------------------------------------- synthetic labels
def synthetic_labels(places: List[Place], top_frac: float = 0.2) -> Set[str]:
    """Set of place_id treating the top top_frac of Place.true_food_quality as "listed".

    FQS is never used (only true_food_quality). Places without tfq set are excluded.
    """
    scored = [p for p in places if p.true_food_quality is not None]
    if not scored:
        raise ValueError(
            "no true_food_quality (not from synth?). Cannot build synthetic labels."
        )
    k = max(1, round(len(scored) * top_frac))
    ranked = sorted(scored, key=lambda p: (-p.true_food_quality, p.place_id))
    return {p.place_id for p in ranked[:k]}


# ---------------------------------------------------------------- real labels (CSV)
def labels_from_csv(csv_path: str, places: Optional[List[Place]] = None) -> Set[str]:
    """Read the set of listed places from a CSV. The column is 'place_id' or 'name' (either works).

    For a name column, resolve via the name->place_id of places (places required).
    Also supports a headerless single-column CSV (treats the value as place_id).
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"label CSV not found: {csv_path}")

    name_to_id = {}
    if places:
        name_to_id = {p.name: p.place_id for p in places}

    ids: Set[str] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return ids

    # Detect the header explicitly rather than relying on Sniffer: if the first row has a place_id/name column name, it is a header.
    first = [c.strip().lower() for c in rows[0]]
    if "place_id" in first:
        col, key, body = first.index("place_id"), "place_id", rows[1:]
    elif "name" in first:
        col, key, body = first.index("name"), "name", rows[1:]
    else:
        col, key, body = 0, "place_id", rows   # headerless single column -> treat value as place_id

    unresolved: List[str] = []
    for row in body:
        if not row or col >= len(row):
            continue
        val = row[col].strip()
        if not val:
            continue
        if key == "name":
            pid = name_to_id.get(val)
            if pid is None:
                unresolved.append(val)
            else:
                ids.add(pid)
        else:
            ids.add(val)
    if unresolved:
        print(f"[warn] labels_from_csv: could not resolve name, skipped {len(unresolved)} "
              f"(e.g.: {unresolved[:3]})")
    return ids


# ---------------------------------------------------------------- unified interface
def get_proxy_labels(
    places: List[Place],
    source: str = "synthetic",
    top_frac: float = 0.2,
    csv_path: Optional[str] = None,
) -> Set[str]:
    """Unified interface returning the set of listed places.

    source="synthetic" -> top top_frac of true_food_quality
    source="csv"        -> labels_from_csv(csv_path, places)
    """
    if source == "synthetic":
        return synthetic_labels(places, top_frac)
    if source == "csv":
        if not csv_path:
            raise ValueError("source='csv' requires csv_path.")
        return labels_from_csv(csv_path, places)
    raise ValueError(f"unknown label source: {source}")


def write_labels_csv(csv_path: str, place_ids: Iterable[str]) -> None:
    """Write the set of listed places to a CSV (place_id column) (for CSV-path demos / real-label templates)."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["place_id"])
        for pid in place_ids:
            w.writerow([pid])


if __name__ == "__main__":
    from ingest.synth import generate

    places, _ = generate(n_places=120, seed=42)
    syn = get_proxy_labels(places, source="synthetic", top_frac=0.2)
    print(f"proxy_labels.py OK: synthetic top-20% = {len(syn)}/{len(places)} listed")

    # CSV-path round-trip (the same set can be restored = check that the real-label interface works)
    tmp = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "data", "labels", "_synthetic_demo.csv")
    write_labels_csv(tmp, syn)
    back = get_proxy_labels(places, source="csv", csv_path=tmp)
    assert back == syn, "CSV round-trip mismatch"
    print(f"  CSV round-trip OK: wrote+read {len(back)} ids from {os.path.relpath(tmp)}")
    # also check name-column CSV resolution
    name_csv = tmp.replace("_synthetic_demo", "_name_demo")
    import csv as _csv
    with open(name_csv, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["name"])
        for p in places[:3]:
            w.writerow([p.name])
    by_name = get_proxy_labels(places, source="csv", csv_path=name_csv)
    assert by_name == {p.place_id for p in places[:3]}
    print(f"  name-column resolve OK: {len(by_name)} ids")
