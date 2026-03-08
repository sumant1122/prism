"use client";

import { FormEvent, useState } from "react";

type ResourceResponse = {
  source: string;
  external_id: string;
  name: string;
  owner: string;
  description: string;
  resource_count: number;
  tags: string[];
  concepts: string[];
  fields: string[];
  relationships_created: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ResourceIngestionPage() {
  const [source, setSource] = useState("github");
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ResourceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!identifier.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/resources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source,
          identifier
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to ingest resource");
      }
      setResult(payload);
      setIdentifier("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid">
      <div className="card">
        <h2 className="page-title">Add Enterprise Resource</h2>
        <p className="page-subtitle">Ingest resource metadata from GitHub, ServiceNow, or manual source connectors.</p>
        <form onSubmit={onSubmit} className="row">
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="github">GitHub</option>
            <option value="servicenow">ServiceNow</option>
            <option value="manual">Manual</option>
          </select>
          <input
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder={source === "github" ? "org/repo" : "resource-id"}
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Adding..." : "Add"}
          </button>
        </form>
        {error && <p style={{ color: "#ad1f1f", marginBottom: 0 }}>{error}</p>}
      </div>
      {result && (
        <div className="card">
          <h3 className="page-title">{result.name}</h3>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className="chip">Source: {result.source}</span>
            <span className="chip">Owner: {result.owner}</span>
            <span className="chip">Resources: {result.resource_count}</span>
          </div>
          <p>
            <strong>External ID:</strong> {result.external_id}
          </p>
          <p>
            <strong>Concepts:</strong> {result.concepts.join(", ") || "None detected yet"}
          </p>
          <p>
            <strong>Fields:</strong> {result.fields.join(", ") || "None detected yet"}
          </p>
          <p>
            <strong>Relationships Created:</strong> {result.relationships_created}
          </p>
        </div>
      )}
    </div>
  );
}

