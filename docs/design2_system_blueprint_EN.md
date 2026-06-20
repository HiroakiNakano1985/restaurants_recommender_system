# Design Document 2: Implementation System Blueprint (for VSCode)

> Purpose: A system design at a level of granularity that lets you start implementation directly in VSCode.
> Approach: Follow the existing `mindful-tourism-group-E` structure (requests + FieldMask + dotenv + Streamlit) while newly stacking on
> **"structured storage that throws away no information," "grid retrieval by district × cuisine," "ABSA → FQS computation," "reranking," and a "Streamlit demo."**
> The critical flaw in the existing code is that `_review_to_text()` crushes a review into a single string and discards its metadata. **Abolishing this and saving reviews as JSONL while keeping the dict structure intact** is the biggest change.

---

## 0. Overall Architecture

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ A. Ingest     │ → │ B. ABSA       │ → │ C. Scoring    │ → │ D. Rerank     │
│ (raw data     │   │ (aspect-based │   │ (FQS          │   │ (reranking)   │
│  retrieval)   │   │  sentiment)   │   │  computation) │   │               │
└──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
        │                                                          │
        │                  ┌──────────────┐   ┌──────────────┐    │
        └─ fallback ─────→ │ A-sim.        │   │ E. Streamlit  │ ←─┘
                           │ synthetic     │   │ (demo UI)     │
                           │ data gen.     │   │               │
                           └──────────────┘   └──────┬───────┘
                                                      │
                                       ┌──────────────┴───────┐
                                       │ F. Eval (evaluation   │
                                       │     & validation)     │
                                       └──────────────────────┘
```

---

## 1. Directory Structure (new)

```
bcn-food-quality/
├── .env                          # API keys (gitignore)
├── .env.example
├── requirements.txt
├── README.md
│
├── config/
│   ├── districts.py              # Barcelona district list (tagged tourist/local)
│   └── cuisines.py               # cuisine genre list
│
├── ingest/
│   ├── places_grid.py            # ★Module A: grid retrieval by district × cuisine
│   ├── schema.py                 # structured schema definitions for reviews/places
│   └── synth.py                  # ★Module A-sim: synthetic data generator
│
├── nlp/
│   ├── absa.py                   # ★Module B: aspect-based sentiment analysis
│   └── reviewer_profile.py       # reviewer reliability (for McAuley)
│
├── scoring/
│   ├── fqs.py                    # ★Module C: Food Quality Score computation
│   └── weights.py                # signal weights (time decay, etc.)
│
├── rerank/
│   └── reranker.py               # ★Module D: reranking + rank delta
│
├── eval/
│   ├── proxy_labels.py           # load Michelin/Repsol listing lists
│   └── metrics.py                # Precision@K, NDCG, AUC, ablation
│
├── app/
│   └── streamlit_app.py          # ★Module E: demo UI
│
├── analysis/
│   └── divergence_report.py      # auto-render STEP2-4 of Design Document 1
│
└── data/
    ├── raw/                      # retrieved raw reviews (JSONL)
    ├── processed/                # ABSA-annotated (Parquet)
    └── labels/                   # proxy ground-truth labels (CSV)
```

---

## 2. Data Schema (most important: throw away no information)

### 2-A. Review (`Review`)
```python
# ingest/schema.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Review:
    place_id: str
    review_id: str
    rating: int                      # 1-5 (per-review. Do not bury it in a string!)
    text: str
    lang: Optional[str] = None       # language detection result
    author_name: Optional[str] = None
    author_id: Optional[str] = None  # not available in Places. Available in McAuley
    publish_time: Optional[str] = None      # ISO (if available)
    relative_time: Optional[str] = None     # "2 months ago" etc. (this is what Places New gives)
    has_photo: bool = False
    photo_count: int = 0
    # ↓ assigned after ABSA
    aspect_food: Optional[float] = None      # -1 to +1, None if not mentioned
    aspect_service: Optional[float] = None
    aspect_ambiance: Optional[float] = None
    aspect_price: Optional[float] = None
```

### 2-B. Place (`Place`)
```python
@dataclass
class Place:
    place_id: str
    name: str
    star_rating: float               # Google aggregate stars
    review_count: int
    cuisine: Optional[str] = None    # genre (primaryType, etc.)
    price_level: Optional[str] = None
    lat: float = 0.0
    lng: float = 0.0
    district: Optional[str] = None   # district (used for tourist/local classification)
    is_tourist_area: Optional[bool] = None
    # ↓ assigned after computation
    fqs: Optional[float] = None      # Food Quality Score
    fqs_rank: Optional[int] = None
    star_rank: Optional[int] = None
    rank_delta: Optional[int] = None # star_rank - fqs_rank
```

> **Change from the existing code**: completely remove `_review_to_text()`. Instead of stuffing strings into `page_content`, save the dataclasses above as JSONL, one review per line. Use ChromaDB only at the stage where "text search" is required (the natural-language search in Streamlit), and **use the structured data for score computation**.

---

## 3. Module A: Grid Retrieval (`ingest/places_grid.py`)

### Design Intent
The existing `"best restaurants in {city}"` query **only captures the head of the distribution** (i.e., popular places that already have high stars).
The core of this proposal is the **divergence** between "the ☆4.6 dud" and "the high-3-star gem," so we switch to a grid search that **picks up the tail of the distribution**.

### Specification
```python
# config/districts.py
DISTRICTS = [
    {"name": "La Rambla",   "tourist": True},
    {"name": "Barceloneta", "tourist": True},
    {"name": "Gothic Quarter", "tourist": True},
    {"name": "Gràcia",      "tourist": False},
    {"name": "Sant Andreu", "tourist": False},
    {"name": "Sants",       "tourist": False},
    {"name": "Eixample",    "tourist": None},  # mixed
    # … about 20 districts
]

# config/cuisines.py
CUISINES = ["tapas", "japanese", "italian", "catalan", "seafood",
            "vegetarian", "burger", "ramen", "paella", "brunch"]
```

```python
# ingest/places_grid.py main logic
def build_queries():
    # grid of district × cuisine (20 × 10 = 200 queries)
    for d in DISTRICTS:
        for c in CUISINES:
            yield f"{c} restaurant in {d['name']}, Barcelona", d

def fetch_grid(limit_per_query=20):
    seen = set()  # dedup by place_id
    for query, district in build_queries():
        places = text_search(query, page_size=20, max_pages=3)  # up to 60 results
        for p in places:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            reviews = get_place_reviews(p["id"])   # up to 5 reviews
            save_jsonl(p, reviews, district)        # structured storage
```

### FieldMask (mindful of billing SKUs)
```python
# Text Search: narrow to cheap fields
FIELDS_SEARCH = "places.id,places.displayName,places.rating,places.userRatingCount,places.priceLevel,places.location,places.primaryType,places.formattedAddress"

# Place Details: reviews are the Atmosphere SKU (most expensive). Keep to the bare minimum
FIELDS_DETAILS = "id,rating,reviews"
```

### Pagination
The existing code stops at one page (20 results). Add a loop that retrieves **up to 60 results** via `nextPageToken`.

### Cost Estimate (reference)
- Text Search 200 calls + Place Details 800 calls (Atmosphere SKU) ≈ on the order of tens of dollars.
- ⚠️ The $200 free credit may have been discontinued in 2026. Be sure to verify current pricing in the Google Cloud Console before running.

---

## 4. Module A-sim: Synthetic Data Generator (`ingest/synth.py`)

### Design Intent
So that the entire analysis of Design Document 1 can be run even before real data is retrieved, generate **synthetic data that reflects the reality of Barcelona**.
The professor's assignment allows "mock data," so this is legitimate. The key to integrity is to **state the generation assumptions explicitly**.

### Generative Model (embedding the hypotheses)

> **Revision 2026-06-20**: The following is the current formula (consistent with the `ingest/synth.py` implementation). For the reason for the change from the original formula, see the boxed note immediately below.

```python
# Give each place a latent variable for "true food quality"; stars are assumed to inflate, driven by ambiance
true_food_quality ~ Beta(2,2)            # latent food quality in 0-1 (the true-value axis of FQS)
is_tourist_area    ~ Bernoulli(p=district-dependent)
ambiance           = tourist: Uniform(0.3, 1.0) / local: Uniform(0.0, 0.35)  # appeal beyond food (terrace / photogenic)

appeal      = 0.35*true_food_quality + 0.65*ambiance   # ambiance dominates the stars
star_rating = clip( 3.4 + 1.7*appeal + noise , 3.0, 5.0 )  # Google's real-world inflated band ~3.4-4.9

# Generate review text too: the more touristy, the lower the food-mention rate and the more ambiance/price mentions
food_mention_prob = 0.7 - 0.4*is_tourist_area
```

This produces **data designed so that "stars and food quality diverge"** → divergence is guaranteed to be detected in the analysis.
Because the stars inflate driven by ambiance, **"tourist-trap places that are ☆4.6 yet have bad food"** are actually generated.

> **Reason for the revision from the original formula**: Originally it was
> `ambiance_boost = is_tourist * Uniform(0,0.8)` / `star = clip(1 + 4*(0.5*tfq + 0.5*ambiance_boost) + noise, 1, 5)`,
> but this yielded a center-skewed star distribution averaging ~2.4, which (a) diverged from Google's inflated star distribution (real places are generally 3.5 and above), and
> (b) since food accounted for 50% of the stars, "the ☆4.6 dud" was **impossible to produce by construction**, so the thresholds of Design Document 1 STEP2/3 (☆4.0/4.5) yielded
> zero matches. To align with the project premise of "the ☆4.6 dud" and with the figures of Design Document 1, we inflated the stars into the realistic range and
> made the ambiance contribution (0.65) larger than food (0.35).

(Note: "showing divergence with data built to diverge" is circular reasoning, so in the slides state explicitly that **"with real data we will validate it through the same pipeline,"** and position the synthetic data purely as a demonstration that the pipeline works.)

---

## 5. Module B: ABSA (`nlp/absa.py`)

### Options (accuracy vs. ease)
| Method | Pros | Cons | Recommendation |
|---|---|---|---|
| **Aspect extraction with an LLM (Gemini/GPT)** | Strong on multilingual, fast to implement, reuses existing assets | API cost, reproducibility | ★Top choice (existing track record of using Gemini) |
| Dedicated ABSA model (PyABSA, SemEval family) | Offline, reproducible | Weak on multilingual / Catalan | Runner-up |
| Dictionary + rules | Lightweight | Low accuracy | Demo only |

### LLM Approach Specification
```python
# nlp/absa.py
PROMPT = """
Analyze this restaurant review. For each aspect, return sentiment in [-1, 1],
or null if the aspect is not mentioned. Return JSON only.
Aspects: food, service, ambiance, price.
Review: {text}
"""
# Example output: {"food": 0.8, "service": null, "ambiance": -0.2, "price": 0.5}
```
- Stabilize with batch processing + JSON mode (reusing the existing Gemini JSON mode track record).
- Reviews where `food` is null are treated as "food not mentioned" and used in the STEP3 aggregation.

---

## 6. Module C: FQS Computation (`scoring/fqs.py`)

```python
def compute_fqs(place_reviews, weights):
    """Compute a place's Food Quality Score"""
    contribs = []
    for r in place_reviews:
        if r.aspect_food is None:       # exclude reviews not mentioning food
            continue
        w = 1.0
        w *= time_decay(r.publish_time, weights.half_life_days)   # ③ time decay
        w *= reviewer_weight(r.author_id, weights)                # ② reliability (McAuley only)
        contribs.append((r.aspect_food, w))
    if not contribs:
        return None                     # a place with zero food mentions
    fqs_raw = weighted_mean(contribs)
    return normalize_by_cuisine(fqs_raw, place.cuisine)           # ④ cuisine normalization
```

### Weight Design (`scoring/weights.py`)
```python
@dataclass
class Weights:
    half_life_days: int = 365        # ③ weight halves over 1 year
    use_reviewer_weight: bool = False # ② True only for McAuley
    reviewer_food_focus_boost: float = 1.5
```

> For the sake of ablation (evaluation), design each weight so it **can be toggled ON/OFF via a flag**.

---

## 7. Module D: Reranking (`rerank/reranker.py`)

```python
def rerank(places, scope="district_cuisine"):
    """Compare star order and FQS order within the same area and same cuisine"""
    for group in group_by(places, scope):
        rank_by_star = sorted(group, key=lambda p: -p.star_rating)
        rank_by_fqs  = sorted(group, key=lambda p: -(p.fqs or 0))
        for p in group:
            p.star_rank = rank_by_star.index(p) + 1
            p.fqs_rank  = rank_by_fqs.index(p) + 1
            p.rank_delta = p.star_rank - p.fqs_rank
    # rank_delta > 0 : low in stars but rises in FQS = an undiscovered gem
    # rank_delta < 0 : high in stars but drops in FQS = a tourist-trap place
```

---

## 8. Module E: Streamlit Demo UI (`app/streamlit_app.py`)

### Screen Layout (reusing existing Streamlit assets)
```
┌─────────────────────────────────────────┐
│ Sidebar                                   │
│  - district select / cuisine select       │
│  - sort axis: [Google stars] [Food Quality]│ ← the toggle is the heart of the demo
│  - weight sliders (time decay, etc.)       │
├─────────────────────────────────────────┤
│ Main                                      │
│  [scatter] stars vs FQS (Design Doc 1 Fig.1)│
│  [place card]                             │
│    name / ⭐4.6 / 🍽FQS 2.8 / ↓trap        │
│    "80% of these reviews are terrace & beer"│
│  [map] tourist-trap places red, gems green │
└─────────────────────────────────────────┘
```
- The most compelling demo is **toggling between "viewing the same area by stars vs. by food quality."**
- For each place, an explanation of "why this FQS" (food-mention rate, representative review excerpts) = explainability.

---

## 9. Module F: Evaluation (`eval/metrics.py`)

Implements §3 of Design Document 1.
```python
def evaluate(places, proxy_label_set):
    """Using expert-guide-listed places as ground truth, compare the ranking quality of stars vs FQS"""
    y_true = [p.place_id in proxy_label_set for p in places]
    results = {}
    for scorer_name, score in [("star", "star_rating"), ("fqs", "fqs")]:
        ranked = sorted(places, key=lambda p: -getattr(p, score))
        results[scorer_name] = {
            "precision@10": precision_at_k(ranked, proxy_label_set, 10),
            "ndcg@10":      ndcg_at_k(ranked, y_true, 10),
            "auc":          roc_auc(getattr_list(places, score), y_true),
        }
    return results   # compare star and fqs side by side
```
- Ablation: toggle the `Weights` flags and repeat `evaluate`, tabulating each signal's contribution.

---

## 10. requirements.txt (additions)
```
requests
python-dotenv
pandas
pyarrow            # Parquet
numpy
scikit-learn       # metrics
scipy              # correlation
matplotlib
streamlit
folium
streamlit-folium
google-generativeai   # ABSA (Gemini)
langdetect            # language detection
# chromadb / langchain only if adding natural-language search
```

---

## 11. Implementation Order (recommended)

1. **schema.py + synth.py** … run the whole thing end-to-end first with synthetic data (don't wait on real data)
2. **absa.py (LLM version)** … annotate aspects onto the synthetic text
3. **fqs.py + reranker.py** … scoring and reranking
4. **divergence_report.py** … auto-generate Figures 1-3 of Design Document 1 ← first results here
5. **metrics.py** … evaluation (under synthetic data, the proxy labels are synthetic too)
6. **streamlit_app.py** … demo UI
7. **places_grid.py** … real data retrieval (after obtaining an API key) → flow it through the same pipeline
8. Re-run 4-5 on real data → swap in the production figures

> Key point: **If you complete 1-6 with synthetic data, the figures will be replaced with the real thing the moment real data (7) arrives.** A design where the presence or absence of real-data retrieval is not a bottleneck.

---

## 12. Migration Notes from the Existing Code

| Existing (mindful-tourism) | This project | Reason for change |
|---|---|---|
| `_review_to_text()` string concatenation | `Review` dataclass + JSONL | don't throw away metadata |
| `"best restaurants"` single query | district × cuisine grid | pick up the tail of the distribution |
| stops at 20 results on one page | 60 results via nextPageToken | secure enough samples |
| score depends on ChromaDB | score from structured data, Chroma for search only | accuracy of numerical computation |
| category = restaurant lumped together | subdivide by genre via primaryType | for ④ normalization |
