"""Zendesk mock adapter."""

from __future__ import annotations

import structlog

from b2b_toolkit.models import PartnerTier, ZendeskOrg

log = structlog.get_logger()

_SLA_BY_TIER: dict[PartnerTier, int] = {
    "bronze": 4001,
    "silver": 4002,
    "gold": 4003,
    "platinum": 4004,
}


class ZendeskMock:
    def __init__(self) -> None:
        self._orgs: dict[int, ZendeskOrg] = {}
        self._next_id = 9000

    async def create_organization(self, *, name: str, domain: str, tier: PartnerTier) -> ZendeskOrg:
        self._next_id += 1
        org = ZendeskOrg(organization_id=self._next_id, name=name)
        self._orgs[org.organization_id] = org
        log.info("mock.zendesk.org", name=name, id=org.organization_id)
        return org

    async def attach_sla_policy(self, *, org_id: int, tier: PartnerTier) -> int:
        sla_id = _SLA_BY_TIER[tier]
        if org_id in self._orgs:
            self._orgs[org_id].sla_policy_id = sla_id
        log.info("mock.zendesk.sla", org_id=org_id, sla_id=sla_id)
        return sla_id

    async def get_ticket_velocity(self, org_id: int, days: int = 30) -> dict:
        return {
            "tickets_opened": 18,
            "tickets_closed": 14,
            "avg_first_response_minutes": 22,
            "avg_resolution_hours": 9.4,
            "p1_count": 1,
        }
