"""
llm_assistant.py – Turns a natural-language shopping query into structured filters.

Flow:
  LLM (or rule-based fallback) → validate_filters() → SQL search in app.py

IMPORTANT: The LLM only ever returns *filters*, never product data.
           Its output is always validated and never executed as SQL,
           so it cannot invent products or cause SQL injection.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

ALLOWED_SORTS = {"relevance", "price_asc", "price_desc", "rating_desc"}

# Words that map to a catalog category (used by the fallback parser).
CATEGORY_HINTS = {
    "Smartphones":   ["phone", "smartphone", "mobile"],
    "Laptops":       ["laptop", "notebook", "ultrabook"],
    "Headphones":    ["headphone", "earbud", "earphone", "headset", "airpod"],
    "Smartwatches":  ["smartwatch", "watch", "band", "fitness tracker"],
    "Cameras":       ["camera", "dslr", "mirrorless", "camcorder"],
    "Tablets":       ["tablet", "ipad"],
}

STOPWORDS = {
    "a", "an", "the", "i", "me", "my", "want", "need", "looking", "for", "with", "and", "or",
    "under", "below", "above", "over", "than", "less", "more", "good", "best", "cheap",
    "cheapest", "show", "find", "get", "some", "any", "please", "to", "of", "in", "on", "that",
    "is", "are", "it", "its", "rs", "inr", "rupees", "budget", "between", "around", "about",
    "top", "rated", "high", "low", "price", "buy", "k", "from", "within",
    "something", "anything", "thing", "things", "one", "ones", "like", "would", "can", "you",
    "have", "has", "who", "what", "which", "also", "just", "really", "very", "nice",
}

# System prompt sent to the LLM.
# {categories} and {brands} are replaced with JSON arrays from the live database.
SYSTEM_PROMPT = (
    "You convert shopping requests into search filters for a product catalog.\n"
    "Respond with ONLY a JSON object (no prose, no markdown) with these keys:\n"
    '  "category": one of {categories} or null\n'
    '  "brand": one of {brands} or null\n'
    '  "min_price": integer in INR or null\n'
    '  "max_price": integer in INR or null\n'
    '  "min_rating": number 1-5 or null\n'
    '  "keywords": array of up to 6 short lowercase feature words '
    '(e.g. "camera", "battery", "gaming")\n'
    '  "sort": one of "relevance", "price_asc", "price_desc", "rating_desc"\n'
    'Interpret "20k" as 20000 and "1.5 lakh" as 150000. '
    "Use null when the request does not mention a value."
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _to_int(value):
    """Convert a value to int, returning None on failure."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def validate_filters(raw: dict, categories: list, brands: list):
    """Clamp whatever the LLM returned to safe, known values.

    This function is the security boundary: any LLM hallucinations in
    category/brand names are silently dropped, prices are clamped to
    non-negative integers, and the sort is validated against an allowlist.
    """
    if not isinstance(raw, dict):
        return None

    cat_map   = {c.lower(): c for c in categories}
    brand_map = {b.lower(): b for b in brands}

    category  = cat_map.get(str(raw.get("category") or "").lower())
    brand     = brand_map.get(str(raw.get("brand") or "").lower())

    min_price = _to_int(raw.get("min_price"))
    max_price = _to_int(raw.get("max_price"))
    if min_price is not None and min_price < 0:
        min_price = None
    if max_price is not None and max_price <= 0:
        max_price = None
    if min_price and max_price and min_price > max_price:
        min_price, max_price = max_price, min_price

    rating = raw.get("min_rating")
    try:
        rating = float(rating)
        rating = rating if 1 <= rating <= 5 else None
    except (TypeError, ValueError):
        rating = None

    kws = raw.get("keywords") or []
    if not isinstance(kws, list):
        kws = []
    keywords: list[str] = []
    for k in kws[:6]:
        # Strip everything except letters, digits, spaces, hyphens, plus signs.
        k = re.sub(r"[^a-z0-9 +\-]", "", str(k).lower()).strip()
        if k and k not in STOPWORDS and k not in keywords:
            keywords.append(k)

    sort = raw.get("sort") if raw.get("sort") in ALLOWED_SORTS else "relevance"

    return {
        "category":  category,
        "brand":     brand,
        "min_price": min_price,
        "max_price": max_price,
        "min_rating": rating,
        "keywords":  keywords,
        "sort":      sort,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback parser
# ---------------------------------------------------------------------------

def _parse_money(num: str, suffix: str) -> int:
    """Convert a matched number+suffix string to INR integer."""
    value = float(num.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix in ("k", "thousand"):
        value *= 1_000
    elif suffix in ("l", "lakh", "lac", "lakhs"):
        value *= 100_000
    return int(value)


def rule_based_filters(query: str, categories: list, brands: list) -> dict:
    """Fallback used when no API key is set or the LLM call fails.

    Applies simple regex heuristics to extract category, brand,
    price constraints, sort order, and feature keywords.
    """
    q = query.lower()
    filters: dict = {
        "category": None, "brand": None,
        "min_price": None, "max_price": None,
        "min_rating": None, "keywords": [], "sort": "relevance",
    }

    # Category detection
    for cat, hints in CATEGORY_HINTS.items():
        if cat in categories and any(re.search(r"\b" + re.escape(h), q) for h in hints):
            filters["category"] = cat
            break

    # Brand detection
    for b in brands:
        if re.search(r"\b" + re.escape(b.lower()) + r"\b", q):
            filters["brand"] = b
            break

    # Price parsing
    money = r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lac|lakhs)?"
    between = re.search(
        r"between\s+" + money + r"\s+(?:and|to|-)\s+" + money, q
    )
    if between:
        filters["min_price"] = _parse_money(between.group(1), between.group(2) or between.group(4))
        filters["max_price"] = _parse_money(between.group(3), between.group(4))
    else:
        under = re.search(
            r"(?:under|below|less than|within|upto|up to|max|budget of)"
            r"\s*(?:rs\.?|inr|₹)?\s*" + money, q,
        )
        over = re.search(
            r"(?:above|over|more than|at least|min)"
            r"\s*(?:rs\.?|inr|₹)?\s*" + money, q,
        )
        if under:
            filters["max_price"] = _parse_money(under.group(1), under.group(2))
        if over:
            filters["min_price"] = _parse_money(over.group(1), over.group(2))

    # Sort detection
    if re.search(r"cheap|lowest price|affordable", q):
        filters["sort"] = "price_asc"
    elif re.search(r"top rated|highest rated|best rated", q):
        filters["sort"] = "rating_desc"
    elif "premium" in q or "most expensive" in q:
        filters["sort"] = "price_desc"

    # Keyword extraction
    # Drop words that named the chosen category to avoid redundant search terms.
    hint_words = set(CATEGORY_HINTS.get(filters["category"], []))
    words = re.findall(r"[a-z0-9+]+", re.sub(money, " ", q))
    for w in words:
        if (
            w in STOPWORDS
            or len(w) < 3
            or any(w.startswith(h) for h in hint_words)
            or w in (filters["brand"] or "").lower()
        ):
            continue
        if w not in filters["keywords"]:
            filters["keywords"].append(w)
    filters["keywords"] = filters["keywords"][:6]

    return filters


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_filters(
    query: str,
    categories: list,
    brands: list,
    api_key: str = "",
    model: str = "",
) -> tuple[dict, str]:
    """Return (filters_dict, source) where source is 'llm' or 'rules'.

    The LLM path is only attempted when an API key is present.
    Any failure (timeout, bad JSON, quota exceeded, …) silently falls back
    to the rule-based parser so the app always responds.
    """
    if api_key:
        try:
            import anthropic  # optional dependency – only imported when needed

            client = anthropic.Anthropic(api_key=api_key, timeout=15.0)
            system = SYSTEM_PROMPT.format(
                categories=json.dumps(sorted(categories)),
                brands=json.dumps(sorted(brands)),
            )
            msg = client.messages.create(
                model=model,
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": query[:500]}],
            )
            # Extract the text block(s) from the response.
            text = "".join(
                b.text for b in msg.content if getattr(b, "type", "") == "text"
            )
            # Strip optional markdown code fences the model might add.
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
            filters = validate_filters(json.loads(text), categories, brands)
            if filters:
                return filters, "llm"
        except Exception as exc:
            # Log the error but do NOT expose it to the user.
            logger.warning("LLM failed, using rule-based parser: %s", exc)

    return rule_based_filters(query, categories, brands), "rules"
