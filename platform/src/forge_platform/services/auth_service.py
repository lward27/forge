import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.api_key import ApiKey

logger = logging.getLogger(__name__)

KEY_PREFIX_LITERAL = "forge_"
KEY_RANDOM_LENGTH = 48


def generate_key() -> str:
    """Generate a new API key with forge_ prefix."""
    random_part = secrets.token_urlsafe(KEY_RANDOM_LENGTH)
    return f"{KEY_PREFIX_LITERAL}{random_part}"


def hash_key(key: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix(key: str) -> str:
    """First 8 characters of the key for identification."""
    return key[:8]


def create_api_key(
    session: Session,
    name: str,
    role: str,
    tenant_id: uuid.UUID | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (model, plaintext_key)."""
    plaintext = generate_key()

    api_key = ApiKey(
        key_hash=hash_key(plaintext),
        key_prefix=key_prefix(plaintext),
        tenant_id=tenant_id,
        role=role,
        name=name,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return api_key, plaintext


def validate_key(session: Session, plaintext: str) -> ApiKey | None:
    """Validate an API key. Returns the ApiKey if valid, None otherwise."""
    h = hash_key(plaintext)
    statement = select(ApiKey).where(ApiKey.key_hash == h)
    api_key = session.exec(statement).first()

    if api_key is None or not api_key.is_active:
        return None

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    session.add(api_key)
    session.commit()

    return api_key


def list_keys(
    session: Session, tenant_id: uuid.UUID | None = None
) -> list[ApiKey]:
    """List API keys. If tenant_id provided, filter to that tenant's keys."""
    statement = select(ApiKey).where(ApiKey.is_active == True)  # noqa: E712
    if tenant_id is not None:
        statement = statement.where(ApiKey.tenant_id == tenant_id)
    return list(session.exec(statement).all())


def revoke_key(session: Session, key_id: uuid.UUID) -> ApiKey | None:
    """Revoke an API key by setting is_active=False."""
    api_key = session.get(ApiKey, key_id)
    if api_key is None:
        return None

    api_key.is_active = False
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def has_any_keys(session: Session) -> bool:
    """Check if any API keys exist (for bootstrap detection)."""
    statement = select(ApiKey).limit(1)
    return session.exec(statement).first() is not None


def bootstrap_admin_key(session: Session) -> str | None:
    """Create the initial admin key if none exist. Returns plaintext or None."""
    if has_any_keys(session):
        return None

    api_key, plaintext = create_api_key(
        session, name="Initial Admin Key", role="admin"
    )
    logger.warning(
        "[FORGE] Initial admin API key created: %s", plaintext
    )
    return plaintext
