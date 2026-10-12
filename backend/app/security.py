"""Role-based access control via API keys (header: X-API-Key).

Roles, least to most privilege:
  viewer  - read projects & budget summaries; client PII is redacted
  field   - viewer + log costs + submit feedback (job-site crews)
  manager - field + create/edit projects, budgets, client info; sees client PII
  admin   - everything, including the feedback log and storage provisioning
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

ROLE_LEVELS = {"viewer": 0, "field": 1, "manager": 2, "admin": 3}

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    role: str

    def at_least(self, role: str) -> bool:
        return ROLE_LEVELS[self.role] >= ROLE_LEVELS[role]


def get_principal(api_key: str | None = Security(_api_key_header)) -> Principal:
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    for known, role in get_settings().api_keys.items():
        if hmac.compare_digest(known.encode(), api_key.encode()):
            return Principal(role=role)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")


def require(role: str):
    """Dependency factory: require at least `role`."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.at_least(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{role}' or higher")
        return principal

    return _dep
