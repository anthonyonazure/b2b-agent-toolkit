"""Azure Resource Graph mock — returns canned facts engineered to surface
common SOC 2 gaps (storage account public, no diagnostic settings)."""

from __future__ import annotations

import structlog

from b2b_toolkit.models import AzureResourceFact

log = structlog.get_logger()


class AzureResourceMock:
    async def query_resources(self, kql: str) -> list[AzureResourceFact]:
        log.info("mock.azure.resource_graph", kql=kql[:60])
        # Return a few resources covering different control gaps. The compliance
        # agent can decide what to flag based on its KQL filtering.
        return [
            AzureResourceFact(
                resource_id="/subscriptions/demo/resourceGroups/aam-portfolio-rg/providers/Microsoft.Web/sites/aam-bot",
                resource_type="microsoft.web/sites",
                name="aam-bot",
                location="eastus",
                properties={"httpsOnly": True, "minimumTlsVersion": "1.2"},
            ),
            AzureResourceFact(
                resource_id="/subscriptions/demo/resourceGroups/aam-portfolio-rg/providers/Microsoft.Storage/storageAccounts/aamlogs01",
                resource_type="microsoft.storage/storageaccounts",
                name="aamlogs01",
                location="eastus",
                properties={
                    "supportsHttpsTrafficOnly": True,
                    "minimumTlsVersion": "TLS1_2",
                    "allowBlobPublicAccess": True,  # gap — public blobs allowed
                    "encryption": {"services": {"blob": {"enabled": True}}},
                },
            ),
            AzureResourceFact(
                resource_id="/subscriptions/demo/resourceGroups/aam-portfolio-rg/providers/Microsoft.KeyVault/vaults/aam-kv",
                resource_type="microsoft.keyvault/vaults",
                name="aam-kv",
                location="eastus",
                properties={
                    "enableSoftDelete": True,
                    "enablePurgeProtection": False,  # gap — purge protection off
                    "enabledForDeployment": False,
                    "publicNetworkAccess": "Enabled",
                },
            ),
        ]

    async def get_subscription_diagnostic_settings(self) -> list[dict]:
        # Empty = no subscription-level activity logging exported. SOC 2 gap.
        return []
