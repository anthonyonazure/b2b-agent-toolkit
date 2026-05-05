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
        upn = f"{alias}@{self._settings.m365_domain}"
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
        except Exception as e:
            # Only treat "not found" as absent. Re-raise auth/permission errors
            # so we don't silently mask real problems then collide on create.
            code = getattr(getattr(e, "error", None), "code", "") or ""
            if "Request_ResourceNotFound" in code or "ResourceNotFound" in code:
                return None
            if getattr(e, "response_status_code", None) == 404:
                return None
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_sharepoint_site(self, *, name: str, owner_upn: str) -> SharePointSite:
        # Real impl: use Sites.Create endpoint or provision via M365 group.
        # For brevity here we provision an M365 group (which auto-creates a SharePoint site).
        from msgraph.generated.models.group import Group
        from msgraph.generated.groups.groups_request_builder import GroupsRequestBuilder

        slug = name.lower().replace(" ", "-")

        # Idempotency: return existing group if mailNickname already taken
        existing = await self._client.groups.get(
            request_configuration=GroupsRequestBuilder.GroupsRequestBuilderGetRequestConfiguration(
                query_parameters=GroupsRequestBuilder.GroupsRequestBuilderGetQueryParameters(
                    filter=f"mailNickname eq '{slug}'",
                )
            )
        )
        if existing and existing.value:
            g = existing.value[0]
            log.info("m365.site.exists", name=name, group_id=g.id)
            return SharePointSite(
                site_id=g.id,
                web_url=f"https://{self._settings.sharepoint_host()}/sites/{slug}",
                name=name,
            )

        group = Group(
            display_name=name,
            mail_enabled=True,
            mail_nickname=slug,
            security_enabled=False,
            group_types=["Unified"],
        )
        created = await self._client.groups.post(group)
        # The group provisions a SharePoint site asynchronously; web URL is derivable
        # from the SharePoint host + group mailNickname. In production you'd poll
        # /groups/{id}/sites/root for a deterministic URL.
        web_url = f"https://{self._settings.sharepoint_host()}/sites/{slug}"
        log.info("m365.site.created", name=name, group_id=created.id)
        return SharePointSite(site_id=created.id, web_url=web_url, name=name)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def create_planner_board(
        self, *, title: str, owner_group_id: str, buckets: list[str]
    ) -> PlannerBoard:
        # Idempotency: if a plan with the same title already exists in the group, reuse it
        try:
            existing_plans = await self._client.groups.by_group_id(owner_group_id).planner.plans.get()
            for p in (existing_plans.value if existing_plans else []) or []:
                if p.title == title:
                    log.info("m365.planner.exists", plan_id=p.id, title=title)
                    existing_buckets = await self._client.planner.plans.by_planner_plan_id(p.id).buckets.get()
                    bucket_ids = [b.id for b in (existing_buckets.value or [])]
                    return PlannerBoard(plan_id=p.id, title=title, bucket_ids=bucket_ids)
        except Exception as e:
            log.warning("m365.planner.lookup_failed", err=str(e)[:200])

        plan = PlannerPlan(
            title=title,
            container=PlannerPlanContainer(
                # Per Graph: must specify url alone, OR (type + container_id) without url
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
        # site_id here is the M365 group id (we provision via group).
        # SharePoint sites for groups are provisioned asynchronously, so the first
        # upload after group creation may need a brief retry. We resolve the
        # group's root site, then PUT to its drive via raw HTTP for the path-based
        # endpoint (the SDK's path-upload helper isn't exposed cleanly in 1.56).
        import httpx

        site = await self._client.groups.by_group_id(site_id).sites.by_site_id("root").get()
        drive = await self._client.sites.by_site_id(site.id).drive.get()

        # Use a self-contained credential for the raw HTTP token — the long-lived
        # one shared with the SDK has its aiohttp transport closed by this point.
        async with ClientSecretCredential(
            tenant_id=self._settings.m365_tenant_id,
            client_id=self._settings.m365_client_id,
            client_secret=self._settings.m365_client_secret.get_secret_value(),
        ) as token_cred:
            token = await token_cred.get_token("https://graph.microsoft.com/.default")
        encoded_path = path.lstrip("/")
        url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive.id}"
            f"/root:/{encoded_path}:/content"
        )
        async with httpx.AsyncClient(timeout=60.0) as http:
            r = await http.put(
                url,
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Type": "application/octet-stream",
                },
                content=content,
            )
            r.raise_for_status()
            data = r.json()
        log.info("m365.file.uploaded", path=path, item_id=data.get("id"))
        return data.get("webUrl") or ""
