from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class EnterpriseMetadata:
    source: str
    external_id: str
    name: str
    description: str
    owner: str
    resource_count: int
    tags: list[str]
    raw: dict[str, Any]


class EnterpriseConnectorClient:
    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch(self, source: str, identifier: str, overrides: dict[str, Any] | None = None) -> EnterpriseMetadata:
        source = source.strip().lower()
        overrides = overrides or {}
        if source == "github":
            return await self._from_github(identifier, overrides=overrides)
        if source == "servicenow":
            return self._from_servicenow(identifier, overrides=overrides)
        return self._from_manual(source, identifier, overrides=overrides)

    async def _from_github(self, repo_path: str, overrides: dict[str, Any]) -> EnterpriseMetadata:
        url = f"https://api.github.com/repos/{repo_path}"
        response = await self._client.get(url, headers={"Accept": "application/vnd.github+json"})
        if response.status_code >= 400:
            return self._from_manual(
                "github",
                repo_path,
                overrides={
                    **overrides,
                    "description": overrides.get("description") or "GitHub repository metadata unavailable.",
                },
            )
        payload = response.json()
        topics = payload.get("topics") or []
        return EnterpriseMetadata(
            source="github",
            external_id=str(payload.get("full_name") or repo_path),
            name=str(overrides.get("name") or payload.get("name") or repo_path),
            description=str(overrides.get("description") or payload.get("description") or ""),
            owner=str(payload.get("owner", {}).get("login") or "unknown"),
            resource_count=int(payload.get("stargazers_count") or 0),
            tags=[str(t) for t in topics[:12]],
            raw=payload,
        )

    def _from_servicenow(self, config_item: str, overrides: dict[str, Any]) -> EnterpriseMetadata:
        return EnterpriseMetadata(
            source="servicenow",
            external_id=config_item,
            name=str(overrides.get("name") or config_item),
            description=str(overrides.get("description") or "ServiceNow configuration item"),
            owner=str(overrides.get("owner") or "servicenow-team"),
            resource_count=int(overrides.get("resource_count") or 1),
            tags=[str(x) for x in (overrides.get("tags") or ["itsm", "cmdb"])],
            raw={"config_item": config_item},
        )

    def _from_manual(self, source: str, identifier: str, overrides: dict[str, Any]) -> EnterpriseMetadata:
        return EnterpriseMetadata(
            source=source,
            external_id=identifier,
            name=str(overrides.get("name") or identifier),
            description=str(overrides.get("description") or ""),
            owner=str(overrides.get("owner") or "unknown"),
            resource_count=int(overrides.get("resource_count") or 1),
            tags=[str(x) for x in (overrides.get("tags") or [])],
            raw=overrides,
        )

