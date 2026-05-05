"""Single entry point that returns the right adapter set based on settings."""

from __future__ import annotations

from dataclasses import dataclass

from b2b_toolkit.adapters.base import (
    HubSpotAdapter,
    M365Adapter,
    PortalAdapter,
    ZendeskAdapter,
)
from b2b_toolkit.adapters.hubspot import HubSpotMock
from b2b_toolkit.adapters.m365 import M365GraphClient, M365Mock
from b2b_toolkit.adapters.portal import PortalClient
from b2b_toolkit.adapters.zendesk import ZendeskMock
from b2b_toolkit.settings import Settings


@dataclass
class Adapters:
    m365: M365Adapter
    hubspot: HubSpotAdapter
    zendesk: ZendeskAdapter
    portal: PortalAdapter


def get_adapters(settings: Settings | None = None) -> Adapters:
    s = settings or Settings()
    m365: M365Adapter
    if s.use_mocks or not s.m365_configured():
        m365 = M365Mock()
    else:
        m365 = M365GraphClient(s)

    return Adapters(
        m365=m365,
        hubspot=HubSpotMock(),
        zendesk=ZendeskMock(),
        portal=PortalClient(s),
    )
