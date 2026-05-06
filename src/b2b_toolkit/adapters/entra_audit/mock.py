"""Entra audit mock — canned data engineered to expose realistic SOC 2 gaps:
no MFA-for-admins policy, audit log retention not configured, one global admin
without privileged access management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from b2b_toolkit.models import AuditEvent, ConditionalAccessPolicy

log = structlog.get_logger()
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


class EntraAuditMock:
    async def list_conditional_access_policies(self) -> list[ConditionalAccessPolicy]:
        log.info("mock.entra.policies")
        return [
            ConditionalAccessPolicy(
                id="ca-001",
                display_name="Block legacy authentication",
                state="enabled",
                grant_controls=["block"],
                user_scope_includes=["All"],
                apps_includes=["All"],
            ),
            ConditionalAccessPolicy(
                id="ca-002",
                display_name="Require MFA for guest users",
                state="enabled",
                grant_controls=["mfa"],
                user_scope_includes=["GuestsOrExternalUsers"],
                apps_includes=["All"],
            ),
            # Intentionally missing: a "Require MFA for all users" or
            # "Require MFA for admins" policy. The compliance agent should flag this.
        ]

    async def list_directory_audit_events(self, *, days: int = 30) -> list[AuditEvent]:
        return [
            AuditEvent(
                id=f"audit-{i:03d}",
                activity_display_name=name,
                activity_datetime=NOW - timedelta(days=i, hours=2),
                initiated_by=actor,
                target_resources=[target],
                result="success",
            )
            for i, (name, actor, target) in enumerate(
                [
                    ("Add user", "admin@mock.tenant", "new-user@mock.tenant"),
                    ("Update conditional access policy", "secadmin@mock.tenant", "Block legacy authentication"),
                    ("Add member to role", "admin@mock.tenant", "Privileged Role Administrator"),
                    ("Reset password (self-service)", "user@mock.tenant", "user@mock.tenant"),
                    ("Add owner to group", "admin@mock.tenant", "ENG-Engineering"),
                ]
            )
        ]

    async def list_admin_role_members(self) -> list[dict]:
        return [
            {"role": "Global Administrator", "member_upn": "admin@mock.tenant", "member_id": "u1", "type": "user"},
            {"role": "Global Administrator", "member_upn": "founder@mock.tenant", "member_id": "u2", "type": "user"},
            {"role": "Privileged Role Administrator", "member_upn": "secadmin@mock.tenant", "member_id": "u3", "type": "user"},
            {"role": "Security Administrator", "member_upn": "secadmin@mock.tenant", "member_id": "u3", "type": "user"},
        ]
