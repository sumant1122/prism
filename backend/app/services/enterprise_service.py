from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.concept_agent import ConceptAgent
from app.agents.relationship_agent import RelationshipAgent
from app.graph.neo4j_client import GraphRepository
from app.ingestion.connectors import EnterpriseConnectorClient, EnterpriseMetadata


@dataclass(slots=True)
class EnterpriseIngestionResult:
    metadata: EnterpriseMetadata
    concepts: list[str]
    fields: list[str]
    relationships_created: int


class EnterpriseService:
    def __init__(
        self,
        connector_client: EnterpriseConnectorClient,
        graph_repo: GraphRepository,
        concept_agent: ConceptAgent,
        relationship_agent: RelationshipAgent,
        relationship_scan_limit: int = 20,
    ) -> None:
        self._connector_client = connector_client
        self._graph_repo = graph_repo
        self._concept_agent = concept_agent
        self._relationship_agent = relationship_agent
        self._relationship_scan_limit = relationship_scan_limit

    async def ingest_resource(
        self,
        *,
        source: str,
        identifier: str,
        overrides: dict[str, Any] | None = None,
    ) -> EnterpriseIngestionResult:
        metadata = await self._connector_client.fetch(source=source, identifier=identifier, overrides=overrides)
        extraction = self._concept_agent.extract(
            metadata.description,
            fallback_subjects=[metadata.source, *metadata.tags],
        )
        self._graph_repo.upsert_enterprise_resource(metadata, extraction.concepts, extraction.fields)
        relationships = self._discover_relationships(metadata)
        return EnterpriseIngestionResult(
            metadata=metadata,
            concepts=extraction.concepts,
            fields=extraction.fields,
            relationships_created=relationships,
        )

    def _discover_relationships(self, new_resource: EnterpriseMetadata) -> int:
        candidates = self._graph_repo.get_resources_for_relationship_scan(
            exclude_external_id=new_resource.external_id,
            limit=self._relationship_scan_limit,
        )
        source_payload = {
            "title": new_resource.name,
            "description": new_resource.description,
            "subjects": [new_resource.source, *new_resource.tags],
        }
        created = 0
        for candidate in candidates:
            relationship = self._relationship_agent.determine_relationship(source_payload, candidate)
            if not relationship:
                continue
            self._graph_repo.add_resource_relationship(
                source_external_id=new_resource.external_id,
                relation=relationship.relation,
                target_external_id=str(candidate.get("external_id")),
            )
            created += 1
        return created

