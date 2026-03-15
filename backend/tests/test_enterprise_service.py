from __future__ import annotations

import sys
import types
import unittest

neo4j_stub = types.ModuleType("neo4j")
neo4j_stub.GraphDatabase = types.SimpleNamespace(driver=lambda *args, **kwargs: None)
neo4j_exceptions_stub = types.ModuleType("neo4j.exceptions")
neo4j_exceptions_stub.CypherSyntaxError = Exception
neo4j_exceptions_stub.Neo4jError = Exception
sys.modules.setdefault("neo4j", neo4j_stub)
sys.modules.setdefault("neo4j.exceptions", neo4j_exceptions_stub)

from app.agents.concept_agent import ConceptAgent
from app.ingestion.connectors import EnterpriseMetadata
from app.services.enterprise_service import EnterpriseService


class FakeConnectorClient:
    async def fetch(self, source: str, identifier: str, overrides=None) -> EnterpriseMetadata:
        return EnterpriseMetadata(
            source="github",
            external_id="acme/repo-teacher",
            name="repo-teacher",
            description="A Next.js and FastAPI app for explaining repositories.",
            owner="acme",
            resource_count=42,
            tags=["education", "ai"],
            raw={
                "languages": ["TypeScript", "Python"],
                "topics": ["education", "ai"],
                "readme_excerpt": "This project uses Next.js for the frontend, FastAPI for the backend, and pytest for tests.",
                "tree_paths": [
                    "frontend/app/page.tsx",
                    "frontend/components/RepoCard.tsx",
                    "backend/app/api/routes.py",
                    "backend/app/services/repo_teacher.py",
                    "backend/tests/test_repo_teacher.py",
                    "docker/docker-compose.yml",
                ],
                "file_samples": [
                    {
                        "path": "frontend/app/page.tsx",
                        "excerpt": "import { useState } from 'react'; async function loadRepo() { const res = await fetch('/api/repo'); }",
                    },
                    {
                        "path": "backend/app/api/routes.py",
                        "excerpt": "from fastapi import APIRouter\nrouter = APIRouter()\n@router.post('/repos')\nasync def analyze_repo(): ...",
                    },
                    {
                        "path": "backend/tests/test_repo_teacher.py",
                        "excerpt": "def test_repo_teacher_analysis():\n    assert True",
                    },
                ],
            },
        )


class FakeGraphRepo:
    def __init__(self) -> None:
        self.last_upsert: tuple[EnterpriseMetadata, list[str], list[str]] | None = None

    def upsert_enterprise_resource(
        self,
        metadata: EnterpriseMetadata,
        concepts: list[str],
        fields: list[str],
    ) -> None:
        self.last_upsert = (metadata, concepts, fields)

    def get_resources_for_relationship_scan(self, exclude_external_id: str, limit: int) -> list[dict]:
        return []

    def add_resource_relationship(self, source_external_id: str, relation: str, target_external_id: str) -> None:
        raise AssertionError("Relationship creation should not be called in this test")


class FakeRelationshipAgent:
    def determine_relationship(self, source_payload: dict, candidate: dict) -> None:
        return None


class EnterpriseServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_github_ingestion_returns_repo_teaching_report(self) -> None:
        graph_repo = FakeGraphRepo()
        service = EnterpriseService(
            connector_client=FakeConnectorClient(),
            graph_repo=graph_repo,
            concept_agent=ConceptAgent(),
            relationship_agent=FakeRelationshipAgent(),
        )

        result = await service.ingest_resource(source="github", identifier="acme/repo-teacher")

        self.assertIn("Client-Server Architecture", result.concepts)
        self.assertIn("Testing and Verification", result.concepts)
        self.assertTrue(result.repo_summary.startswith("acme/repo-teacher"))
        self.assertTrue(result.architecture_summary)
        self.assertEqual(result.languages, ["TypeScript", "Python"])
        self.assertTrue(result.concept_details)
        self.assertTrue(result.learning_path)
        self.assertIsNotNone(graph_repo.last_upsert)
        assert graph_repo.last_upsert is not None
        _, concepts, fields = graph_repo.last_upsert
        self.assertEqual(concepts, result.concepts)
        self.assertEqual(fields, result.fields)


if __name__ == "__main__":
    unittest.main()
