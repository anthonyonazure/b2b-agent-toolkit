# b2b-agent-toolkit

Reusable Python integration adapters for AI agents that operate against B2B SaaS stacks.

Designed to be imported by both [partner-onboarding-agent](https://github.com/anthonyonazure/partner-onboarding-agent) and [ai-account-manager](https://github.com/anthonyonazure/ai-account-manager), but works standalone for any LangGraph / LangChain / Anthropic SDK project.

### One small protocol per source — real and mock implementations both conform

![Adapter Protocols](docs/media/adapter-protocols.png)

### Single entry point — env flag picks real vs mock

![Adapter factory](docs/media/factory.png)

## What's in here

| Adapter | Real impl | Mock impl | Notes |
|---|---|---|---|
| Microsoft 365 (Graph) | yes | yes | Mailbox, SharePoint, Planner via app-only auth |
| HubSpot | interface | yes | CRM cards, deals, contacts, webhooks |
| Zendesk | interface | yes | Organizations, tickets, SLA policies |
| Internal portal | client only | n/a — runs against [mock server](../partner-onboarding-agent/mock_portal/) | Speaks the same OpenAPI as the real portal |

Every adapter implements a small `Adapter` protocol so you can swap real ↔ mock with a single env flag (`B2B_USE_MOCKS`).

## Install

```bash
cd b2b-agent-toolkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in real creds only when you need them
```

## Use

```python
from b2b_toolkit import get_adapters

adapters = get_adapters()  # honors B2B_USE_MOCKS
mailbox = await adapters.m365.create_mailbox(
    display_name="Acme Partners",
    alias="acme-partners",
)
```

## Layout

```
src/b2b_toolkit/
├── settings.py          # pydantic-settings, env-driven config
├── models.py            # Partner, Account, ProvisioningResult
├── factory.py           # get_adapters() — picks real vs mock
└── adapters/
    ├── base.py          # Protocols
    ├── m365/            # Real Microsoft Graph + mock
    ├── hubspot/
    ├── zendesk/
    └── portal/          # Always real client; the *server* is mocked
```
