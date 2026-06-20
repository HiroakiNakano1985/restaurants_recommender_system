"""Design 2 §5: Module B — Aspect-Based Sentiment Analysis.

Decompose each review into the four aspects food / service / ambiance / price and
assign each a sentiment polarity in [-1, 1] (None if not mentioned).

There are two backends. The **interface (AbsaAnalyzer / get_analyzer / analyze) is
shared**, so they can be swapped without changing fqs.py:

  - SimpleAbsa : reads the aspect_* values already embedded in the synthetic data (no API key, offline)
  - LlmAbsa    : extracts aspects from the review text with Gemini (JSON mode, batched, multilingual)

Switching:
  get_analyzer("simple") / get_analyzer("gemini")
  or the environment variable ABSA_BACKEND=simple|gemini (referenced when get_analyzer() is called with no arguments)

Following the Gemini implementation in the existing mindful-tourism
(group_E/llm/client.py), this uses the new SDK `google-genai`
(Design 2 §10 lists the legacy `google-generativeai`, but we matched the
running reference implementation).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Protocol

from ingest.schema import Review

logger = logging.getLogger("absa")

ASPECTS = ("food", "service", "ambiance", "price")


class AbsaAnalyzer(Protocol):
    """Shared interface for ABSA implementations. Both the simple and LLM versions follow it."""

    def analyze(self, reviews: List[Review]) -> List[Review]:
        """Fill in each review's aspect_* and return them (the same objects may be mutated in place)."""
        ...


# ---------------------------------------------------------------- shared helpers
def _coerce_aspect(v) -> Optional[float]:
    """Normalize the LLM output to a float in [-1, 1] or None. Returns None if it can't be coerced to a number."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, f))


def _apply_aspects(review: Review, parsed: Dict) -> None:
    for asp in ASPECTS:
        setattr(review, f"aspect_{asp}", _coerce_aspect(parsed.get(asp)))


# ---------------------------------------------------------------- SimpleAbsa
class SimpleAbsa:
    """Simple version: adopt the aspect_* values already embedded in the synthetic data.

    Since synth.py sets aspect_* as ground truth, here we just return them
    (with only a range check if needed). No LLM call, no API key.
    """

    def analyze(self, reviews: List[Review]) -> List[Review]:
        for r in reviews:
            for asp in ASPECTS:
                v = getattr(r, f"aspect_{asp}")
                if v is not None:
                    setattr(r, f"aspect_{asp}", max(-1.0, min(1.0, float(v))))
        return reviews


# ---------------------------------------------------------------- LlmAbsa (Gemini)
class LlmAbsa:
    """Gemini-based ABSA. Extracts aspect polarities from the review text.

    - Stabilized with JSON mode (response_mime_type="application/json").
    - Batched processing (default batch_size=8). Falls back to per-item retry on malformed JSON / count mismatch.
    - The prompt instructs language-agnostic extraction across multiple languages (English, Spanish, Catalan, etc.).
    - On API/JSON failure, **it does not silently set all aspects to null**; it logs a warning and skips.
    """

    SYSTEM = (
        "You are an aspect-based sentiment analysis engine for restaurant reviews.\n"
        "Reviews may be written in ANY language (commonly English, Spanish, or "
        "Catalan in Barcelona). Analyze them regardless of language — do NOT "
        "translate, just extract sentiment.\n"
        "For each review return sentiment for four aspects: food, service, "
        "ambiance, price.\n"
        "Each value is a number in [-1, 1] (-1 = very negative, 0 = neutral, "
        "+1 = very positive), or null if that aspect is NOT mentioned in the review.\n"
        "Only judge an aspect from what the review actually says about it.\n"
        "Respond with VALID JSON ONLY — no prose, no markdown."
    )

    # Single-item prompt (fallback). {text} is interpolated.
    SINGLE_INSTR = (
        'Analyze this restaurant review. Return a JSON object exactly like '
        '{{"food": <number|null>, "service": <number|null>, '
        '"ambiance": <number|null>, "price": <number|null>}}.\n'
        "Review: {text}"
    )

    def __init__(self, model: str = "gemini-2.5-flash-lite", batch_size: int = 8,
                 temperature: float = 0.0, api_key: Optional[str] = None,
                 timeout_ms: int = 45_000, max_retries: int = 3,
                 retry_delay: float = 2.0):
        self.model = model
        self.batch_size = batch_size
        self.temperature = temperature
        self._api_key = api_key
        self._client = None  # lazily created (so import doesn't break in environments without an API key)
        # ↓ Hang protection: always attach a timeout to each request; if it stalls, retry a few times and give up
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # -- low level ------------------------------------------------------------
    def _get_client(self):
        if self._client is None:
            from google import genai  # lazy import
            from google.genai import types
            key = self._api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set. Set it in .env or use SimpleAbsa."
                )
            # http_options.timeout (milliseconds) caps the whole request to prevent infinite hangs
            self._client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(timeout=self.timeout_ms),
            )
        return self._client

    def _generate(self, user: str, max_tokens: int) -> str:
        from google.genai import types
        cfg = types.GenerateContentConfig(
            system_instruction=self.SYSTEM,
            temperature=self.temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._get_client().models.generate_content(
                    model=self.model, contents=user, config=cfg)
                break
            except Exception as exc:  # noqa: BLE001  (retry on timeout/transient errors)
                last_exc = exc
                logger.warning("generate attempt %d/%d failed: %s",
                               attempt + 1, self.max_retries, exc)
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay)
        else:
            raise last_exc if last_exc else RuntimeError("generate failed")
        # usage is accumulated. Used for cost estimation.
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            self.last_usage = {
                "prompt": getattr(um, "prompt_token_count", 0) or 0,
                "output": getattr(um, "candidates_token_count", 0) or 0,
                "total": getattr(um, "total_token_count", 0) or 0,
            }
            self.total_usage["prompt"] += self.last_usage["prompt"]
            self.total_usage["output"] += self.last_usage["output"]
            self.total_usage["total"] += self.last_usage["total"]
        return resp.text or ""

    # -- parsing --------------------------------------------------------------
    @staticmethod
    def _loads(raw: str):
        """Parse JSON as robustly as possible (strip code fences → direct parse → extract)."""
        if not raw:
            return None
        txt = re.sub(r"```(?:json)?", "", raw).strip()
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass
        # extract an array or object via brace-counting
        for open_c, close_c in (("[", "]"), ("{", "}")):
            depth, start = 0, None
            for i, ch in enumerate(txt):
                if ch == open_c:
                    if start is None:
                        start = i
                    depth += 1
                elif ch == close_c and start is not None:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(txt[start:i + 1])
                        except json.JSONDecodeError:
                            break
        return None

    # -- batch / single -------------------------------------------------------
    def _analyze_batch(self, batch: List[Review]) -> bool:
        """Process a batch in one call. True on success. False on count/ID mismatch or failure (→ per-item)."""
        payload = [{"id": r.review_id, "text": r.text} for r in batch]
        user = (
            "Analyze EACH restaurant review below. Reviews may be in different "
            "languages. Return a JSON ARRAY with one object per review, in the "
            "SAME order, each exactly like "
            '{"id": <id>, "food": <number|null>, "service": <number|null>, '
            '"ambiance": <number|null>, "price": <number|null>}.\n'
            "Reviews (JSON):\n" + json.dumps(payload, ensure_ascii=False)
        )
        try:
            raw = self._generate(user, max_tokens=120 * len(batch) + 200)
        except Exception as exc:  # noqa: BLE001
            logger.warning("batch generate failed (%d reviews): %s", len(batch), exc)
            return False
        parsed = self._loads(raw)
        if not isinstance(parsed, list):
            logger.warning("batch did not return a JSON array; falling back to single")
            return False
        by_id = {str(o.get("id")): o for o in parsed if isinstance(o, dict)}
        if len(by_id) < len(batch):
            logger.warning("batch returned %d/%d objects; falling back to single",
                           len(by_id), len(batch))
            return False
        for r in batch:
            obj = by_id.get(str(r.review_id))
            if obj is None:
                logger.warning("batch missing id=%s; will retry single", r.review_id)
                return False
            _apply_aspects(r, obj)
        return True

    def _analyze_single(self, r: Review) -> bool:
        """Process a single item. True on success; on failure, log a warning and skip (aspects are left untouched)."""
        try:
            raw = self._generate(self.SINGLE_INSTR.format(text=r.text), max_tokens=200)
        except Exception as exc:  # noqa: BLE001
            logger.warning("review %s: API error, skipped: %s", r.review_id, exc)
            return False
        parsed = self._loads(raw)
        if not isinstance(parsed, dict):
            logger.warning("review %s: JSON parse failed, skipped. raw=%.120r",
                           r.review_id, raw)
            return False
        _apply_aspects(r, parsed)
        return True

    def analyze(self, reviews: List[Review]) -> List[Review]:
        self.total_usage = {"prompt": 0, "output": 0, "total": 0}
        self.last_usage = {}
        self.n_failed = 0
        for i in range(0, len(reviews), self.batch_size):
            batch = reviews[i:i + self.batch_size]
            if self._analyze_batch(batch):
                continue
            # fallback: process the batch one item at a time
            for r in batch:
                if not self._analyze_single(r):
                    self.n_failed += 1
        if self.n_failed:
            logger.warning("ABSA finished with %d/%d reviews skipped (logged above)",
                           self.n_failed, len(reviews))
        return reviews


# ---------------------------------------------------------------- factory
def get_analyzer(kind: Optional[str] = None, **kwargs) -> AbsaAnalyzer:
    """Factory. If kind is unspecified, refers to the environment variable ABSA_BACKEND (default "simple").

    "simple" / "dummy" → SimpleAbsa
    "gemini" / "llm"   → LlmAbsa
    """
    if kind is None:
        kind = os.getenv("ABSA_BACKEND", "simple")
    kind = kind.lower()
    if kind in ("simple", "dummy"):
        return SimpleAbsa()
    if kind in ("gemini", "llm"):
        return LlmAbsa(**kwargs)
    raise ValueError(f"unknown ABSA backend: {kind}")


if __name__ == "__main__":
    # minimal smoke test (SimpleAbsa only; for real LLM calls see verify_absa_llm.py)
    from ingest.synth import generate

    _, reviews = generate(n_places=10, seed=1)
    before = [r.aspect_food for r in reviews]
    out = get_analyzer("simple").analyze(reviews)
    assert before == [r.aspect_food for r in out]
    assert all(-1.0 <= v <= 1.0 for r in out for v in
               (r.aspect_food, r.aspect_service, r.aspect_ambiance, r.aspect_price)
               if v is not None)
    # the factory switching works
    assert isinstance(get_analyzer("simple"), SimpleAbsa)
    assert isinstance(get_analyzer("gemini"), LlmAbsa)
    assert isinstance(get_analyzer("llm"), LlmAbsa)
    print(f"absa.py OK (SimpleAbsa): {len(out)} reviews; factory simple/gemini switch OK")
