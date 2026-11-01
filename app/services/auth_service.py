"""
Authentication service handling secure password hashing and session management.
"""
import bcrypt
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from app.config import settings

# Default bcrypt hash for 'admin123' used if no ADMIN_PASSWORD_HASH is set in .env
DEFAULT_ADMIN_HASH = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with a random salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_admin_password_hash() -> str:
    """Returns the configured admin password hash or defaults to 'admin123' hash."""
    return settings.ADMIN_PASSWORD_HASH if settings.ADMIN_PASSWORD_HASH else DEFAULT_ADMIN_HASH


def is_authenticated(request: Request) -> bool:
    """Returns True if the current session has an authenticated admin."""
    return bool(request.session.get("admin_logged_in"))


def require_admin(request: Request) -> None:
    """
    FastAPI dependency that enforces admin authentication.
    Redirects unauthenticated users to /login.
    """
    if not is_authenticated(request):
        # HTTP 303 See Other is the standard status for redirecting after GET/POST
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
