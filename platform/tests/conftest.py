"""Shared test fixtures — mock session and auth for all tests."""
from unittest.mock import MagicMock

from sqlmodel import Session

from forge_platform.app import app
from forge_platform.database import get_session
from forge_platform.middleware.auth import get_api_key


def _mock_session():
    session = MagicMock(spec=Session)
    yield session


def _mock_admin_key():
    key = MagicMock()
    key.role = "admin"
    key.tenant_id = None
    key.is_active = True
    return key


# Override globally for all tests
app.dependency_overrides[get_session] = _mock_session
app.dependency_overrides[get_api_key] = _mock_admin_key
