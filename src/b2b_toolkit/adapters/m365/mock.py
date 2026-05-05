"""In-memory M365 mock — same protocol as M365GraphClient."""

from __future__ import annotations

from uuid import uuid4

import structlog

from b2b_toolkit.models import Mailbox, PlannerBoard, SharePointSite

log = structlog.get_logger()


class M365Mock:
    def __init__(self) -> None:
        self.mailboxes: dict[str, Mailbox] = {}
        self.sites: dict[str, SharePointSite] = {}
        self.plans: dict[str, PlannerBoard] = {}
        self.files: dict[str, bytes] = {}

    async def create_mailbox(self, *, display_name: str, alias: str) -> Mailbox:
        upn = f"{alias}@mock.tenant"
        if upn in self.mailboxes:
            return self.mailboxes[upn]
        mb = Mailbox(upn=upn, display_name=display_name, object_id=uuid4().hex)
        self.mailboxes[upn] = mb
        log.info("mock.m365.mailbox", upn=upn)
        return mb

    async def create_sharepoint_site(self, *, name: str, owner_upn: str) -> SharePointSite:
        slug = name.lower().replace(" ", "-")
        site = SharePointSite(
            site_id=uuid4().hex,
            web_url=f"https://mock.sharepoint.com/sites/{slug}",
            name=name,
        )
        self.sites[site.site_id] = site
        log.info("mock.m365.site", name=name)
        return site

    async def create_planner_board(
        self, *, title: str, owner_group_id: str, buckets: list[str]
    ) -> PlannerBoard:
        board = PlannerBoard(
            plan_id=uuid4().hex,
            title=title,
            bucket_ids=[uuid4().hex for _ in buckets],
        )
        self.plans[board.plan_id] = board
        log.info("mock.m365.planner", title=title, buckets=len(buckets))
        return board

    async def upload_file(self, *, site_id: str, path: str, content: bytes) -> str:
        key = f"{site_id}/{path}"
        self.files[key] = content
        log.info("mock.m365.upload", path=path, bytes=len(content))
        return f"https://mock.sharepoint.com/{key}"
