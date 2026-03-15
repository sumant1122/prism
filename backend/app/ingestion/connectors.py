from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

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
            return await self._from_github(self._normalize_github_identifier(identifier), overrides=overrides)
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
        languages = await self._fetch_github_languages(str(payload.get("languages_url") or ""))
        readme = await self._fetch_github_readme(repo_path)
        tree_paths = await self._fetch_github_tree(repo_path, str(payload.get("default_branch") or "HEAD"))
        file_samples = await self._fetch_key_file_samples(repo_path, tree_paths)
        description = str(overrides.get("description") or payload.get("description") or "").strip()
        readme_excerpt = str(readme.get("excerpt") or "").strip()
        combined_description = description
        if readme_excerpt:
            preview = readme_excerpt[:480]
            combined_description = f"{description}\n\nREADME snapshot:\n{preview}".strip()
        return EnterpriseMetadata(
            source="github",
            external_id=str(payload.get("full_name") or repo_path),
            name=str(overrides.get("name") or payload.get("name") or repo_path),
            description=combined_description,
            owner=str(payload.get("owner", {}).get("login") or "unknown"),
            resource_count=int(payload.get("stargazers_count") or 0),
            tags=self._dedupe_strings([*topics[:12], *languages[:6]]),
            raw={
                **payload,
                "full_name": str(payload.get("full_name") or repo_path),
                "languages": languages,
                "topics": [str(topic) for topic in topics[:12]],
                "readme_path": str(readme.get("path") or "README.md"),
                "readme_excerpt": readme_excerpt,
                "tree_paths": tree_paths[:300],
                "file_samples": file_samples,
            },
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

    def _normalize_github_identifier(self, identifier: str) -> str:
        cleaned = identifier.strip()
        if "github.com" not in cleaned:
            return cleaned.removesuffix(".git").strip("/")
        parsed = urlparse(cleaned)
        parts = [segment for segment in parsed.path.split("/") if segment]
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].removesuffix(".git")
            return f"{owner}/{repo}"
        return cleaned

    async def _fetch_github_languages(self, languages_url: str) -> list[str]:
        if not languages_url:
            return []
        try:
            response = await self._client.get(languages_url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            payload = response.json()
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(payload, dict):
            return []
        return [str(language) for language in list(payload.keys())[:8]]

    async def _fetch_github_readme(self, repo_path: str) -> dict[str, str]:
        url = f"https://api.github.com/repos/{repo_path}/readme"
        try:
            response = await self._client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            payload = response.json()
        except Exception:  # noqa: BLE001
            return {"path": "README.md", "excerpt": ""}
        content = str(payload.get("content") or "")
        encoding = str(payload.get("encoding") or "").lower()
        decoded = ""
        if content and encoding == "base64":
            try:
                decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                decoded = ""
        excerpt = self._extract_readme_excerpt(decoded)
        return {
            "path": str(payload.get("path") or "README.md"),
            "excerpt": excerpt,
        }

    async def _fetch_github_tree(self, repo_path: str, reference: str) -> list[str]:
        url = f"https://api.github.com/repos/{repo_path}/git/trees/{quote(reference, safe='')}?recursive=1"
        try:
            response = await self._client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            payload = response.json()
        except Exception:  # noqa: BLE001
            return []
        entries = payload.get("tree") or []
        if not isinstance(entries, list):
            return []
        paths = [str(entry.get("path") or "").strip() for entry in entries if str(entry.get("path") or "").strip()]
        return paths[:400]

    async def _fetch_key_file_samples(self, repo_path: str, tree_paths: list[str]) -> list[dict[str, str]]:
        interesting_paths = self._pick_interesting_paths(tree_paths)
        samples: list[dict[str, str]] = []
        for path in interesting_paths:
            content = await self._fetch_github_file_content(repo_path, path)
            if not content:
                continue
            samples.append({"path": path, "excerpt": content[:2200]})
        return samples[:10]

    async def _fetch_github_file_content(self, repo_path: str, path: str) -> str:
        url = f"https://api.github.com/repos/{repo_path}/contents/{quote(path, safe='/')}"
        try:
            response = await self._client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            payload = response.json()
        except Exception:  # noqa: BLE001
            return ""
        if not isinstance(payload, dict):
            return ""
        if str(payload.get("type") or "file") != "file":
            return ""
        content = str(payload.get("content") or "")
        encoding = str(payload.get("encoding") or "").lower()
        if not content or encoding != "base64":
            return ""
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            return ""
        return decoded.strip()

    def _pick_interesting_paths(self, tree_paths: list[str]) -> list[str]:
        preferred_names = {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "cargo.toml",
            "pom.xml",
            "build.gradle",
            "dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "tsconfig.json",
            "next.config.js",
            "next.config.mjs",
            "vite.config.ts",
            "vite.config.js",
            "prisma/schema.prisma",
        }
        preferred_fragments = [
            "app/",
            "src/",
            "components/",
            "pages/",
            "api/",
            "backend/",
            "frontend/",
        ]
        selected: list[str] = []
        for path in tree_paths:
            normalized = path.lower()
            basename = normalized.rsplit("/", maxsplit=1)[-1]
            if basename in preferred_names or normalized in preferred_names:
                selected.append(path)
                continue
            if any(fragment in normalized for fragment in preferred_fragments) and basename.endswith(
                (".ts", ".tsx", ".js", ".jsx", ".py")
            ):
                selected.append(path)
            if len(selected) >= 10:
                break
        return self._dedupe_strings(selected)[:10]

    def _extract_readme_excerpt(self, markdown: str) -> str:
        if not markdown.strip():
            return ""
        lines = []
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                if lines:
                    break
                continue
            if line.startswith("#") and not lines:
                continue
            lines.append(line)
            if len(" ".join(lines)) >= 600:
                break
        return " ".join(lines)[:1200]

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped
