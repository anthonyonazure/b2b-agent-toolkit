"""Smoke tests for the factory + every mock adapter."""

from __future__ import annotations

import os

import pytest

from b2b_toolkit import Settings, get_adapters
from b2b_toolkit.adapters.base import (
    AzureResourceAdapter,
    EntraAuditAdapter,
    HubSpotAdapter,
    M365Adapter,
    M365MailerAdapter,
    PortalAdapter,
    ZendeskAdapter,
)
from b2b_toolkit.models import (
    AuditEvent,
    AzureResourceFact,
    ConditionalAccessPolicy,
    EmailDraft,
    Mailbox,
    PlannerBoard,
    SharePointSite,
    ZendeskOrg,
)


# All env-driven config off; mocks for everyone
@pytest.fixture(autouse=True)
def _force_mocks(monkeypatch):
    monkeypatch.setenv("B2B_USE_MOCKS", "true")
    for v in (
        "B2B_M365_TENANT_ID",
        "B2B_M365_CLIENT_ID",
        "B2B_M365_CLIENT_SECRET",
        "B2B_M365_DOMAIN",
    ):
        monkeypatch.delenv(v, raising=False)


def test_factory_returns_all_adapters_conforming_to_protocols():
    a = get_adapters(Settings())
    assert isinstance(a.m365, M365Adapter)
    assert isinstance(a.hubspot, HubSpotAdapter)
    assert isinstance(a.zendesk, ZendeskAdapter)
    assert isinstance(a.portal, PortalAdapter)
    assert isinstance(a.entra_audit, EntraAuditAdapter)
    assert isinstance(a.azure_resource, AzureResourceAdapter)
    assert isinstance(a.m365_mailer, M365MailerAdapter)


@pytest.mark.asyncio
async def test_m365_mock_provisions_mailbox_site_planner():
    a = get_adapters(Settings())
    mb = await a.m365.create_mailbox(display_name="Demo", alias="demo")
    assert isinstance(mb, Mailbox)
    site = await a.m365.create_sharepoint_site(name="Demo Workspace", owner_upn=mb.upn)
    assert isinstance(site, SharePointSite)
    plan = await a.m365.create_planner_board(
        title="Demo Board", owner_group_id=site.site_id, buckets=["A", "B"]
    )
    assert isinstance(plan, PlannerBoard)
    assert len(plan.bucket_ids) == 2


@pytest.mark.asyncio
async def test_zendesk_mock_org_and_sla():
    a = get_adapters(Settings())
    org = await a.zendesk.create_organization(name="Acme", domain="acme.com", tier="gold")
    assert isinstance(org, ZendeskOrg)
    sla = await a.zendesk.attach_sla_policy(org_id=org.organization_id, tier="gold")
    assert sla > 0


@pytest.mark.asyncio
async def test_entra_mock_returns_typed_results():
    a = get_adapters(Settings())
    pols = await a.entra_audit.list_conditional_access_policies()
    assert all(isinstance(p, ConditionalAccessPolicy) for p in pols)
    audits = await a.entra_audit.list_directory_audit_events(days=30)
    assert all(isinstance(e, AuditEvent) for e in audits)
    members = await a.entra_audit.list_admin_role_members()
    assert all("role" in m and "member_upn" in m for m in members)


@pytest.mark.asyncio
async def test_azure_mock_returns_resource_facts():
    a = get_adapters(Settings())
    facts = await a.azure_resource.query_resources("Resources")
    assert all(isinstance(f, AzureResourceFact) for f in facts)
    diag = await a.azure_resource.get_subscription_diagnostic_settings()
    assert diag == []  # mock surfaces "no export" gap


@pytest.mark.asyncio
async def test_m365_mailer_mock_creates_draft():
    a = get_adapters(Settings())
    d = await a.m365_mailer.create_draft(
        sender_upn="me@example.com",
        to=["target@example.com"],
        subject="hello",
        body_html="<p>hi</p>",
    )
    assert isinstance(d, EmailDraft)
    assert d.subject == "hello"
    assert "target@example.com" in d.to
