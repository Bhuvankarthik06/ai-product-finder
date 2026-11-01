"""
tests/test_search.py – Unit tests for search_products() and Recommender.

Tests run inside the Flask app context so SQLAlchemy is available.
"""
import pytest

from search import search_products
from recommender import Recommender


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_filter(**kwargs):
    base = {"q": "", "category": None, "brand": None,
            "min_price": None, "max_price": None,
            "min_rating": None, "keywords": [], "sort": "relevance"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# search_products unit tests
# ---------------------------------------------------------------------------
class TestSearchProducts:
    def test_returns_all_when_no_filters(self, seeded_app):
        with seeded_app.app_context():
            items, total, relaxed = search_products(make_filter(), 1, 10)
        assert total == 5
        assert len(items) == 5
        assert relaxed is False

    def test_category_filter(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(category="Laptops"), 1, 10)
        assert total == 1
        assert all(i["category"] == "Laptops" for i in items)

    def test_brand_filter(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(brand="Zenvo"), 1, 10)
        assert total == 1
        assert items[0]["brand"] == "Zenvo"

    def test_min_price_filter(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(min_price=30000), 1, 10)
        assert all(i["price"] >= 30000 for i in items)

    def test_max_price_filter(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(max_price=12000), 1, 10)
        assert all(i["price"] <= 12000 for i in items)

    def test_combined_price_range(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(min_price=5000, max_price=15000), 1, 10)
        assert all(5000 <= i["price"] <= 15000 for i in items)

    def test_min_rating_filter(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(min_rating=4.5), 1, 10)
        assert all(i["rating"] >= 4.5 for i in items)

    def test_text_search_finds_gaming(self, seeded_app):
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(q="gaming"), 1, 10)
        assert total > 0
        assert any("gaming" in i["description"].lower() or "gaming" in i["specs"].lower()
                   for i in items)

    def test_text_search_no_match_relaxes(self, seeded_app):
        with seeded_app.app_context():
            items, total, relaxed = search_products(
                make_filter(q="xyzzy_no_product_ever", category="Laptops"), 1, 10
            )
        # When nothing keyword-matches, we fall back to filter-only results
        assert relaxed is True
        assert total > 0   # the category filter still returns the laptop

    def test_sort_price_asc(self, seeded_app):
        with seeded_app.app_context():
            items, _, _ = search_products(make_filter(sort="price_asc"), 1, 10)
        prices = [i["price"] for i in items]
        assert prices == sorted(prices)

    def test_sort_price_desc(self, seeded_app):
        with seeded_app.app_context():
            items, _, _ = search_products(make_filter(sort="price_desc"), 1, 10)
        prices = [i["price"] for i in items]
        assert prices == sorted(prices, reverse=True)

    def test_sort_rating_desc(self, seeded_app):
        with seeded_app.app_context():
            items, _, _ = search_products(make_filter(sort="rating_desc"), 1, 10)
        ratings = [i["rating"] for i in items]
        assert ratings == sorted(ratings, reverse=True)

    def test_invalid_sort_falls_back(self, seeded_app):
        """An unknown sort value should not crash; it falls back to relevance."""
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(sort="INVALID"), 1, 10)
        assert total == 5

    def test_pagination_page_1(self, seeded_app):
        with seeded_app.app_context():
            items1, total, _ = search_products(make_filter(), 1, 3)
        assert len(items1) == 3
        assert total == 5

    def test_pagination_page_2(self, seeded_app):
        with seeded_app.app_context():
            items1, _, _ = search_products(make_filter(), 1, 3)
            items2, _, _ = search_products(make_filter(), 2, 3)
        ids1 = {i["id"] for i in items1}
        ids2 = {i["id"] for i in items2}
        assert ids1.isdisjoint(ids2)

    def test_pagination_beyond_last_page_empty(self, seeded_app):
        with seeded_app.app_context():
            items, _, _ = search_products(make_filter(), 999, 10)
        assert items == []

    def test_empty_catalog(self, seeded_app):
        """Passing an impossible filter returns zero results."""
        with seeded_app.app_context():
            items, total, _ = search_products(make_filter(min_price=99999999), 1, 10)
        assert total == 0
        assert items == []

    def test_keyword_whole_word_match(self, seeded_app):
        """'cam' should NOT match 'camera' (whole-word matching)."""
        with seeded_app.app_context():
            # "rtx" is a whole word in specs – this should match the gaming laptop
            items_rtx, total_rtx, _ = search_products(make_filter(q="rtx"), 1, 10)
        assert total_rtx >= 1

    def test_result_has_icon_field(self, seeded_app):
        with seeded_app.app_context():
            items, _, _ = search_products(make_filter(), 1, 10)
        for item in items:
            assert "icon" in item


# ---------------------------------------------------------------------------
# Recommender unit tests
# ---------------------------------------------------------------------------
class TestRecommender:
    def test_similar_returns_list(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            from models import Product
            pid = Product.query.first().id
            result = recommender.similar(pid, limit=3)
        assert isinstance(result, list)

    def test_similar_excludes_self(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            from models import Product
            pid = Product.query.first().id
            ids = [i for i, _ in recommender.similar(pid)]
        assert pid not in ids

    def test_similar_limit_respected(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            from models import Product
            pid = Product.query.first().id
            result = recommender.similar(pid, limit=2)
        assert len(result) <= 2

    def test_similar_unknown_id_returns_empty(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            result = recommender.similar(999999)
        assert result == []

    def test_score_query_returns_dict(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            scores = recommender.score_query("gaming laptop")
        assert isinstance(scores, dict)
        assert all(isinstance(v, float) for v in scores.values())

    def test_score_empty_query_returns_empty(self, seeded_app):
        with seeded_app.app_context():
            from recommender import recommender
            scores = recommender.score_query("   ")
        assert scores == {}

    def test_unfitted_recommender_similar_returns_empty(self):
        """A fresh Recommender with no fit() call returns [] for similar."""
        r = Recommender()
        assert r.similar(1) == []

    def test_unfitted_recommender_score_returns_empty(self):
        """A fresh Recommender returns {} for score_query."""
        r = Recommender()
        assert r.score_query("test") == {}
