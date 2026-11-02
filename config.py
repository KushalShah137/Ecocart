"""
EcoCart configuration. Every secret / connection detail comes from environment
variables (loaded from .env by python-dotenv). Nothing sensitive is hard-coded.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)   # set true behind HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_HOURS", "12")))
    MAX_CONTENT_LENGTH = 1024 * 1024

    # Oracle (python-oracledb thin mode: no Instant Client needed)
    ORACLE_USER = os.getenv("ECOCART_DB_USER", "ecocart")
    ORACLE_PASSWORD = os.getenv("ECOCART_DB_PASSWORD", "")
    ORACLE_DSN = os.getenv("ECOCART_DB_DSN", "localhost:1521/XEPDB1")
    ORACLE_POOL_MIN = int(os.getenv("ECOCART_DB_POOL_MIN", "1"))
    ORACLE_POOL_MAX = int(os.getenv("ECOCART_DB_POOL_MAX", "4"))

    # Business rules
    ECO_SWAP_PRICE_TOLERANCE = float(os.getenv("ECO_SWAP_PRICE_TOLERANCE", "0.20"))
    ECO_SWAP_MAX_RESULTS = int(os.getenv("ECO_SWAP_MAX_RESULTS", "4"))
    SHOP_PAGE_SIZE = int(os.getenv("SHOP_PAGE_SIZE", "12"))
    FREE_SHIPPING_THRESHOLD = 999
    SHIPPING_FEE = 49


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False
