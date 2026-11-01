"""
tests/test_api.py – Tests for the product listing, detail, and similar endpoints.

Covers:
  - /api/meta         (categories, brands, price range)
  - /api/products     (list, filters, sort, pagination, invalid params)
  - /api/products/<id>  (detail, 404)
  - /api/products/<id>/similar (similarity, 404)
"""
import json


# ---------------------------------------------------------------------------
# /api/meta
# ---------------------------------------------------------------------------
class TestMeta:
    def test_returns_categories_and_brands(self, client):
        res = client.get("/api/meta")
        assert res.status_code == 200
        data = res.get_json()
        assert "categories" in data
        assert "brands" in data
        assert "price_min" in data
        assert "price_max" in data

    def test_categories_are_sorted(self, client):
        data = client.get("/api/meta").get_json()
        cats = data["categories"]
        assert cats == sorted(cats)

    def test_price_range_is_numeric(self, client):
        data = client.get("/api/meta").get_json()
        assert isinstance(data["price_min"], int)
        assert isinstance(data["price_max"], int)
        assert data["price_min"] <= data["price_max"]

    def test_empty_catalog_returns_nulls(self, empty_client):
        res = empty_client.get("/api/meta")
        assert res.status_code == 200
        data = res.get_json()
        assert data["price_min"] is None
        assert data["price_max"] is None
        assert data["categories"] == []


# ---------------------------------------------------------------------------
# /api/products – listing and filters
# ---------------------------------------------------------------------------
class TestProducts:
    def test_returns_products(self, client):
        res = client.get("/api/products")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert "total" in data
        assert data["total"] > 0

    def test_filter_by_category(self, client):
        res = client.get("/api/products?category=Laptops")
        data = res.get_json()
        for item in data["items"]:
            assert item["category"] == "Laptops"

    def test_filter_by_brand(self, client):
        res = client.get("/api/products?brand=Zenvo")
        data = res.get_json()
        for item in data["items"]:
            assert item["brand"] == "Zenvo"

    def test_filter_min_price(self, client):
        res = client.get("/api/products?min_price=20000")
        data = res.get_json()
        for item in data["items"]:
            assert item["price"] >= 20000

    def test_filter_max_price(self, client):
        res = client.get("/api/products?max_price=15000")
        data = res.get_json()
        for item in data["items"]:
            assert item["price"] <= 15000

    def test_filter_min_rating(self, client):
        res = client.get("/api/products?min_rating=4.3")
        data = res.get_json()
        for item in data["items"]:
            assert item["rating"] >= 4.3

    def test_text_search_returns_relevant(self, client):
        res = client.get("/api/products?q=gaming")
        data = res.get_json()
        assert data["total"] > 0
        names = [i["name"] for i in data["items"]]
        assert any("Gamer" in n or "gaming" in n.lower() for n in names)

    def test_no_match_returns_empty(self, client):
        res = client.get("/api/products?category=Laptops&min_price=999999")
        data = res.get_json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_sort_price_asc(self, client):
        res = client.get("/api/products?sort=price_asc")
        items = res.get_json()["items"]
        prices = [i["price"] for i in items]
        assert prices == sorted(prices)

    def test_sort_price_desc(self, client):
        res = client.get("/api/products?sort=price_desc")
        items = res.get_json()["items"]
        prices = [i["price"] for i in items]
        assert prices == sorted(prices, reverse=True)

    def test_sort_rating_desc(self, client):
        res = client.get("/api/products?sort=rating_desc")
        items = res.get_json()["items"]
        ratings = [i["rating"] for i in items]
        assert ratings == sorted(ratings, reverse=True)

    def test_invalid_sort_falls_back_to_relevance(self, client):
        res = client.get("/api/products?sort=INVALID")
        assert res.status_code == 200  # no error, just uses default

    def test_pagination_page_1(self, client):
        res = client.get("/api/products?page=1")
        data = res.get_json()
        assert data["page"] == 1
        assert len(data["items"]) <= data["page_size"]

    def test_pagination_page_2_different_items(self, client):
        """With PAGE_SIZE=5 and 5 products, page 2 should be empty."""
        p1 = client.get("/api/products?page=1").get_json()["items"]
        p2 = client.get("/api/products?page=2").get_json()["items"]
        # Page 2 items should not overlap with page 1 (or page 2 is empty)
        ids1 = {i["id"] for i in p1}
        ids2 = {i["id"] for i in p2}
        assert ids1.isdisjoint(ids2) or len(ids2) == 0

    def test_invalid_page_defaults_to_1(self, client):
        res = client.get("/api/products?page=abc")
        assert res.status_code == 200
        assert res.get_json()["page"] == 1

    def test_invalid_price_ignored(self, client):
        res = client.get("/api/products?min_price=notanumber")
        assert res.status_code == 200

    def test_response_fields(self, client):
        item = client.get("/api/products").get_json()["items"][0]
        for field in ("id", "name", "brand", "category", "price", "rating", "in_stock", "icon"):
            assert field in item, f"Missing field: {field}"

    def test_empty_catalog(self, empty_client):
        data = empty_client.get("/api/products").get_json()
        assert data["total"] == 0
        assert data["items"] == []


# ---------------------------------------------------------------------------
# /api/products/<id> – product detail
# ---------------------------------------------------------------------------
class TestProductDetail:
    def test_returns_product(self, client):
        # Get a valid product ID from the listing first
        items = client.get("/api/products").get_json()["items"]
        pid = items[0]["id"]
        res = client.get(f"/api/products/{pid}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["id"] == pid
        assert "name" in data
        assert "price" in data

    def test_404_returns_json(self, client):
        res = client.get("/api/products/999999")
        assert res.status_code == 404
        data = res.get_json()
        assert "error" in data

    def test_nonint_id_returns_404(self, client):
        res = client.get("/api/products/abc")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# /api/products/<id>/similar
# ---------------------------------------------------------------------------
class TestSimilar:
    def test_returns_similar(self, client):
        items = client.get("/api/products").get_json()["items"]
        pid = items[0]["id"]
        res = client.get(f"/api/products/{pid}/similar")
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        # Similar items should NOT include the product itself
        ids = [i["id"] for i in data["items"]]
        assert pid not in ids

    def test_404_unknown_product(self, client):
        res = client.get("/api/products/999999/similar")
        assert res.status_code == 404
        assert "error" in res.get_json()

    def test_similar_has_similarity_score(self, client):
        items = client.get("/api/products").get_json()["items"]
        pid = items[0]["id"]
        sim_items = client.get(f"/api/products/{pid}/similar").get_json()["items"]
        for s in sim_items:
            assert "similarity" in s
            assert 0 <= s["similarity"] <= 1
