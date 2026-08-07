"""Entra ID audit + policy reads via Microsoft Graph.

Required Graph application permissions:
  - Policy.Read.All                 (conditional access policies)
  - AuditLog.Read.All               (directory audit events)
  - RoleManagement.Read.Directory   (admin role assignments)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import structlog
from azure.identity.aio import ClientSecretCredential
from tenacity import retry, stop_after_attempt, wait_exponential

from b2b_toolkit.models import AuditEvent, ConditionalAccessPolicy
from b2b_toolkit.settings import Settings

log = structlog.get_logger()


class EntraAuditClient:
    def __init__(self, settings: Settings):
        if not settings.m365_configured():
            raise RuntimeError("M365 credentials not configured")
        self._settings = settings

    async def _token(self) -> str:
        tenant_id, client_id, client_secret = self._settings.m365_credentials()
        async with ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        ) as cred:
            return (await cred.get_token("https://graph.microsoft.com/.default")).token

    async def _get(self, path: str, params: dict | None = None) -> dict:
        token = await self._token()
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(
                f"https://graph.microsoft.com/v1.0/{path.lstrip('/')}",
                headers={"Authorization": f"Bearer {token}"},
                params=params or {},
            )
            r.raise_for_status()
            return r.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def list_conditional_access_policies(self) -> list[ConditionalAccessPolicy]:
        data = await self._get("identity/conditionalAccess/policies")
        out: list[ConditionalAccessPolicy] = []
        for p in data.get("value", []):
            grants = (p.get("grantControls") or {}).get("builtInControls") or []
            users = p.get("conditions", {}).get("users", {})
            apps = p.get("conditions", {}).get("applications", {})
            out.append(
                ConditionalAccessPolicy(
                    id=p["id"],
                    display_name=p.get("displayName", ""),
                    state=p.get("state", "unknown"),
                    grant_controls=grants,
                    user_scope_includes=users.get("includeUsers", []),
                    user_scope_excludes=users.get("excludeUsers", []),
                    apps_includes=apps.get("includeApplications", []),
                )
            )
        log.info("entra.policies.fetched", count=len(out))
        return out

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def list_directory_audit_events(self, *, days: int = 30) -> list[AuditEvent]:
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        data = await self._get(
            "auditLogs/directoryAudits",
            params={"$filter": f"activityDateTime ge {since}", "$top": "200"},
        )
        out: list[AuditEvent] = []
        for e in data.get("value", []):
            initiated = (
                (e.get("initiatedBy") or {}).get("user")
                or (e.get("initiatedBy") or {}).get("app")
                or {}
            )
            targets = [
                t.get("displayName") or t.get("id") for t in (e.get("targetResources") or [])
            ]
            out.append(
                AuditEvent(
                    id=e["id"],
                    activity_display_name=e.get("activityDisplayName", ""),
                    # Python 3.11+ parses the trailing "Z" natively, so no
                    # substitution to "+00:00" is needed.
                    activity_datetime=datetime.fromisoformat(e["activityDateTime"]),
                    initiated_by=initiated.get("userPrincipalName")
                    or initiated.get("displayName")
                    or "unknown",
                    target_resources=[t for t in targets if t],
                    result=e.get("result", "unknown"),
                )
            )
        log.info("entra.audit.fetched", count=len(out), days=days)
        return out

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def list_admin_role_members(self) -> list[dict]:
        # Returns a flat list of {role, member_upn, member_object_id}
        roles = await self._get("directoryRoles")
        out = []
        for r in roles.get("value", []):
            members = await self._get(f"directoryRoles/{r['id']}/members")
            for m in members.get("value", []):
                out.append(
                    {
                        "role": r.get("displayName"),
                        "member_upn": m.get("userPrincipalName"),
                        "member_id": m.get("id"),
                        "type": m.get("@odata.type", "").split(".")[-1],
                    }
                )
        log.info("entra.roles.fetched", count=len(out))
        return out
