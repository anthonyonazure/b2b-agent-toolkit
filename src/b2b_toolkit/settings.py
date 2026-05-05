from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="B2B_",
        extra="ignore",
        case_sensitive=False,
    )

    use_mocks: bool = True

    m365_tenant_id: str | None = None
    m365_client_id: str | None = None
    m365_client_secret: SecretStr | None = None
    m365_domain: str | None = None  # verified domain for UPNs (e.g. "contoso.com")
    m365_sharepoint_host: str | None = None  # e.g. "contoso.sharepoint.com"; auto-derived if unset

    hubspot_token: SecretStr | None = None

    zendesk_subdomain: str | None = None
    zendesk_email: str | None = None
    zendesk_token: SecretStr | None = None

    portal_base_url: str = "http://localhost:8001"
    portal_api_key: SecretStr | None = None

    def m365_configured(self) -> bool:
        return all([
            self.m365_tenant_id, self.m365_client_id, self.m365_client_secret, self.m365_domain
        ])

    def sharepoint_host(self) -> str:
        if self.m365_sharepoint_host:
            return self.m365_sharepoint_host
        # Default: <domain prefix>.sharepoint.com (works when initial onmicrosoft tenant matches)
        return f"{(self.m365_domain or '').split('.')[0]}.sharepoint.com"
