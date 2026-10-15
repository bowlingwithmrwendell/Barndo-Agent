"""Public-only directory reads using Supabase's restricted publishable/anon key."""

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter(tags=["directory"])
PUBLIC_FIELDS = (
    "id,name,scope,areas,coverage_note,phone,source,last_web_checked,work_types,"
    "company_confirmed_at,availability,availability_confirmed_at"
)


def public_companies() -> list[dict]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(503, "Builder directory is not configured yet")
    headers = {"apikey": settings.supabase_publishable_key}
    # Legacy anon JWTs also need Authorization. New publishable keys use apikey only.
    if settings.supabase_publishable_key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + settings.supabase_publishable_key
    try:
        response = httpx.get(
            settings.supabase_url.rstrip("/") + "/rest/v1/builder_companies",
            headers=headers,
            params={"select": PUBLIC_FIELDS, "published": "eq.true", "order": "name.asc", "limit": "500"},
            timeout=10,
        )
        response.raise_for_status()
        records = response.json()
        if not isinstance(records, list):
            raise ValueError("Unexpected directory response")
        # Explicit whitelist even if upstream unexpectedly returns extra fields.
        fields = PUBLIC_FIELDS.split(",")
        return [{key: record.get(key) for key in fields} for record in records]
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(503, "Builder directory is temporarily unavailable") from None


@router.get("/public/builders")
def builders():
    return {"companies": public_companies()}
