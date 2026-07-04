"""
Lightweight RBAC helpers for the UBA ITD API.

DEMO CONTROL — NOT PRODUCTION AUTH
==================================
Role is read from the ``X-User-Role`` request header. This is trivially
**spoofable** by any client (a caller can simply send ``X-User-Role: Admin``)
and exists only to demonstrate role-gated endpoints in this prototype. In a
real deployment this MUST be replaced by an authenticated identity — e.g. a
signed JWT / OIDC token validated server-side, or an SSO-provided identity —
from which the role is derived. Do not rely on this for any real access
control decision.

These helpers live in their own module (rather than in ``main.py``) so routers
can depend on ``require_role`` without importing ``main`` and creating a
circular import.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException

# Roles recognised by the demo RBAC layer.
VALID_ROLES = {"Admin", "Analyst", "Viewer"}


def get_current_role(x_user_role: Optional[str] = Header(None)) -> str:
    """
    Extract the caller's role from the ``X-User-Role`` header.

    DEMO ONLY: this header is client-supplied and therefore spoofable. Returns
    ``"Viewer"`` (least privilege) if the header is missing or unrecognised.
    """
    if x_user_role and x_user_role in VALID_ROLES:
        return x_user_role
    return "Viewer"


def require_role(*allowed_roles: str):
    """
    Factory returning a FastAPI dependency that enforces role membership.

    DEMO ONLY — see module docstring; the underlying role signal is spoofable.

    Usage in a router:
        @router.post("/secret", dependencies=[Depends(require_role("Admin"))])
    """
    def _check(role: str = Depends(get_current_role)):
        if role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' is not permitted. Required: {', '.join(allowed_roles)}",
            )
        return role

    return _check
