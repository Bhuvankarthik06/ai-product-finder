"""
tests/conftest.py – Shared pytest fixtures.

Uses an in-memory SQLite database so tests never touch the development database.
The TestConfig class (defined in config.py) sets SQLALCHEMY_DATABASE_URI to
sqlite:///:memory: and disables the LLM API key.
"""
import pytest

from app import create_app
from config import TestConfig
from models import Product, db as _db


# ---------------------------------------------------------------------------
# Sample product data used across tests
# ---------------------------------------------------------------------------
SAMPLE_PRODUCTS = [
    dict(name="Zenvo Pro Max", brand="Zenvo", category="Smartphones", price=34999, rating=4.5,
         description="Flagship phone with great camera and 5G.", specs="108MP, 5G, 6.7-inch", in_stock=True),
    dict(name="Arcwave Lite", brand="Arcwave", category="Smartphones", price=11999, rating=3.8,
         description="Budget phone with long battery.", specs="50MP, 5000mAh, 6.5-inch", in_stock=True),
    dict(name="Vertex Gamer X", brand="Vertex", category="Laptops", price=79999, rating=4.6,
         description="Gaming laptop with RTX GPU.", specs="RTX, 144Hz, 16GB RAM", in_stock=True),
    dict(name="Sonara Buds ANC", brand="Sonara", category="Headphones", price=5999, rating=4.3,
         description="Noise-cancelling earbuds.", specs="ANC, 30hr battery, IPX4", in_stock=False),
    dict(name="Chronix Active 2", brand="Chronix", category="Smartwatches", price=9999, rating=4.1,
         description="GPS smartwatch with AMOLED.", specs="GPS, 7-day battery, heart rate", in_stock=True),
]


@pytest.fixture(scope="session")
def app():
    """Create an application using the test configuration.
    This fixture is shared for the whole test session.
    """
    application = create_app(TestConfig)
    return application


@pytest.fixture(scope="session")
def seeded_app(app):
    """Return the app with sample products already in the database."""
    with app.app_context():
        _db.create_all()
        if Product.query.count() == 0:
            for data in SAMPLE_PRODUCTS:
                _db.session.add(Product(**data))
            _db.session.commit()

        # Build the recommendation index so /similar works.
        from recommender import recommender
        recommender.fit()

    return app


@pytest.fixture()
def client(seeded_app):
    """Flask test client – each test gets a fresh client against the seeded DB."""
    return seeded_app.test_client()


@pytest.fixture()
def empty_client(app):
    """A test client with NO products – tests empty-catalog behaviour."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
    return app.test_client()
