"""
app.py – Flask application factory and REST API routes.

All API responses are JSON.  Error handlers ensure no HTML slips through.
"""
import logging
import logging.config

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config
from llm_assistant import extract_filters
from models import Product, db
from recommender import recommender
from search import search_products, VALID_SORTS

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        try:
            recommender.fit()
        except Exception as exc:
            logger.warning("Could not build recommendation index at startup: %s", exc)

    # ------------------------------------------------------------------
    # Helper: catalog metadata (categories, brands, price range)
    # ------------------------------------------------------------------
    def _catalog_values():
        categories = [
            c for (c,) in db.session.query(Product.category).distinct().order_by(Product.category)
        ]
        brands = [
            b for (b,) in db.session.query(Product.brand).distinct().order_by(Product.brand)
        ]
        return categories, brands

    def _safe_num(name, cast):
        """Parse a query-string parameter to a number; return None on failure."""
        value = request.args.get(name, "").strip()
        try:
            return cast(value) if value else None
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Global error handlers – always return JSON, never HTML
    # ------------------------------------------------------------------
    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify(error=exc.description), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        logger.exception("Unhandled server error")
        return jsonify(error="An unexpected server error occurred."), 500

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/meta")
    def meta():
        """Return catalog metadata used to populate filter dropdowns."""
        categories, brands = _catalog_values()
        row = db.session.query(
            db.func.min(Product.price), db.func.max(Product.price)
        ).one()
        price_min, price_max = row if row else (None, None)
        return jsonify(
            categories=categories,
            brands=brands,
            price_min=price_min,
            price_max=price_max,
        )

    @app.get("/api/products")
    def products():
        """Search and filter products.

        Query parameters:
            q           – free-text search
            category    – exact category name
            brand       – exact brand name
            min_price   – minimum price (INR, integer)
            max_price   – maximum price (INR, integer)
            min_rating  – minimum rating (float 1-5)
            sort        – relevance | price_asc | price_desc | rating_desc
            page        – page number (default 1)
        """
        sort = request.args.get("sort", "relevance")
        if sort not in VALID_SORTS:
            sort = "relevance"

        in_stock_raw = request.args.get("in_stock", "").lower()
        in_stock = True if in_stock_raw in ("1", "true") else None

        filters = {
            "q":          request.args.get("q", "").strip()[:200],
            "category":   request.args.get("category") or None,
            "brand":      request.args.get("brand") or None,
            "min_price":  _safe_num("min_price", int),
            "max_price":  _safe_num("max_price", int),
            "min_rating": _safe_num("min_rating", float),
            "in_stock":   in_stock,
            "sort":       sort,
        }
        page = max(_safe_num("page", int) or 1, 1)
        items, total, relaxed = search_products(filters, page, app.config["PAGE_SIZE"])
        return jsonify(
            items=items,
            total=total,
            page=page,
            page_size=app.config["PAGE_SIZE"],
            relaxed=relaxed,
        )

    @app.get("/api/products/<int:product_id>")
    def product_detail(product_id):
        """Return full details for a single product."""
        product = db.session.get(Product, product_id)
        if product is None:
            return jsonify(error="Product not found."), 404
        return jsonify(product.to_dict())

    @app.get("/api/products/<int:product_id>/similar")
    def similar(product_id):
        """Return up to 4 similar products using TF-IDF cosine similarity."""
        if db.session.get(Product, product_id) is None:
            return jsonify(error="Product not found."), 404

        pairs = recommender.similar(product_id, limit=4)
        ids   = [i for i, _ in pairs]
        by_id = {
            p.id: p
            for p in Product.query.filter(Product.id.in_(ids)).all()
        }
        return jsonify(items=[
            {**by_id[i].to_dict(), "similarity": round(score, 3)}
            for i, score in pairs
            if i in by_id
        ])

    @app.post("/api/assistant")
    def assistant():
        """Parse a natural-language query into filters and return matching products.

        Body (JSON): { "query": "a phone under 20k with a good camera" }

        The LLM (or fallback parser) returns *only filters*, which are then
        passed to the same search_products() function used by /api/products.
        The AI can never invent products or generate SQL.
        """
        data  = request.get_json(silent=True) or {}
        query = str(data.get("query", "")).strip()
        if not query:
            return jsonify(error="Please type what you are looking for."), 400
        if len(query) > 500:
            return jsonify(error="Query is too long (max 500 characters)."), 400

        categories, brands = _catalog_values()
        filters, source = extract_filters(
            query, categories, brands,
            api_key=app.config["ANTHROPIC_API_KEY"],
            model=app.config["LLM_MODEL"],
        )
        items, total, relaxed = search_products(filters, 1, app.config["PAGE_SIZE"])
        return jsonify(
            filters=filters,
            source=source,
            items=items,
            total=total,
            relaxed=relaxed,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
