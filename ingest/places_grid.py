"""Design blueprint 2 §3: Module A — collect real Barcelona data over a district x genre grid.

Design intent: "best restaurants in {city}" only captures the head of the distribution. The core
of this proposal is the divergence between "4.6-star dud restaurants" and "good restaurants in
the low-3-star range," so a district x genre grid search is used to pick up **the tail of the
distribution**. No information is discarded; data is saved to JSONL as the Place/Review dataclasses
from schema.py.

⚠ This module **incurs real charges**. The Place Details (New) reviews are the Atmosphere SKU
  (the most expensive), so already-fetched place_ids are cached to avoid double-charging, and a
  delay is inserted between each request. __main__ does nothing without an explicit flag (to
  prevent accidental charges).

FieldMask (mindful of billing SKUs):
  Text Search   : places.id,displayName,rating,userRatingCount,priceLevel,location,primaryType,formattedAddress
  Place Details : id,rating,reviews  <- reviews is the Atmosphere SKU. Do not add extra fields

Storage format: data/raw/bcn.jsonl. 1 line = 1 restaurant = {"place": <Place dict>, "reviews": [<Review dict>...]}.
  (Satisfies design blueprint 2 §2 "discard no information" while preserving the Place-Review
    correspondence in a form that is easy for downstream stages to read. If a one-review-per-line
    format is needed, it can be converted later.)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Dict, Iterator, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv

from config.cuisines import CUISINES
from config.districts import DISTRICTS
from ingest.schema import Place, Review

load_dotenv()

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

FIELDS_SEARCH = ("places.id,places.displayName,places.rating,places.userRatingCount,"
                 "places.priceLevel,places.location,places.primaryType,"
                 "places.formattedAddress")
FIELDS_DETAILS = "id,rating,reviews"

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw", "bcn.jsonl")
SEEN_SIDECAR = DEFAULT_OUT + ".seen.json"

PAGE_SIZE = 20            # Max per Text Search page
MAX_PAGES_PROD = 3       # Up to 60 results/query via nextPageToken
REVIEWS_PER_PLACE = 5     # Place Details returns at most 5 reviews (hard constraint)


# ---------------------------------------------------------------- Billing counter
class Cost:
    def __init__(self) -> None:
        self.text_search = 0
        self.place_details = 0

    def __str__(self) -> str:
        return (f"Text Search={self.text_search} calls, "
                f"Place Details(Atmosphere SKU)={self.place_details} calls")


# ---------------------------------------------------------------- Authentication
def _api_key() -> str:
    key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not set (check .env).")
    return key


def _headers(field_mask: str) -> Dict[str, str]:
    # The key goes in the header only. Never log or print it.
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _api_key(),
        "X-Goog-FieldMask": field_mask,
    }


# ---------------------------------------------------------------- Query generation
def build_queries(districts=DISTRICTS, cuisines=CUISINES) -> Iterator[Tuple[str, dict, str]]:
    for d in districts:
        for c in cuisines:
            yield f"{c} restaurant in {d['name']}, Barcelona", d, c


# ---------------------------------------------------------------- Text Search
def text_search(query: str, cost: Cost, max_pages: int = MAX_PAGES_PROD,
                delay: float = 1.5) -> List[dict]:
    """Fetch up to max_pages pages via nextPageToken (= up to 20*max_pages results)."""
    results: List[dict] = []
    page_token: Optional[str] = None
    for page in range(max_pages):
        body: Dict[str, object] = {"textQuery": query, "pageSize": PAGE_SIZE}
        if page_token:
            body["pageToken"] = page_token
        resp = requests.post(SEARCH_URL, headers=_headers(FIELDS_SEARCH),
                             json=body, timeout=30)
        cost.text_search += 1
        if resp.status_code != 200:
            print(f"  [warn] Text Search HTTP {resp.status_code}: {_safe(resp.text)}")
            break
        data = resp.json()
        results.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(delay)   # Wait before fetching the next page (propagation + rate limiting)
    return results


# ---------------------------------------------------------------- Place Details
def get_place_reviews(place_id: str, cost: Cost, delay: float = 1.0) -> List[dict]:
    """Fetch reviews via Place Details (New) (up to 5). Atmosphere SKU."""
    resp = requests.get(DETAILS_URL.format(place_id=place_id),
                        headers=_headers(FIELDS_DETAILS), timeout=30)
    cost.place_details += 1
    if resp.status_code != 200:
        print(f"  [warn] Place Details HTTP {resp.status_code}: {_safe(resp.text)}")
        return []
    time.sleep(delay)
    return resp.json().get("reviews", [])[:REVIEWS_PER_PLACE]


# ---------------------------------------------------------------- dataclass conversion
def to_place(p: dict, district: dict, cuisine: str) -> Place:
    loc = p.get("location", {}) or {}
    return Place(
        place_id=p["id"],
        name=(p.get("displayName", {}) or {}).get("text", ""),
        star_rating=float(p.get("rating", 0.0) or 0.0),
        review_count=int(p.get("userRatingCount", 0) or 0),
        cuisine=cuisine,                       # Search genre (primaryType is fetched separately but is outside the schema)
        price_level=p.get("priceLevel"),       # enum string (PRICE_LEVEL_*)
        lat=float(loc.get("latitude", 0.0) or 0.0),
        lng=float(loc.get("longitude", 0.0) or 0.0),
        district=district["name"],
        is_tourist_area=district["tourist"],
    )


def to_reviews(place_id: str, raw_reviews: List[dict]) -> List[Review]:
    out: List[Review] = []
    for i, r in enumerate(raw_reviews):
        # Prefer originalText (original language) = better for ABSA's multilingual processing. Fall back to text.
        orig = r.get("originalText") or {}
        disp = r.get("text") or {}
        text = orig.get("text") or disp.get("text") or ""
        lang = orig.get("languageCode") or disp.get("languageCode")
        name = r.get("name", "")
        review_id = name.split("/")[-1] if "/reviews/" in name else f"{place_id}_r{i:02d}"
        author = (r.get("authorAttribution") or {}).get("displayName")
        out.append(Review(
            place_id=place_id,
            review_id=review_id,
            rating=int(r.get("rating", 0) or 0),
            text=text,
            lang=lang,
            author_name=author,
            author_id=None,                         # Not available from Places (known, design blueprint 1 §1)
            publish_time=r.get("publishTime"),       # ISO absolute timestamp (used for time decay if present)
            relative_time=r.get("relativePublishTimeDescription"),  # "2 months ago" etc.
            has_photo=False,                         # Not fetched with this FieldMask
            photo_count=0,
        ))
    return out


# ---------------------------------------------------------------- Saving / caching
def load_seen(out_path: str) -> Set[str]:
    """Gather already-fetched place_ids from the existing JSONL + sidecar (to prevent double-charging)."""
    seen: Set[str] = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    pid = (rec.get("place") or {}).get("place_id")
                    if pid:
                        seen.add(pid)
                except json.JSONDecodeError:
                    continue
    side = out_path + ".seen.json"
    if os.path.exists(side):
        try:
            seen |= set(json.load(open(side, encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return seen


def load_bcn_jsonl(path: str = DEFAULT_OUT) -> Tuple[List[Place], List[Review]]:
    """Restore saved JSONL into Place/Review dataclasses (no charge; loader for downstream pipeline)."""
    places: List[Place] = []
    reviews: List[Review] = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} does not exist. Fetch the data first.")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            places.append(Place.from_dict(rec["place"]))
            for rv in rec.get("reviews", []):
                reviews.append(Review.from_dict(rv))
    return places, reviews


def append_record(out_path: str, place: Place, reviews: List[Review]) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rec = {"place": place.to_dict(), "reviews": [r.to_dict() for r in reviews]}
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def save_seen(out_path: str, seen: Set[str]) -> None:
    with open(out_path + ".seen.json", "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)


def _safe(text: str) -> str:
    """Redact the key from the response string just in case (normally it is not included)."""
    key = os.getenv("GOOGLE_PLACES_API_KEY") or ""
    return text.replace(key, "***REDACTED***") if key else text


# ---------------------------------------------------------------- Orchestration
def fetch_grid(
    districts,
    cuisines,
    out_path: str = DEFAULT_OUT,
    max_pages: int = MAX_PAGES_PROD,
    max_details_per_query: Optional[int] = None,   # For smoke tests: cap on Details calls per query
    max_detail_calls: Optional[int] = None,        # Overall safety cap on Details calls
    search_delay: float = 1.5,
    details_delay: float = 1.0,
) -> Cost:
    """Walk the grid to fetch and save. Skip already-fetched place_ids (do not re-charge Details)."""
    cost = Cost()
    seen = load_seen(out_path)
    print(f"Already-fetched place_ids: {len(seen)} (these skip Details)")
    new_places = 0

    for query, district, cuisine in build_queries(districts, cuisines):
        print(f"\n[query] {query}")
        places = text_search(query, cost, max_pages=max_pages, delay=search_delay)
        print(f"  Text Search returned: {len(places)} results")
        details_this_query = 0
        for p in places:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            if max_detail_calls is not None and cost.place_details >= max_detail_calls:
                print("  [stop] Reached overall Details cap. Aborting.")
                save_seen(out_path, seen)
                return cost
            if max_details_per_query is not None and details_this_query >= max_details_per_query:
                break
            seen.add(pid)
            raw_reviews = get_place_reviews(pid, cost, delay=details_delay)
            place = to_place(p, district, cuisine)
            reviews = to_reviews(pid, raw_reviews)
            append_record(out_path, place, reviews)
            new_places += 1
            details_this_query += 1

    save_seen(out_path, seen)
    print(f"\nNewly saved: {new_places} restaurants -> {os.path.relpath(out_path)}")
    print(f"Cost: {cost}")
    return cost


# ---------------------------------------------------------------- Report (for smoke tests)
def report_jsonl(out_path: str, max_records: int = 3) -> None:
    if not os.path.exists(out_path):
        print("(JSONL not created)")
        return
    with open(out_path, encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    print(f"\n===== Saved results: {len(lines)} restaurants in {os.path.relpath(out_path)} =====")
    n_pub = n_rev = 0
    for line in lines:
        rec = json.loads(line)
        revs = rec.get("reviews", [])
        n_rev += len(revs)
        n_pub += sum(1 for r in revs if r.get("publish_time"))
        pl = rec["place"]
        print(f"  - {pl['name'][:32]:32} ⭐{pl['star_rating']} "
              f"({pl['review_count']} reviews) [{pl['cuisine']}/{pl['district']}] "
              f"reviews fetched={len(revs)}")
    print(f"  total reviews={n_rev}  with publish_time(ISO)={n_pub}/{n_rev}")
    if lines:
        print("\n----- Full JSONL record (first restaurant) -----")
        print(json.dumps(json.loads(lines[0]), ensure_ascii=False, indent=2))


def smoke(out_path: str = DEFAULT_OUT, max_pages: int = 1,
          max_details_per_query: Optional[int] = 5) -> None:
    """Stage 1: Gràcia x [tapas, japanese] = just 2 queries. With caps to minimize cost."""
    gracia = [d for d in DISTRICTS if d["name"] == "Gràcia"]
    cuisines = ["tapas", "japanese"]
    print("=== Stage 1 smoke test: Gràcia x [tapas, japanese] ===")
    print(f"  Settings: max_pages={max_pages} ({'up to 20 per page' if max_pages==1 else f'up to {max_pages*20} results'}), "
          f"max_details_per_query={max_details_per_query}")
    cost = fetch_grid(gracia, cuisines, out_path=out_path, max_pages=max_pages,
                      max_details_per_query=max_details_per_query)
    report_jsonl(out_path)
    print(f"\n*** Actual smoke-test cost: {cost} ***")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BCN grid ingest (warning: incurs real charges)")
    ap.add_argument("--smoke", action="store_true", help="Stage 1: 2-query smoke test")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--max-pages", type=int, default=1, help="Number of pages during the smoke test")
    ap.add_argument("--max-details-per-query", type=int, default=5)
    args = ap.parse_args()

    if args.smoke:
        smoke(out_path=args.out, max_pages=args.max_pages,
              max_details_per_query=args.max_details_per_query)
    else:
        print("Doing nothing (to prevent accidental charges). Add --smoke to run the smoke test.")
        print("The production grid is run separately after the stage 1 check.")
