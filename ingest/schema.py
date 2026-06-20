"""Design blueprint 2 §2: Data schema (structured storage that discards no information).

This replaces the existing mindful-tourism `_review_to_text()` (which collapses reviews into
a single string). Instead, each review = one dataclass = one JSONL line, preserving metadata
such as rating/author/time/photo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Review:
    """One review = one line. aspect_* is populated after ABSA (§5)."""

    place_id: str
    review_id: str
    rating: int                       # 1-5 (per-review; do NOT embed in the text string!)
    text: str
    lang: Optional[str] = None        # Language detection result
    author_name: Optional[str] = None
    author_id: Optional[str] = None   # Not available from Places; available from McAuley
    publish_time: Optional[str] = None     # ISO (if available)
    relative_time: Optional[str] = None    # "2 months ago" etc. (this is what Places New returns)
    has_photo: bool = False
    photo_count: int = 0
    # Populated after ABSA (-1 to +1; None if not mentioned)
    aspect_food: Optional[float] = None
    aspect_service: Optional[float] = None
    aspect_ambiance: Optional[float] = None
    aspect_price: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Review":
        # Ignore unknown keys from the JSONL and keep only known fields
        fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in fields})


@dataclass
class Place:
    """One restaurant. fqs/*_rank/rank_delta are populated after scoring (§6) and rerank (§7)."""

    place_id: str
    name: str
    star_rating: float                # Google-aggregated star rating
    review_count: int
    cuisine: Optional[str] = None     # Genre (primaryType etc.)
    price_level: Optional[str] = None
    lat: float = 0.0
    lng: float = 0.0
    district: Optional[str] = None    # District (used for tourist/local classification)
    is_tourist_area: Optional[bool] = None
    # Populated after computation
    fqs: Optional[float] = None       # Food Quality Score
    fqs_rank: Optional[int] = None
    star_rank: Optional[int] = None
    rank_delta: Optional[int] = None  # star_rank - fqs_rank

    # -- Ground-truth latent variables used solely for eval-label generation (stored by synth.py) --
    # WARNING - LEAK: these are used ONLY to generate the "proxy ground-truth labels" in
    #   eval/proxy_labels.py. NEVER reference them in FQS computation (scoring/fqs.py),
    #   ABSA (nlp/absa.py), or rerank.
    #   (Referencing them would leak true_food_quality into the FQS, making the evaluation a
    #    trivially circular argument.)
    #   These do not exist in real data = synthetic-data-only fields.
    true_food_quality: Optional[float] = None  # synth latent tfq (true food quality, 0-1)
    true_ambiance: Optional[float] = None       # synth latent ambiance (non-food appeal, 0-1)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Place":
        fields = cls.__dataclass_fields__  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in fields})


if __name__ == "__main__":
    # Minimal sanity check: round-trip serialization
    r = Review(place_id="p1", review_id="r1", rating=5, text="great paella",
               aspect_food=0.8)
    assert Review.from_dict(r.to_dict()) == r
    p = Place(place_id="p1", name="Test", star_rating=4.6, review_count=120,
              cuisine="paella", district="La Rambla", is_tourist_area=True)
    assert Place.from_dict(p.to_dict()) == p
    # Unknown keys should be ignored
    assert Review.from_dict({**r.to_dict(), "extra": 1}) == r
    print("schema.py OK:", r.to_dict())
