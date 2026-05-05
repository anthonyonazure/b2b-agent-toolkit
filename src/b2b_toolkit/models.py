from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

PartnerTier = Literal["bronze", "silver", "gold", "platinum"]


class Partner(BaseModel):
    id: str
    name: str
    domain: str
    primary_contact_email: EmailStr
    primary_contact_name: str
    logo_url: str | None = None
    tier: PartnerTier = "silver"
    region: str = "NA"
    contract_signed_at: datetime
    services_purchased: list[str] = Field(default_factory=list)


class Mailbox(BaseModel):
    upn: str
    display_name: str
    object_id: str


class SharePointSite(BaseModel):
    site_id: str
    web_url: str
    name: str


class PlannerBoard(BaseModel):
    plan_id: str
    title: str
    bucket_ids: list[str] = Field(default_factory=list)


class ZendeskOrg(BaseModel):
    organization_id: int
    name: str
    sla_policy_id: int | None = None


class PortalAccount(BaseModel):
    account_id: str
    partner_id: str
    api_key: str
    intake_form_url: str


class ProvisioningResult(BaseModel):
    """Generic envelope so nodes can store mixed adapter outputs in graph state."""

    success: bool
    resource_kind: str
    resource_id: str | None = None
    detail: dict = Field(default_factory=dict)
    error: str | None = None
