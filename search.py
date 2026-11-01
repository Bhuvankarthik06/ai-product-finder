"""
search.py – Product search: SQL filters first, then keyword / TF-IDF relevance ranking.

The function always returns only serialisable dicts, never ORM objects,
so callers don't need to worry about lazy-loading after the session closes.
"""
import re

from models import Product
from recommender import recommender

# The only sort values the UI is allowed to pass.
VALID_SORTS = {"relevance", "price_asc", "price_desc", "rating_desc"}


def search_products(filters: dict, page: int = 1, page_size: int = 12):
    """Apply structured filters and return a page of matching products.

    Returns:
        items   – list of product dicts for the requested page
        total   – total number of matching products (before pagination)
        relaxed – True when keyword search was relaxed because nothing matched
    """
    # --- 1. SQL-level filters (run in the database, cheap) -------------------
    query = Product.query

    if filters.get("category"):
        query = query.filter(Product.category == filters["category"])
    if filters.get("brand"):
        query = query.filter(Product.brand == filters["brand"])
    if filters.get("min_price") is not None:
        query = query.filter(Product.price >= filters["min_price"])
    if filters.get("max_price") is not None:
        query = query.filter(Product.price <= filters["max_price"])
    if filters.get("min_rating") is not None:
        query = query.filter(Product.rating >= filters["min_rating"])
    if filters.get("in_stock") is True or filters.get("in_stock") == "true":
        query = query.filter(Product.in_stock.is_(True))

    products = query.all()

    # --- 2. In-memory keyword + TF-IDF scoring --------------------------------
    # Use the free-text query OR the keywords extracted by the AI assistant.
    keywords = [k for k in filters.get("keywords", []) if k]
    text = filters.get("q") or " ".join(keywords)
    sort = filters.get("sort", "relevance")
    if sort not in VALID_SORTS:
        sort = "relevance"

    scores: dict[int, float] = {}
    relaxed = False

    if text:
        tfidf = recommender.score_query(text)
        for p in products:
            blob = p.text_blob().lower()
            # Whole-word keyword hits give a bonus on top of TF-IDF cosine score.
            hits = sum(
                1 for k in keywords
                if re.search(r"\b" + re.escape(k) + r"\b", blob)
            )
            scores[p.id] = hits + tfidf.get(p.id, 0.0)

        if keywords or filters.get("q"):
            matched = [p for p in products if scores.get(p.id, 0) > 0]
            # If nothing matched the words, show filter-only results and tell the user.
            relaxed = not bool(matched)
            products = matched or products

    # --- 3. Sorting -----------------------------------------------------------
    if sort == "price_asc":
        products.sort(key=lambda p: p.price)
    elif sort == "price_desc":
        products.sort(key=lambda p: -p.price)
    elif sort == "rating_desc":
        products.sort(key=lambda p: (-p.rating, p.price))
    elif scores:
        # Default relevance sort when there are scores.
        products.sort(key=lambda p: (-scores.get(p.id, 0), -p.rating))
    else:
        # No text search at all – fall back to rating-then-price.
        products.sort(key=lambda p: (-p.rating, p.price))

    # --- 4. Pagination --------------------------------------------------------
    total = len(products)
    start = (page - 1) * page_size
    return [p.to_dict() for p in products[start: start + page_size]], total, relaxed
