"""HubSpot mock — returns deterministic seeded data for portfolio demos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

log = structlog.get_logger()

_SEED_DEALS = {
    "deal-001": {
        "id": "deal-001",
        "dealname": "Acme Corp - Managed SOC",
        "amount": 84_000,
        "dealstage": "closedwon",
        "closedate": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "associated_company_id": "company-001",
        "services_purchased": ["managed-soc", "vuln-mgmt", "incident-response"],
    },
}

_SEED_COMPANIES = {
    "company-001": {
        "id": "company-001",
        "name": "Acme Corp",
        "domain": "acme.com",
        "tier": "gold",
        "region": "NA",
        "primary_contact_email": "ciso@acme.com",
        "primary_contact_name": "Jordan Reeves",
        "logo_url": "https://logo.clearbit.com/acme.com",
        "contract_signed_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    },
}


class HubSpotMock:
    def __init__(self) -> None:
        self._deal_notes: dict[str, list[str]] = {}

    async def get_deal(self, deal_id: str) -> dict:
        log.info("mock.hubspot.get_deal", deal_id=deal_id)
        return _SEED_DEALS.get(deal_id) or _SEED_DEALS["deal-001"]

    async def get_company(self, company_id: str) -> dict:
        log.info("mock.hubspot.get_company", company_id=company_id)
        return _SEED_COMPANIES.get(company_id) or _SEED_COMPANIES["company-001"]

    async def add_note_to_deal(self, deal_id: str, note: str) -> None:
        self._deal_notes.setdefault(deal_id, []).append(note)
        log.info("mock.hubspot.note", deal_id=deal_id)

    async def get_engagement_signals(self, company_id: str, days: int = 30) -> dict:
        return {
            "emails_opened": 12,
            "meetings_attended": 3,
            "last_activity_at": (datetime.now(UTC) - timedelta(days=4)).isoformat(),
            "trend": "stable",
        }
