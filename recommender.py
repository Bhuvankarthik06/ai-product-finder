"""
recommender.py – Content-based recommendations using TF-IDF vectors and cosine similarity.

The Recommender class is instantiated once as a module-level singleton.
The app calls `recommender.fit()` at startup and after any bulk data import.
All public methods are thread-safe via a lock.
"""
import logging
import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from models import Product

logger = logging.getLogger(__name__)


class Recommender:
    """Builds a TF-IDF matrix from all products and answers similarity queries."""

    def __init__(self):
        self._lock       = threading.Lock()
        self._vectorizer = None
        self._matrix     = None
        self._ids: list  = []
        self._index: dict = {}

    def fit(self):
        """(Re)build the TF-IDF matrix from the products table.

        Safe to call multiple times – replaces the existing matrix atomically.
        Does nothing if the products table is empty.
        """
        products = Product.query.order_by(Product.id).all()
        if not products:
            logger.info("Recommender: no products found, skipping fit.")
            return

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        matrix = vectorizer.fit_transform([p.text_blob() for p in products])

        with self._lock:
            self._vectorizer = vectorizer
            self._matrix     = matrix
            self._ids        = [p.id for p in products]
            self._index      = {pid: i for i, pid in enumerate(self._ids)}

        logger.info("Recommender: indexed %d products.", len(products))

    def similar(self, product_id: int, limit: int = 4) -> list[tuple[int, float]]:
        """Return [(product_id, cosine_score), …] for the most similar products.

        Excludes the product itself.  Returns an empty list if the product
        is not in the index or the index has not been built yet.
        """
        with self._lock:
            if self._matrix is None:
                return []
            if product_id not in self._index:
                return []
            row    = self._index[product_id]
            scores = linear_kernel(self._matrix[row], self._matrix).ravel()
            ranked = scores.argsort()[::-1]
            return [
                (self._ids[i], float(scores[i]))
                for i in ranked
                if i != row and scores[i] > 0
            ][:limit]

    def score_query(self, text: str) -> dict[int, float]:
        """Cosine similarity of free text against every product.

        Returns {product_id: score}.  Products with score 0 are omitted.
        """
        with self._lock:
            if self._vectorizer is None or not text.strip():
                return {}
            vec    = self._vectorizer.transform([text])
            scores = linear_kernel(vec, self._matrix).ravel()
            return {self._ids[i]: float(s) for i, s in enumerate(scores) if s > 0}


# Module-level singleton used by app.py and search.py.
recommender = Recommender()
