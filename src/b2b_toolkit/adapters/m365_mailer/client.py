"""M365 mailer — creates DRAFT emails in a sender's mailbox via Graph.

Drafts are intentional: humans review and click Send. AAM never autonomously
sends mail on a user's behalf.

Required Graph application permission: Mail.ReadWrite (the SP must be granted
this on the target mailbox; for tenant-wide use, Mail.ReadWrite app permission
+ admin consent).
"""

from __future__ import annotations

import httpx
import structlog
from azure.identity.aio import ClientSecretCredential
from tenacity import retry, stop_after_attempt, wait_exponential

from b2b_toolkit.models import EmailDraft
from b2b_toolkit.settings import Settings

log = structlog.get_logger()


class M365MailerClient:
    def __init__(self, settings: Settings):
        if not settings.m365_configured():
            raise RuntimeError("M365 credentials not configured")
        self._settings = settings

    async def _token(self) -> str:
        async with ClientSecretCredential(
            tenant_id=self._settings.m365_tenant_id,
            client_id=self._settings.m365_client_id,
            client_secret=self._settings.m365_client_secret.get_secret_value(),
        ) as cred:
            return (await cred.get_token("https://graph.microsoft.com/.default")).token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_draft(
        self, *, sender_upn: str, to: list[str], subject: str, body_html: str
    ) -> EmailDraft:
        token = await self._token()
        body = {
            "subject": subject,
            "body": {"contentType": "html", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
        }
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(
                f"https://graph.microsoft.com/v1.0/users/{sender_upn}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        log.info("m365.mailer.draft_created", upn=sender_upn, subject=subject[:40], id=data["id"])
        return EmailDraft(
            draft_id=data["id"],
            to=to,
            subject=subject,
            body_preview=body_html[:200],
            web_link=data.get("webLink"),
        )
