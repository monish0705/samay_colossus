import os
import pytest

os.environ["SAMAY_ENVIRONMENT"] = "test"

try:
    from app.config import get_settings
    get_settings.cache_clear()
except ImportError:
    pass

@pytest.fixture(autouse=True)
def default_test_environment(monkeypatch):
    monkeypatch.setenv("SAMAY_ENVIRONMENT", "test")
    try:
        from app.config import get_settings
        get_settings.cache_clear()
    except ImportError:
        pass
