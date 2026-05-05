"""Real Microsoft Graph adapter (app-only auth).

Requires an Entra ID app registration with at least:
  - User.ReadWrite.All
  - Sites.FullControl.All
  - Group.ReadWrite.All
  - Tasks.ReadWrite.All
  - Files.ReadWrite.All
and admin consent granted.
"""

from __future__ import annotations

import structlog
from azure.identity.aio import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.assigned_license import AssignedLicense
from msgraph.generated.models.password_profile import PasswordProfile
from msgraph.generated.models.planner_bucket import PlannerBucket
from msgraph.generated.models.planner_plan import PlannerPlan
from msgraph.generated.models.planner_plan_container import PlannerPlanContainer
from msgraph.generated.models.user import User
from tenacity import retry, stop_after_attempt, wait_exponential

from b2b_toolkit.models import Mailbox, PlannerBoard, SharePointSite
from b2b_toolkit.settings import Settings

log = structlog.get_logger()


class M365GraphClient:
    def __init__(self, settings: Settings, default_password: str = "ChangeMe!" + "12345"):
        if not settings.m365_configured():
            raise RuntimeError("M365 credentials not configured")
        self._settings = settings
        self._default_password = default_password
        self._cred = ClientSecretCredential(
            tenant_id=settings.m365_tenant_id,
            client_id=settings.m365_client_id,
            client_secret=settings.m365_client_secret.get_secret_value(),
        )
        self._client = GraphServiceClient(
            credentials=self._cred,
            scopes=["https://graph.microsoft.com/.default"],
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_mailbox(self, *, display_name: str, alias: str) -> Mailbox:
        upn = f"{alias}@{self._settings.m365_tenant_id}"
        existing = await self._find_user_by_upn(upn)
        if existing:
            log.info("m365.mailbox.exists", upn=upn)
            return Mailbox(upn=upn, display_name=existing.display_name, object_id=existing.id)

        body = User(
            account_enabled=True,
            display_name=display_name,
            mail_nickname=alias,
            user_principal_name=upn,
            password_profile=PasswordProfile(
                password=self._default_password,
                force_change_password_next_sign_in=True,
            ),
        )
        created = await self._client.users.post(body)
        log.info("m365.mailbox.created", upn=upn, object_id=created.id)
        return Mailbox(upn=upn, display_name=display_name, object_id=created.id)

    async def _find_user_by_upn(self, upn: str) -> User | None:
        try:
            return await self._client.users.by_user_id(upn).get()
        except Exception:
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_sharepoint_site(self, *, name: str, owner_upn: str) -> SharePointSite:
        # Real impl: use Sites.Create endpoint or provision via M365 group.
        # For brevity here we provision an M365 group (which auto-creates a SharePoint site).
        from msgraph.generated.models.group import Group

        slug = name.lower().replace(" ", "-")
        group = Group(
            display_name=name,
            mail_enabled=True,
            mail_nickname=slug,
            security_enabled=False,
            group_types=["Unified"],
        )
        created = await self._client.groups.post(group)
        # SharePoint site URL is derivable from the group; in production, poll group.sites endpoint.
        web_url = f"https://{self._settings.m365_tenant_id.split('.')[0]}.sharepoint.com/sites/{slug}"
        log.info("m365.site.created", name=name, group_id=created.id)
        return SharePointSite(site_id=created.id, web_url=web_url, name=name)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_planner_board(
        self, *, title: str, owner_group_id: str, buckets: list[str]
    ) -> PlannerBoard:
        plan = PlannerPlan(
            title=title,
            container=PlannerPlanContainer(
                container_id=owner_group_id,
                type="group",
                url=f"https://graph.microsoft.com/v1.0/groups/{owner_group_id}",
            ),
        )
        created_plan = await self._client.planner.plans.post(plan)
        bucket_ids: list[str] = []
        for name in buckets:
            b = PlannerBucket(name=name, plan_id=created_plan.id, order_hint=" !")
            created_bucket = await self._client.planner.buckets.post(b)
            bucket_ids.append(created_bucket.id)
        log.info("m365.planner.created", plan_id=created_plan.id, buckets=len(bucket_ids))
        return PlannerBoard(plan_id=created_plan.id, title=title, bucket_ids=bucket_ids)

    async def upload_file(self, *, site_id: str, path: str, content: bytes) -> str:
        # Upload to the default drive of a site
        drive = await self._client.sites.by_site_id(site_id).drive.get()
        item = (
            await self._client.drives.by_drive_id(drive.id)
            .root.item_with_path(path)
            .content.put(content)
        )
        log.info("m365.file.uploaded", path=path, item_id=item.id)
        return item.web_url
