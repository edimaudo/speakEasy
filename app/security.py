from __future__ import annotations

import hashlib
import hmac
import uuid

COOKIE_NAME = "speakeasy_guest"


def sign_visitor(visitor_id: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), visitor_id.encode(), hashlib.sha256).hexdigest()
    return f"{visitor_id}.{signature}"


def verify_visitor(cookie_value: str | None, secret: str) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    visitor_id, signature = cookie_value.rsplit(".", 1)
    try:
        uuid.UUID(visitor_id)
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), visitor_id.encode(), hashlib.sha256).hexdigest()
    return visitor_id if hmac.compare_digest(signature, expected) else None


def new_visitor_id() -> str:
    return str(uuid.uuid4())
