"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
import pytest
from starlette.testclient import TestClient

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import Settings, get_settings
from src.server.app import create_app
from src.tools.crm_tool import LocalJSONCRMAdapter


@pytest.fixture
def temp_crm_db():
    """Create isolated temporary JSON database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = tf.name

    adapter = LocalJSONCRMAdapter(db_path=temp_path)
    yield adapter

    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    """FastAPI TestClient fixture."""
    app = create_app()
    with TestClient(app) as client:
        yield client
