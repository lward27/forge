import re
import uuid

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from forge_platform.database import get_session
from forge_platform.services import auth_service

# Endpoints that don't require auth
PUBLIC_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}

# Endpoints that require admin role
ADMIN_ONLY_PATTERNS = [
    ("POST", "/tenants"),
    ("DELETE", re.compile(r"^/tenants/[^/]+$")),
    ("POST", "/auth/keys"),
    ("DELETE", re.compile(r"^/auth/keys/")),
]

# Pattern to extract tenant_id from path
TENANT_PATH_PATTERN = re.compile(r"^/tenants/([0-9a-f-]{36})")


def get_api_key(
    request: Request,
    session: Session = Depends(get_session),
):
    """FastAPI dependency that validates the API key and enforces access rules."""
    # Skip auth for public endpoints
    if request.url.path in PUBLIC_PATHS:
        return None

    # Extract key from header
    key = request.headers.get("X-API-Key")
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    # Validate key
    api_key = auth_service.validate_key(session, key)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Admin has full access
    if api_key.role == "admin":
        request.state.auth = api_key
        return api_key

    # Tenant role: check endpoint access
    method = request.method
    path = request.url.path

    # Check admin-only endpoints
    for admin_method, admin_path in ADMIN_ONLY_PATTERNS:
        if method == admin_method:
            if isinstance(admin_path, str) and path == admin_path:
                raise HTTPException(status_code=403, detail="Admin access required")
            if isinstance(admin_path, re.Pattern) and admin_path.match(path):
                raise HTTPException(status_code=403, detail="Admin access required")

    # GET /tenants (list all) is admin-only
    if method == "GET" and path == "/tenants":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Check tenant scoping for paths with tenant_id
    match = TENANT_PATH_PATTERN.match(path)
    if match:
        path_tenant_id = uuid.UUID(match.group(1))
        if api_key.tenant_id != path_tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")

    request.state.auth = api_key
    return api_key
