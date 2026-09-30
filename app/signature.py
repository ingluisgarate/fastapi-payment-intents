from __future__ import annotations

import hashlib
import hmac


def sign(raw_body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def matches(raw_body: bytes, header: str, secret: str) -> bool:
    return hmac.compare_digest(sign(raw_body, secret), header.strip())
