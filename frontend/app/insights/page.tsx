"use client";

import { useEffect, useState } from "react";

type InsightsResponse = {
  central_resources: {
    summary: string;
    central_resources: Array<{ name: string; score: number }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
  };
  clusters: {
    cluster_count: number;
    clusters: Array<{ communityId: string; resources: string[] }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
  };
  missing_topics: {
    summary: string;
    missing_topics: Array<{ field: string; resourceCount: number }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
  };
  graph_stats: {
    resources: number;
    platforms: number;
    concepts: number;
    fields: number;
    resource_edges: number;
    inter_resource_relationship_density: number;
    summary: string;
  };
  coverage: {
    top_fields: Array<{ field: string; resourceCount: number }>;
    top_concepts: Array<{ concept: string; resourceCount: number }>;
    unlinked_resources: Array<{ name: string }>;
  };
  recommendations: Array<{ action: string; effort: string; type: string }>;
  narrative: {
    summary: string;
    key_findings: string[];
    recommended_actions: string[];
    graph_health_score: number;
  };
  time_delta: {
    has_previous: boolean;
    summary: string;
    previous_snapshot_at?: string | null;
  };
  quality_scores: {
    overall_score: number;
    breakdown: {
      relationship_quality: number;
      concept_coverage: number;
      cluster_cohesion: number;
      link_completeness: number;
    };
  };
  reading_paths: Array<{
    field: string;
    path: Array<{ name: string; score: number }>;
  }>;
  overlap_contradiction: {
    overlap_count: number;
    contradiction_count: number;
    samples: Array<{ source: string; relation: string; target: string }>;
  };
  sparse_bridges: Array<{ field_a: string; field_b: string; resources_a: number; resources_b: number }>;
  field_dashboards: Array<{
    field: string;
    resource_count: number;
    top_resources: Array<{ name: string }>;
    top_concepts: Array<{ concept: string }>;
    isolated_resources: Array<{ name: string }>;
    unanswered_questions: string[];
  }>;
  freshness: {
    generated_at: string;
    confidence: { score: number; label: string };
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function InsightsPage() {
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch(`${API_BASE}/insights`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ?? "Failed to load insights.");
        }
        setData(payload as InsightsResponse);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load insights.");
      }
    };
    void load();
  }, []);

  if (error) {
    return <div className="card">Insights error: {error}</div>;
  }

  if (!data) {
    return <div className="card">Loading insights...</div>;
  }

  return (
    <div className="grid two">
      <div className="card">
        <h3 className="page-title">Graph Health</h3>
        <p style={{ fontSize: 28, margin: "6px 0" }}>
          {data.quality_scores?.overall_score ?? data.narrative.graph_health_score}/100
        </p>
        <p>{data.graph_stats.summary}</p>
        <p>
          <strong>Freshness:</strong> {new Date(data.freshness.generated_at).toLocaleString()}
        </p>
        <p>
          <strong>Confidence:</strong> {data.freshness.confidence.label} (
          {(data.freshness.confidence.score * 100).toFixed(0)}%)
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">LLM Summary</h3>
        <p>{data.narrative.summary}</p>
        <p>{data.time_delta.summary}</p>
      </div>
      <div className="card">
        <h3 className="page-title">Central Resources</h3>
        <p>{data.central_resources.summary}</p>
        <p>
          {data.central_resources.central_resources
            .map((r) => `${r.name} (${r.score.toFixed(2)})`)
            .join(", ") || "No centrality data yet."}
        </p>
        <p>
          <strong>Evidence:</strong>{" "}
          {data.central_resources.evidence?.nodes?.map((n) => n.label).join(", ") || "No evidence"}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Clusters</h3>
        <p>Detected {data.clusters.cluster_count} groups.</p>
        <p>
          {data.clusters.clusters
            .slice(0, 3)
            .map((cluster) => `${cluster.communityId}: ${cluster.resources.slice(0, 3).join(", ")}`)
            .join(" | ") || "No cluster data yet."}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Missing Topics</h3>
        <p>{data.missing_topics.summary}</p>
        <p>
          {data.missing_topics.missing_topics
            .map((topic) => `${topic.field} (${topic.resourceCount})`)
            .join(", ") || "No gaps found."}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Coverage</h3>
        <p>
          <strong>Top fields:</strong>{" "}
          {data.coverage.top_fields.map((f) => `${f.field} (${f.resourceCount})`).join(", ") || "N/A"}
        </p>
        <p>
          <strong>Top concepts:</strong>{" "}
          {data.coverage.top_concepts
            .map((c) => `${c.concept} (${c.resourceCount})`)
            .join(", ") || "N/A"}
        </p>
        <p>
          <strong>Unlinked resources:</strong>{" "}
          {data.coverage.unlinked_resources.map((r) => r.name).join(", ") || "None"}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Recommendations</h3>
        <p>
          {data.recommendations
            .map((rec) => `[${rec.effort}] ${rec.action}`)
            .join(" ") || "No recommendations yet."}
        </p>
        <p>{data.narrative.recommended_actions?.join(" ")}</p>
      </div>
      <div className="card">
        <h3 className="page-title">Quality Breakdown</h3>
        <p>Relationship quality: {data.quality_scores.breakdown.relationship_quality}</p>
        <p>Concept coverage: {data.quality_scores.breakdown.concept_coverage}</p>
        <p>Cluster cohesion: {data.quality_scores.breakdown.cluster_cohesion}</p>
        <p>Link completeness: {data.quality_scores.breakdown.link_completeness}</p>
      </div>
      <div className="card">
        <h3 className="page-title">Reading Paths</h3>
        <p>
          {data.reading_paths
            .map((path) => `${path.field}: ${path.path.map((item) => item.name).join(" -> ")}`)
            .join(" | ") || "No reading paths yet."}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Overlap vs Contradictions</h3>
        <p>
          Overlap links: {data.overlap_contradiction.overlap_count}, Contradictions:{" "}
          {data.overlap_contradiction.contradiction_count}
        </p>
        <p>
          {data.overlap_contradiction.samples
            .slice(0, 4)
            .map((s) => `${s.source} ${s.relation} ${s.target}`)
            .join(" | ") || "No relationship samples yet."}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Sparse Bridges</h3>
        <p>
          {data.sparse_bridges
            .map((b) => `${b.field_a} <-> ${b.field_b}`)
            .join(", ") || "No sparse bridge zones detected."}
        </p>
      </div>
      <div className="card">
        <h3 className="page-title">Field Dashboards</h3>
        <p>
          {data.field_dashboards
            .slice(0, 3)
            .map(
              (d) =>
                `${d.field}: resources(${d.top_resources.map((r) => r.name).join(", ")}), concepts(${d.top_concepts
                  .map((c) => c.concept)
                  .join(", ")})`
            )
            .join(" | ") || "No field dashboards yet."}
        </p>
      </div>
    </div>
  );
}
