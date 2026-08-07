"""HTTP client for the internal portal API.

In the portfolio repo this points at the FastAPI mock server in
partner-onboarding-agent/mock_portal/. Swap PORTAL_BASE_URL for production.
"""

from __future__ import annotations

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from b2b_toolkit.models import PortalAccount
from b2b_toolkit.settings import Settings

log = structlog.get_logger()


class PortalClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        headers = {}
        if settings.portal_api_key:
            headers["Authorization"] = f"Bearer {settings.portal_api_key.get_secret_value()}"
        self._http = httpx.AsyncClient(
            base_url=settings.portal_base_url, headers=headers, timeout=15.0
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_account(self, *, partner_id: str, partner_name: str) -> PortalAccount:
        r = await self._http.post(
            "/v1/accounts",
            json={"partner_id": partner_id, "partner_name": partner_name},
        )
        r.raise_for_status()
        data = r.json()
        log.info("portal.account.created", account_id=data["account_id"])
        return PortalAccount(**data)

    async def upload_co_branded_asset(
        self, *, account_id: str, filename: str, content: bytes
    ) -> str:
        files = {"file": (filename, content, "application/pdf")}
        r = await self._http.post(f"/v1/accounts/{account_id}/assets", files=files)
        r.raise_for_status()
        url = r.json()["url"]
        log.info("portal.asset.uploaded", account_id=account_id, filename=filename)
        return url

    async def create_intake_form(self, *, account_id: str, fields: list[str]) -> str:
        r = await self._http.post(
            f"/v1/accounts/{account_id}/intake-forms",
            json={"fields": fields},
        )
        r.raise_for_status()
        return r.json()["url"]

    async def get_usage(self, account_id: str, days: int = 30) -> dict:
        r = await self._http.get(f"/v1/accounts/{account_id}/usage", params={"days": days})
        r.raise_for_status()
        return r.json()
