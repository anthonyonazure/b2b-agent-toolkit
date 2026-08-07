"""Azure Resource Graph reads.

Required Azure RBAC: at least Reader on the subscription. The bot's existing
service principal needs to be added as Reader on the subscription scope:
    az role assignment create --assignee <sp-object-id> --role Reader \
        --scope /subscriptions/<sub-id>
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog
from azure.identity.aio import ClientSecretCredential
from tenacity import retry, stop_after_attempt, wait_exponential

from b2b_toolkit.models import AzureResourceFact
from b2b_toolkit.settings import Settings

log = structlog.get_logger()


class AzureResourceClient:
    def __init__(self, settings: Settings):
        if not settings.m365_configured():
            raise RuntimeError("Azure credentials (sharing M365 SP) not configured")
        self._settings = settings

    async def _token(self, audience: str = "https://management.azure.com/.default") -> str:
        tenant_id, client_id, client_secret = self._settings.m365_credentials()
        async with ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        ) as cred:
            return (await cred.get_token(audience)).token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def query_resources(self, kql: str) -> list[AzureResourceFact]:
        token = await self._token()
        sub_id = os.environ.get("B2B_AZURE_SUBSCRIPTION_ID")
        body: dict[str, Any] = {"query": kql}
        if sub_id:
            body["subscriptions"] = [sub_id]
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(
                "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        out = [
            AzureResourceFact(
                resource_id=row.get("id", ""),
                resource_type=row.get("type", ""),
                name=row.get("name", ""),
                location=row.get("location", "global"),
                properties=row.get("properties") or {},
            )
            for row in data.get("data", [])
        ]
        log.info("azure.resource_graph.query", count=len(out), kql_preview=kql[:80])
        return out

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def get_subscription_diagnostic_settings(self) -> list[dict]:
        token = await self._token()
        sub_id = os.environ.get("B2B_AZURE_SUBSCRIPTION_ID")
        if not sub_id:
            log.warning("azure.diag.no_subscription_id")
            return []
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(
                f"https://management.azure.com/subscriptions/{sub_id}/providers/microsoft.insights/diagnosticSettings?api-version=2021-05-01-preview",
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            return r.json().get("value", [])
