from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.insight_agent import InsightAgent
from app.graph.neo4j_client import GraphRepository


class GraphInsightEngine:
    def __init__(self, repo: GraphRepository, insight_agent: InsightAgent | None = None) -> None:
        self._repo = repo
        self._insight_agent = insight_agent or InsightAgent()

    def get_central_resources(self) -> dict[str, Any]:
        ranked = self._repo.get_central_resources()
        names = [row["name"] for row in ranked if row.get("name")]
        return {
            "central_resources": ranked,
            "summary": f"Most central resources: {', '.join(names[:3])}" if names else "No central resources yet.",
            "evidence": {
                "nodes": self._repo.get_resource_nodes_by_names(names[:5]),
                "edges": self._repo.get_resource_relationship_edges(limit=20),
            },
        }

    def detect_clusters(self) -> dict[str, Any]:
        clusters = self._repo.detect_clusters()
        preview = clusters[0]["resources"][:5] if clusters else []
        return {
            "clusters": clusters,
            "cluster_count": len(clusters),
            "evidence": {
                "nodes": self._repo.get_resource_nodes_by_names(preview),
                "edges": self._repo.get_resource_relationship_edges(limit=20),
            },
        }

    def detect_missing_topics(self) -> dict[str, Any]:
        missing = self._repo.detect_missing_topics()
        fields = [row["field"] for row in missing[:6] if row.get("field")]
        return {
            "missing_topics": missing,
            "summary": "Domains with low coverage indicate blind spots.",
            "evidence": {"nodes": self._repo.get_field_nodes_by_names(fields), "edges": []},
        }

    def get_graph_stats(self) -> dict[str, Any]:
        stats = self._repo.get_graph_stats()
        return {
            **stats,
            "summary": (
                f"Graph has {stats['resources']} resources across {stats['platforms']} platforms, "
                f"{stats['concepts']} concepts, and {stats['resource_edges']} inter-resource links."
            ),
        }

    def get_coverage(self) -> dict[str, Any]:
        return {
            "top_fields": self._repo.get_field_coverage(),
            "top_concepts": self._repo.get_top_concepts(),
            "unlinked_resources": self._repo.get_unlinked_resources(),
        }

    def compute_quality_scores(self, stats: dict[str, Any], clusters: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
        resources = int(stats.get("resources", 0))
        density = float(stats.get("inter_resource_relationship_density", 0.0))
        unlinked = len(coverage.get("unlinked_resources", []))
        largest_cluster = len(clusters["clusters"][0].get("resources", [])) if clusters.get("clusters") else 0
        relationship_quality = max(0, min(100, int((density * 250) + (resources * 2))))
        concept_coverage = max(0, min(100, int((int(stats.get("concepts", 0)) / max(1, resources)) * 20)))
        cluster_cohesion = max(0, min(100, int((largest_cluster / max(1, resources)) * 100)))
        link_completeness = max(0, min(100, int((1 - (unlinked / max(1, resources))) * 100)))
        overall = int((relationship_quality + concept_coverage + cluster_cohesion + link_completeness) / 4)
        return {
            "overall_score": overall,
            "breakdown": {
                "relationship_quality": relationship_quality,
                "concept_coverage": concept_coverage,
                "cluster_cohesion": cluster_cohesion,
                "link_completeness": link_completeness,
            },
        }

    def build_recommendations(self, central: dict[str, Any], missing: dict[str, Any], coverage: dict[str, Any], sparse: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recs: list[dict[str, Any]] = []
        unlinked = coverage.get("unlinked_resources", [])
        if unlinked:
            names = [row.get("name") for row in unlinked[:3] if row.get("name")]
            recs.append({"action": f"Connect isolated resources: {', '.join(names)}.", "effort": "Quick win", "type": "connectivity"})
        missing_fields = [row.get("field") for row in missing.get("missing_topics", [])[:3] if row.get("field")]
        if missing_fields:
            recs.append({"action": f"Increase coverage in: {', '.join(missing_fields)}.", "effort": "Medium", "type": "coverage"})
        ranked = central.get("central_resources", [])
        if ranked:
            recs.append({"action": f"Expand dependencies around '{ranked[0].get('name')}'.", "effort": "Deep work", "type": "expansion"})
        if sparse:
            s = sparse[0]
            recs.append({"action": f"Bridge '{s['field_a']}' and '{s['field_b']}' with shared resources.", "effort": "Medium", "type": "bridge"})
        if not recs:
            recs.append({"action": "Ingest more resources across platforms to improve signal quality.", "effort": "Medium", "type": "growth"})
        return recs

    def build_time_delta(self, current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
        if not previous:
            return {"has_previous": False, "summary": "Baseline snapshot created.", "delta": {}, "previous_snapshot_at": None}
        delta = {
            "resources": int(current.get("resources", 0)) - int(previous.get("resources", 0)),
            "concepts": int(current.get("concepts", 0)) - int(previous.get("concepts", 0)),
            "resource_edges": int(current.get("resource_edges", 0)) - int(previous.get("resource_edges", 0)),
            "density": round(
                float(current.get("inter_resource_relationship_density", 0.0))
                - float(previous.get("inter_resource_relationship_density", 0.0)),
                4,
            ),
        }
        return {
            "has_previous": True,
            "summary": (
                f"Since last snapshot: resources {delta['resources']:+d}, "
                f"relationships {delta['resource_edges']:+d}, density {delta['density']:+.4f}."
            ),
            "delta": delta,
            "previous_snapshot_at": previous.get("created_at"),
        }

    def build_insight_bundle(self) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        central = self._safe(self.get_central_resources, {"central_resources": [], "summary": "Unavailable", "evidence": {"nodes": [], "edges": []}})
        clusters = self._safe(self.detect_clusters, {"clusters": [], "cluster_count": 0, "evidence": {"nodes": [], "edges": []}})
        missing = self._safe(self.detect_missing_topics, {"missing_topics": [], "summary": "Unavailable", "evidence": {"nodes": [], "edges": []}})
        stats = self._safe(self.get_graph_stats, {"resources": 0, "platforms": 0, "concepts": 0, "fields": 0, "resource_edges": 0, "inter_resource_relationship_density": 0.0, "summary": "Unavailable"})
        coverage = self._safe(self.get_coverage, {"top_fields": [], "top_concepts": [], "unlinked_resources": []})
        sparse = self._safe(self._repo.detect_sparse_bridges, [])
        overlap = self._safe(self._repo.get_overlap_contradiction_summary, {"overlap_count": 0, "contradiction_count": 0, "samples": []})
        reading_paths = self._safe(self._repo.get_field_reading_paths, [])
        dashboards = self._safe(self._repo.get_field_dashboards, [])
        quality = self.compute_quality_scores(stats, clusters, coverage)
        previous_rows = self._safe(self._repo.get_latest_insight_snapshots, [], limit=1)
        previous = previous_rows[0] if previous_rows else None
        time_delta = self.build_time_delta(stats, previous)
        recommendations = self.build_recommendations(central, missing, coverage, sparse)

        narrative = self._safe(
            self._insight_agent.synthesize,
            {
                "summary": "Narrative unavailable for this run.",
                "key_findings": [],
                "recommended_actions": [],
                "graph_health_score": quality["overall_score"],
            },
            {
                "central_resources": central,
                "clusters": clusters,
                "missing_topics": missing,
                "graph_stats": stats,
                "coverage": coverage,
                "quality_scores": quality,
                "time_delta": time_delta,
                "sparse_bridges": sparse,
                "overlap_contradiction": overlap,
                "reading_paths": reading_paths,
                "field_dashboards": dashboards,
                "recommendations": recommendations,
            },
        )
        self._safe(self._repo.save_insight_snapshot, None, stats=stats, overall_score=quality["overall_score"])

        return {
            "central_resources": central,
            "clusters": clusters,
            "missing_topics": missing,
            "graph_stats": stats,
            "coverage": coverage,
            "recommendations": recommendations,
            "narrative": narrative,
            "time_delta": time_delta,
            "quality_scores": quality,
            "reading_paths": reading_paths,
            "overlap_contradiction": overlap,
            "sparse_bridges": sparse,
            "field_dashboards": dashboards,
            "freshness": {
                "generated_at": generated_at,
                "confidence": {"score": 0.76 if narrative.get("summary") else 0.55, "label": "medium"},
                "context_size": {
                    "resources": stats.get("resources", 0),
                    "concepts": stats.get("concepts", 0),
                    "edges": stats.get("resource_edges", 0),
                },
            },
        }

    def _safe(self, fn, default, *args, **kwargs):  # noqa: ANN001
        try:
            return fn(*args, **kwargs)
        except Exception:  # noqa: BLE001
            return default

