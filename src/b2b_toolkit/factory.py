"""Single entry point that returns the right adapter set based on settings."""

from __future__ import annotations

from dataclasses import dataclass

from b2b_toolkit.adapters.azure_resource import AzureResourceClient, AzureResourceMock
from b2b_toolkit.adapters.base import (
    AzureResourceAdapter,
    EntraAuditAdapter,
    HubSpotAdapter,
    M365Adapter,
    M365MailerAdapter,
    PortalAdapter,
    ZendeskAdapter,
)
from b2b_toolkit.adapters.entra_audit import EntraAuditClient, EntraAuditMock
from b2b_toolkit.adapters.hubspot import HubSpotMock
from b2b_toolkit.adapters.m365 import M365GraphClient, M365Mock
from b2b_toolkit.adapters.m365_mailer import M365MailerClient, M365MailerMock
from b2b_toolkit.adapters.portal import PortalClient
from b2b_toolkit.adapters.zendesk import ZendeskMock
from b2b_toolkit.settings import Settings


@dataclass
class Adapters:
    m365: M365Adapter
    hubspot: HubSpotAdapter
    zendesk: ZendeskAdapter
    portal: PortalAdapter
    entra_audit: EntraAuditAdapter
    azure_resource: AzureResourceAdapter
    m365_mailer: M365MailerAdapter


def get_adapters(settings: Settings | None = None) -> Adapters:
    s = settings or Settings()
    use_real = (not s.use_mocks) and s.m365_configured()

    m365: M365Adapter = M365GraphClient(s) if use_real else M365Mock()
    entra: EntraAuditAdapter = EntraAuditClient(s) if use_real else EntraAuditMock()
    azure: AzureResourceAdapter = AzureResourceClient(s) if use_real else AzureResourceMock()
    mailer: M365MailerAdapter = M365MailerClient(s) if use_real else M365MailerMock()

    return Adapters(
        m365=m365,
        hubspot=HubSpotMock(),
        zendesk=ZendeskMock(),
        portal=PortalClient(s),
        entra_audit=entra,
        azure_resource=azure,
        m365_mailer=mailer,
    )
