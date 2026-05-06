"""M365 mailer mock — records drafts in memory; returns the same EmailDraft shape."""

from __future__ import annotations

from uuid import uuid4

import structlog

from b2b_toolkit.models import EmailDraft

log = structlog.get_logger()


class M365MailerMock:
    def __init__(self) -> None:
        self.drafts: list[EmailDraft] = []

    async def create_draft(
        self, *, sender_upn: str, to: list[str], subject: str, body_html: str
    ) -> EmailDraft:
        d = EmailDraft(
            draft_id=uuid4().hex,
            to=to,
            subject=subject,
            body_preview=body_html[:200],
            web_link=f"https://mock.outlook/draft/{uuid4().hex[:8]}",
        )
        self.drafts.append(d)
        log.info("mock.m365.mailer.draft", upn=sender_upn, subject=subject[:40])
        return d
