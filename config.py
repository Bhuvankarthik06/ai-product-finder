"""
config.py – Application configuration loaded from environment variables.
All secrets must come from the environment (or a .env file). Never hardcode them.
"""
import os
import secrets

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Graceful fallback if python-dotenv is not installed
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Flask secret key – used for session signing.  Generate a real one with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    # Database: defaults to a local SQLite file so the app runs without MySQL.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "products.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Pagination
    PAGE_SIZE = int(os.getenv("PAGE_SIZE", "12"))

    # LLM assistant (optional – falls back to rule-based parser when absent)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")


class TestConfig(Config):
    """Isolated in-memory database for automated tests.  Never touches the dev DB."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Disable LLM in tests so we never make real API calls.
    ANTHROPIC_API_KEY = ""
    PAGE_SIZE = 5
