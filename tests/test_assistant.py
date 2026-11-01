"""
tests/test_assistant.py – Tests for the /api/assistant endpoint and llm_assistant module.

Covers:
  - Missing/empty query returns 400
  - Query too long returns 400
  - Rule-based parser extracts correct filters (no API key)
  - LLM path is used when a mock API key is present
  - Invalid LLM JSON falls back to rule-based parser
  - Response always includes filters, source, items, total
"""
import json
from unittest.mock import MagicMock, patch

from llm_assistant import (
    CATEGORY_HINTS,
    rule_based_filters,
    validate_filters,
    extract_filters,
)


# ---------------------------------------------------------------------------
# /api/assistant endpoint
# ---------------------------------------------------------------------------
class TestAssistantEndpoint:
    def test_missing_query_returns_400(self, client):
        res = client.post("/api/assistant",
                          json={},
                          content_type="application/json")
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_empty_query_returns_400(self, client):
        res = client.post("/api/assistant",
                          json={"query": "   "},
                          content_type="application/json")
        assert res.status_code == 400

    def test_too_long_query_returns_400(self, client):
        res = client.post("/api/assistant",
                          json={"query": "x" * 501},
                          content_type="application/json")
        assert res.status_code == 400

    def test_valid_query_returns_200(self, client):
        res = client.post("/api/assistant",
                          json={"query": "phone under 20000"},
                          content_type="application/json")
        assert res.status_code == 200
        data = res.get_json()
        assert "filters" in data
        assert "source" in data
        assert "items" in data
        assert "total" in data

    def test_source_is_rules_without_api_key(self, client):
        """Without an API key the source must be 'rules'."""
        res = client.post("/api/assistant",
                          json={"query": "gaming laptop"},
                          content_type="application/json")
        data = res.get_json()
        assert data["source"] == "rules"

    def test_filters_in_response(self, client):
        res = client.post("/api/assistant",
                          json={"query": "smartwatch under 15000"},
                          content_type="application/json")
        f = res.get_json()["filters"]
        assert isinstance(f, dict)
        assert "category" in f
        assert "brand" in f
        assert "min_price" in f
        assert "max_price" in f
        assert "keywords" in f

    def test_no_json_body_returns_400(self, client):
        res = client.post("/api/assistant", data="not json",
                          content_type="text/plain")
        assert res.status_code == 400

    def test_relaxed_flag_present(self, client):
        res = client.post("/api/assistant",
                          json={"query": "phone under 20000"},
                          content_type="application/json")
        data = res.get_json()
        assert "relaxed" in data
        assert isinstance(data["relaxed"], bool)


# ---------------------------------------------------------------------------
# rule_based_filters unit tests
# ---------------------------------------------------------------------------
class TestRuleBasedFilters:
    CATEGORIES = list(CATEGORY_HINTS.keys())
    BRANDS = ["Zenvo", "Arcwave", "Vertex", "Sonara"]

    def test_detects_smartphone_category(self):
        f = rule_based_filters("I want a good phone", self.CATEGORIES, self.BRANDS)
        assert f["category"] == "Smartphones"

    def test_detects_laptop_category(self):
        f = rule_based_filters("need a laptop for work", self.CATEGORIES, self.BRANDS)
        assert f["category"] == "Laptops"

    def test_detects_brand(self):
        f = rule_based_filters("Zenvo phone", self.CATEGORIES, self.BRANDS)
        assert f["brand"] == "Zenvo"

    def test_parses_max_price_with_k(self):
        f = rule_based_filters("phone under 20k", self.CATEGORIES, self.BRANDS)
        assert f["max_price"] == 20000

    def test_parses_max_price_plain(self):
        f = rule_based_filters("earbuds below 8000", self.CATEGORIES, self.BRANDS)
        assert f["max_price"] == 8000

    def test_parses_lakh(self):
        f = rule_based_filters("camera under 1.5 lakh", self.CATEGORIES, self.BRANDS)
        assert f["max_price"] == 150000

    def test_parses_between_price(self):
        f = rule_based_filters("laptop between 50000 and 80000", self.CATEGORIES, self.BRANDS)
        assert f["min_price"] == 50000
        assert f["max_price"] == 80000

    def test_sort_cheapest(self):
        f = rule_based_filters("cheapest smartphone", self.CATEGORIES, self.BRANDS)
        assert f["sort"] == "price_asc"

    def test_sort_top_rated(self):
        f = rule_based_filters("top rated earbuds", self.CATEGORIES, self.BRANDS)
        assert f["sort"] == "rating_desc"

    def test_extracts_keywords(self):
        f = rule_based_filters("phone with good camera and long battery", self.CATEGORIES, self.BRANDS)
        assert len(f["keywords"]) > 0
        assert "camera" in f["keywords"] or "battery" in f["keywords"]

    def test_keywords_capped_at_6(self):
        f = rule_based_filters(
            "phone camera zoom video night portrait stabilisation selfie",
            self.CATEGORIES, self.BRANDS
        )
        assert len(f["keywords"]) <= 6

    def test_no_match_returns_all_none(self):
        f = rule_based_filters("something really vague", [], [])
        assert f["category"] is None
        assert f["brand"] is None


# ---------------------------------------------------------------------------
# validate_filters unit tests
# ---------------------------------------------------------------------------
class TestValidateFilters:
    CATS   = ["Smartphones", "Laptops"]
    BRANDS = ["Zenvo", "Arcwave"]

    def test_valid_input_passes_through(self):
        raw = {"category": "Smartphones", "brand": "Zenvo",
               "min_price": 5000, "max_price": 30000,
               "min_rating": 4.0, "keywords": ["camera"], "sort": "price_asc"}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["category"] == "Smartphones"
        assert f["brand"] == "Zenvo"
        assert f["min_price"] == 5000
        assert f["max_price"] == 30000

    def test_unknown_category_becomes_none(self):
        raw = {"category": "InventedCategory"}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["category"] is None

    def test_negative_min_price_becomes_none(self):
        raw = {"min_price": -500}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["min_price"] is None

    def test_swaps_inverted_price_range(self):
        raw = {"min_price": 50000, "max_price": 10000}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["min_price"] < f["max_price"]

    def test_rating_out_of_range_becomes_none(self):
        raw = {"min_rating": 6.0}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["min_rating"] is None

    def test_invalid_sort_defaults_to_relevance(self):
        raw = {"sort": "hacked"}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["sort"] == "relevance"

    def test_keywords_are_sanitised(self):
        raw = {"keywords": ["<script>alert(1)</script>", "camera"]}
        f = validate_filters(raw, self.CATS, self.BRANDS)
        for k in f["keywords"]:
            assert "<" not in k and ">" not in k

    def test_non_dict_input_returns_none(self):
        assert validate_filters("not a dict", self.CATS, self.BRANDS) is None

    def test_case_insensitive_category_match(self):
        raw = {"category": "smartphones"}   # lowercase
        f = validate_filters(raw, self.CATS, self.BRANDS)
        assert f["category"] == "Smartphones"  # corrected to proper case


# ---------------------------------------------------------------------------
# extract_filters – LLM path mocked
# ---------------------------------------------------------------------------
class TestExtractFilters:
    CATS   = ["Smartphones", "Laptops"]
    BRANDS = ["Zenvo"]

    def test_uses_rules_without_api_key(self):
        _, source = extract_filters("phone under 20k", self.CATS, self.BRANDS, api_key="")
        assert source == "rules"

    def test_llm_path_used_with_mock_key(self):
        """Mock the Anthropic client so we don't make a real API call."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = json.dumps({
            "category": "Smartphones", "brand": None,
            "min_price": None, "max_price": 20000,
            "min_rating": None, "keywords": ["camera"], "sort": "relevance",
        })
        mock_response.content = [mock_block]

        with patch("llm_assistant.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            filters, source = extract_filters(
                "phone under 20k with camera",
                self.CATS, self.BRANDS,
                api_key="fake-key", model="claude-test",
            )

        assert source == "llm"
        assert filters["category"] == "Smartphones"
        assert filters["max_price"] == 20000

    def test_bad_llm_json_falls_back_to_rules(self):
        """If LLM returns invalid JSON, fall back to rule-based parser."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "not valid json!!!"
        mock_response.content = [mock_block]

        with patch("llm_assistant.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            _, source = extract_filters(
                "phone under 20k",
                self.CATS, self.BRANDS,
                api_key="fake-key", model="claude-test",
            )

        assert source == "rules"

    def test_llm_timeout_falls_back_to_rules(self):
        """If LLM raises an exception, fall back gracefully."""
        with patch("llm_assistant.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = TimeoutError("timeout")

            _, source = extract_filters(
                "phone under 20k",
                self.CATS, self.BRANDS,
                api_key="fake-key", model="claude-test",
            )

        assert source == "rules"
