from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError, Neo4jError

from app.ingestion.connectors import EnterpriseMetadata


class GraphRepository:
    def __init__(self, uri: str, username: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self._driver.close()

    def ensure_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT resource_external_unique IF NOT EXISTS FOR (r:Resource) REQUIRE r.external_id IS UNIQUE",
            "CREATE CONSTRAINT platform_name_unique IF NOT EXISTS FOR (p:Platform) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT concept_name_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT field_name_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.name IS UNIQUE",
        ]
        with self._driver.session() as session:
            for statement in constraints:
                session.run(statement).consume()

    def upsert_enterprise_resource(
        self,
        metadata: EnterpriseMetadata,
        concepts: list[str],
        fields: list[str],
    ) -> None:
        query = """
        MERGE (r:Resource {external_id: $external_id})
        SET r.name = $name,
            r.description = $description,
            r.owner = $owner,
            r.resource_count = $resource_count,
            r.source = $source,
            r.tags = $tags
        MERGE (p:Platform {name: $source})
        MERGE (r)-[:BELONGS_TO]->(p)
        WITH r, $concepts AS concepts, $fields AS fields
        FOREACH (concept IN concepts |
            MERGE (c:Concept {name: concept})
            MERGE (r)-[:MENTIONS]->(c)
        )
        FOREACH (field IN fields |
            MERGE (f:Field {name: field})
            MERGE (r)-[:BELONGS_TO]->(f)
        )
        """
        with self._driver.session() as session:
            session.run(
                query,
                external_id=metadata.external_id,
                name=metadata.name,
                description=metadata.description,
                owner=metadata.owner,
                resource_count=metadata.resource_count,
                source=metadata.source,
                tags=metadata.tags,
                concepts=concepts,
                fields=fields,
            ).consume()

    def get_resources_for_relationship_scan(self, exclude_external_id: str, limit: int) -> list[dict[str, Any]]:
        query = """
        MATCH (r:Resource)
        WHERE r.external_id <> $exclude_external_id
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(f:Field)
        RETURN r.external_id AS external_id,
               r.name AS title,
               r.description AS description,
               collect(DISTINCT f.name) AS subjects
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, exclude_external_id=exclude_external_id, limit=limit).data()

    def add_resource_relationship(self, source_external_id: str, relation: str, target_external_id: str) -> None:
        if relation not in {"RELATED_TO", "INFLUENCED_BY", "CONTRADICTS", "EXPANDS", "BELONGS_TO"}:
            return
        query = f"""
        MATCH (source:Resource {{external_id: $source_external_id}})
        MATCH (target:Resource {{external_id: $target_external_id}})
        MERGE (source)-[r:{relation}]->(target)
        RETURN type(r) AS relation
        """
        with self._driver.session() as session:
            session.run(
                query,
                source_external_id=source_external_id,
                target_external_id=target_external_id,
            ).consume()

    def get_graph(self) -> dict[str, list[dict[str, Any]]]:
        nodes_query = """
        MATCH (n)
        WHERE NOT n:InsightSnapshot
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        """
        edges_query = """
        MATCH (a)-[r]->(b)
        WHERE NOT a:InsightSnapshot AND NOT b:InsightSnapshot
        RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type
        """
        with self._driver.session() as session:
            nodes = [
                {
                    "id": row["id"],
                    "label": row["props"].get("name") or row["props"].get("external_id") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": self._to_json_safe(row["props"]),
                }
                for row in session.run(nodes_query).data()
            ]
            edges = [row for row in session.run(edges_query).data()]
            return {"nodes": nodes, "edges": edges}

    def get_central_resources(self, limit: int = 5) -> list[dict[str, Any]]:
        gds_query = """
        CALL gds.graph.project.cypher(
            'resourceGraph',
            'MATCH (r:Resource) RETURN id(r) AS id',
            'MATCH (a:Resource)-[r]->(b:Resource) RETURN id(a) AS source, id(b) AS target'
        )
        YIELD graphName
        CALL gds.pageRank.stream(graphName)
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).name AS name, score
        ORDER BY score DESC
        LIMIT $limit
        """
        cleanup_query = "CALL gds.graph.drop('resourceGraph', false)"
        fallback_query = """
        MATCH (r:Resource)
        OPTIONAL MATCH (r)-[rel]-(:Resource)
        WITH r, count(rel) AS resourceLinks
        OPTIONAL MATCH (r)-[:MENTIONS]->(c:Concept)
        WITH r, resourceLinks, count(DISTINCT c) AS conceptLinks
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(f:Field)
        WITH r, resourceLinks, conceptLinks, count(DISTINCT f) AS fieldLinks
        RETURN r.name AS name, (resourceLinks * 2.0 + conceptLinks + fieldLinks * 0.8) AS score
        ORDER BY score DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            try:
                rows = session.run(gds_query, limit=limit).data()
                session.run(cleanup_query).consume()
                return rows
            except (Neo4jError, CypherSyntaxError):
                return session.run(fallback_query, limit=limit).data()

    def detect_clusters(self) -> list[dict[str, Any]]:
        gds_query = """
        CALL gds.graph.project.cypher(
            'clusterGraph',
            'MATCH (r:Resource) RETURN id(r) AS id',
            'MATCH (a:Resource)-[r]->(b:Resource) RETURN id(a) AS source, id(b) AS target'
        )
        YIELD graphName
        CALL gds.louvain.stream(graphName)
        YIELD nodeId, communityId
        RETURN communityId, collect(gds.util.asNode(nodeId).name) AS resources
        ORDER BY size(resources) DESC
        """
        cleanup_query = "CALL gds.graph.drop('clusterGraph', false)"
        fallback_query = """
        MATCH (r:Resource)-[:BELONGS_TO]->(f:Field)
        RETURN f.name AS communityId, collect(DISTINCT r.name) AS resources
        ORDER BY size(resources) DESC
        """
        with self._driver.session() as session:
            try:
                rows = session.run(gds_query).data()
                session.run(cleanup_query).consume()
                return rows
            except (Neo4jError, CypherSyntaxError):
                return session.run(fallback_query).data()

    def detect_missing_topics(self, threshold: int = 1) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)
        OPTIONAL MATCH (r:Resource)-[:BELONGS_TO]->(f)
        WITH f.name AS field, count(DISTINCT r) AS resourceCount
        WHERE resourceCount <= $threshold
        RETURN field, resourceCount
        ORDER BY resourceCount ASC, field ASC
        """
        with self._driver.session() as session:
            return session.run(query, threshold=threshold).data()

    def get_graph_stats(self) -> dict[str, Any]:
        query = """
        OPTIONAL MATCH (r:Resource)
        WITH count(DISTINCT r) AS resources
        OPTIONAL MATCH (p:Platform)
        WITH resources, count(DISTINCT p) AS platforms
        OPTIONAL MATCH (c:Concept)
        WITH resources, platforms, count(DISTINCT c) AS concepts
        OPTIONAL MATCH (f:Field)
        WITH resources, platforms, concepts, count(DISTINCT f) AS fields
        OPTIONAL MATCH (:Resource)-[rel]->(:Resource)
        WITH resources, platforms, concepts, fields, count(DISTINCT rel) AS resourceEdges
        RETURN resources, platforms, concepts, fields, resourceEdges
        """
        with self._driver.session() as session:
            row = session.run(query).single()
            if not row:
                return {
                    "resources": 0,
                    "platforms": 0,
                    "concepts": 0,
                    "fields": 0,
                    "resource_edges": 0,
                    "inter_resource_relationship_density": 0.0,
                }
            resources = int(row["resources"] or 0)
            edges = int(row["resourceEdges"] or 0)
            max_edges = max(1, resources * max(resources - 1, 1))
            density = float(edges / max_edges) if resources > 1 else 0.0
            return {
                "resources": resources,
                "platforms": int(row["platforms"] or 0),
                "concepts": int(row["concepts"] or 0),
                "fields": int(row["fields"] or 0),
                "resource_edges": edges,
                "inter_resource_relationship_density": round(density, 4),
            }

    def get_field_coverage(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)
        OPTIONAL MATCH (r:Resource)-[:BELONGS_TO]->(f)
        RETURN f.name AS field, count(DISTINCT r) AS resourceCount
        ORDER BY resourceCount DESC, field ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_top_concepts(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (c:Concept)<-[:MENTIONS]-(r:Resource)
        RETURN c.name AS concept, count(DISTINCT r) AS resourceCount
        ORDER BY resourceCount DESC, concept ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_unlinked_resources(self, limit: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (r:Resource)
        WHERE NOT (r)-[:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Resource)
        RETURN r.name AS name
        ORDER BY name ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_resource_relationship_edges(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
        MATCH (a:Resource)-[r:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(b:Resource)
        RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit).data()

    def get_resource_nodes_by_names(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        query = """
        UNWIND $names AS resource_name
        MATCH (r:Resource {name: resource_name})
        RETURN elementId(r) AS id, r.name AS label, 'resource' AS type
        """
        with self._driver.session() as session:
            return session.run(query, names=names).data()

    def get_field_nodes_by_names(self, fields: list[str]) -> list[dict[str, Any]]:
        if not fields:
            return []
        query = """
        UNWIND $fields AS field_name
        MATCH (f:Field {name: field_name})
        RETURN elementId(f) AS id, f.name AS label, 'field' AS type
        """
        with self._driver.session() as session:
            return session.run(query, fields=fields).data()

    def get_field_reading_paths(self, limit_fields: int = 4, path_len: int = 4) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)<-[:BELONGS_TO]-(r:Resource)
        OPTIONAL MATCH (r)-[rel:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Resource)
        WITH f, r, count(DISTINCT rel) AS relScore
        ORDER BY f.name ASC, relScore DESC, r.name ASC
        WITH f, collect({name: r.name, score: relScore})[..$path_len] AS path
        WHERE size(path) >= 2
        RETURN f.name AS field, path
        ORDER BY size(path) DESC, field ASC
        LIMIT $limit_fields
        """
        with self._driver.session() as session:
            return session.run(query, limit_fields=limit_fields, path_len=path_len).data()

    def get_overlap_contradiction_summary(self) -> dict[str, Any]:
        query = """
        MATCH (:Resource)-[rel:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(:Resource)
        RETURN
            count(CASE WHEN type(rel) IN ['RELATED_TO', 'INFLUENCED_BY', 'EXPANDS'] THEN 1 END) AS overlapCount,
            count(CASE WHEN type(rel) = 'CONTRADICTS' THEN 1 END) AS contradictionCount
        """
        sample_query = """
        MATCH (a:Resource)-[rel:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]->(b:Resource)
        RETURN a.name AS source, type(rel) AS relation, b.name AS target
        LIMIT 12
        """
        with self._driver.session() as session:
            row = session.run(query).single()
            samples = session.run(sample_query).data()
            return {
                "overlap_count": int(row["overlapCount"] or 0) if row else 0,
                "contradiction_count": int(row["contradictionCount"] or 0) if row else 0,
                "samples": samples,
            }

    def detect_sparse_bridges(self, limit: int = 8, max_fields: int = 10) -> list[dict[str, Any]]:
        query = """
        MATCH (f:Field)<-[:BELONGS_TO]-(r:Resource)
        WITH f, count(DISTINCT r) AS resourceCount
        WHERE resourceCount > 0
        ORDER BY resourceCount DESC, f.name ASC
        LIMIT $max_fields
        WITH collect({name: f.name, count: resourceCount}) AS fieldRows
        UNWIND fieldRows AS fa
        UNWIND fieldRows AS fb
        WITH fa, fb
        WHERE fa.name < fb.name
        CALL {
            WITH fa, fb
            MATCH (x:Resource)-[rel:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(y:Resource)
            WHERE (x)-[:BELONGS_TO]->(:Field {name: fa.name})
              AND (y)-[:BELONGS_TO]->(:Field {name: fb.name})
            RETURN count(DISTINCT rel) AS crossLinks
        }
        WITH fa, fb, crossLinks
        WHERE crossLinks = 0
        RETURN fa.name AS field_a, fb.name AS field_b, fa.count AS resources_a, fb.count AS resources_b
        ORDER BY (fa.count + fb.count) DESC, field_a ASC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return session.run(query, limit=limit, max_fields=max_fields).data()

    def get_field_dashboards(self, limit: int = 5) -> list[dict[str, Any]]:
        top_fields = self.get_field_coverage(limit=limit)
        dashboards: list[dict[str, Any]] = []
        with self._driver.session() as session:
            for field in top_fields:
                field_name = field["field"]
                resources_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(r:Resource)
                OPTIONAL MATCH (r)-[rel:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Resource)
                RETURN r.name AS name, count(DISTINCT rel) AS relationCount
                ORDER BY relationCount DESC, name ASC
                LIMIT 5
                """
                concepts_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(r:Resource)-[:MENTIONS]->(c:Concept)
                RETURN c.name AS concept, count(DISTINCT r) AS resourceCount
                ORDER BY resourceCount DESC, concept ASC
                LIMIT 5
                """
                isolated_query = """
                MATCH (f:Field {name: $field_name})<-[:BELONGS_TO]-(r:Resource)
                WHERE NOT (r)-[:RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(:Resource)
                RETURN r.name AS name
                LIMIT 5
                """
                dashboards.append(
                    {
                        "field": field_name,
                        "resource_count": field["resourceCount"],
                        "top_resources": session.run(resources_query, field_name=field_name).data(),
                        "top_concepts": session.run(concepts_query, field_name=field_name).data(),
                        "isolated_resources": session.run(isolated_query, field_name=field_name).data(),
                        "unanswered_questions": [
                            f"Which resource should bridge '{field_name}' with adjacent domains?",
                            f"Where are ownership gaps inside '{field_name}'?",
                        ],
                    }
                )
        return dashboards

    def get_latest_insight_snapshots(self, limit: int = 2) -> list[dict[str, Any]]:
        query = """
        MATCH (s:InsightSnapshot)
        RETURN s.created_at AS created_at,
               s.resources AS resources,
               s.platforms AS platforms,
               s.concepts AS concepts,
               s.fields AS fields,
               s.resource_edges AS resource_edges,
               s.inter_resource_relationship_density AS inter_resource_relationship_density,
               s.overall_score AS overall_score
        ORDER BY s.created_at DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            return [self._to_json_safe(row) for row in session.run(query, limit=limit).data()]

    def save_insight_snapshot(self, stats: dict[str, Any], overall_score: int) -> None:
        query = """
        CREATE (s:InsightSnapshot {
            id: randomUUID(),
            created_at: datetime(),
            resources: $resources,
            platforms: $platforms,
            concepts: $concepts,
            fields: $fields,
            resource_edges: $resource_edges,
            inter_resource_relationship_density: $inter_resource_relationship_density,
            overall_score: $overall_score
        })
        """
        with self._driver.session() as session:
            session.run(
                query,
                resources=int(stats.get("resources", 0)),
                platforms=int(stats.get("platforms", 0)),
                concepts=int(stats.get("concepts", 0)),
                fields=int(stats.get("fields", 0)),
                resource_edges=int(stats.get("resource_edges", 0)),
                inter_resource_relationship_density=float(stats.get("inter_resource_relationship_density", 0.0)),
                overall_score=int(overall_score),
            ).consume()

    def get_chat_subgraph(self, question: str, scope: str = "auto", k: int = 20) -> dict[str, list[dict[str, Any]]]:
        terms = [token.strip().lower() for token in question.split() if len(token.strip()) >= 3][:12]
        label_filter = {
            "resource": "Resource",
            "platform": "Platform",
            "concept": "Concept",
            "field": "Field",
        }.get(scope.strip().lower())
        with self._driver.session() as session:
            if label_filter:
                seed_query = """
                MATCH (n)
                WHERE $label IN labels(n)
                  AND any(term IN $terms WHERE toLower(coalesce(n.name, n.description, "")) CONTAINS term)
                RETURN elementId(n) AS id
                LIMIT $k
                """
            else:
                seed_query = """
                MATCH (n)
                WHERE any(term IN $terms WHERE toLower(coalesce(n.name, n.description, "")) CONTAINS term)
                RETURN elementId(n) AS id
                LIMIT $k
                """
            seed_ids = [row["id"] for row in session.run(seed_query, terms=terms, k=k, label=label_filter).data()] if terms else []
            if not seed_ids:
                seed_ids = [row["id"] for row in session.run("MATCH (r:Resource) RETURN elementId(r) AS id LIMIT $k", k=k).data()]
            if not seed_ids:
                return {"nodes": [], "edges": []}

            neighborhood_query = """
            UNWIND $seed_ids AS sid
            MATCH (s) WHERE elementId(s) = sid
            OPTIONAL MATCH (s)-[:MENTIONS|BELONGS_TO|RELATED_TO|INFLUENCED_BY|CONTRADICTS|EXPANDS]-(n)
            WITH collect(DISTINCT elementId(s)) + collect(DISTINCT elementId(n)) AS rawNodeIds
            UNWIND rawNodeIds AS nodeId
            WITH DISTINCT nodeId WHERE nodeId IS NOT NULL
            RETURN nodeId
            LIMIT $node_limit
            """
            node_ids = [row["nodeId"] for row in session.run(neighborhood_query, seed_ids=seed_ids, node_limit=max(k * 3, 20))]
            nodes_query = """
            UNWIND $node_ids AS nid
            MATCH (n) WHERE elementId(n) = nid
            RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
            """
            edges_query = """
            UNWIND $node_ids AS nid
            MATCH (a) WHERE elementId(a) = nid
            MATCH (a)-[rel]->(b) WHERE elementId(b) IN $node_ids
            RETURN DISTINCT elementId(rel) AS id, elementId(a) AS source, elementId(b) AS target, type(rel) AS type
            LIMIT $edge_limit
            """
            nodes = [
                {
                    "id": row["id"],
                    "label": row["props"].get("name") or row["props"].get("external_id") or "Unknown",
                    "type": (row["labels"][0].lower() if row["labels"] else "unknown"),
                    "properties": self._to_json_safe(row["props"]),
                }
                for row in session.run(nodes_query, node_ids=node_ids).data()
            ]
            edges = session.run(edges_query, node_ids=node_ids, edge_limit=max(k * 6, 30)).data()
            return {"nodes": nodes, "edges": edges}

    def _to_json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._to_json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        return str(value)

