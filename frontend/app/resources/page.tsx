"use client";

import { FormEvent, useState } from "react";

type ConceptDetail = {
  name: string;
  category: string;
  summary: string;
  importance: string;
  evidence: string[];
  learn_next: string;
  confidence: number;
};

type LearningPathStep = {
  title: string;
  description: string;
};

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
  repo_summary: string;
  architecture_summary: string;
  concept_details: ConceptDetail[];
  learning_path: LearningPathStep[];
  detected_patterns: string[];
  languages: string[];
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
        body: JSON.stringify({ source, identifier }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to ingest resource");
      }
      setResult(payload);
      setIdentifier("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid">
      <div className="hero-card">
        <div className="hero-copy">
          <span className="eyebrow">Repo Teacher</span>
          <h2 className="hero-title">Learn the computer science inside your GitHub project.</h2>
          <p className="hero-subtitle">
            Paste a GitHub repo and we&apos;ll inspect the codebase structure, README, and key files to explain the
            foundational concepts already showing up in the project.
          </p>
          <div className="row">
            <span className="chip">Contextual learning</span>
            <span className="chip">Code-backed evidence</span>
            <span className="chip">Beginner-friendly explanations</span>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="page-title">Analyze a Repository</h2>
        <p className="page-subtitle">
          Enter `owner/repo` or a full GitHub URL. Start with public repositories for the first MVP.
        </p>
        <form onSubmit={onSubmit} className="row">
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="github">GitHub</option>
            <option value="manual">Manual</option>
          </select>
          <input
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder={source === "github" ? "openai/openai-cookbook or https://github.com/openai/openai-cookbook" : "resource-id"}
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>
        {error && <p style={{ color: "#ad1f1f", marginBottom: 0 }}>{error}</p>}
      </div>

      {result && (
        <div className="grid">
          <div className="grid two">
            <div className="card">
              <span className="eyebrow">Repository Summary</span>
              <h3 className="page-title">{result.external_id}</h3>
              <div className="row" style={{ marginBottom: 10 }}>
                <span className="chip">Source: {result.source}</span>
                <span className="chip">Owner: {result.owner}</span>
                <span className="chip">Stars: {result.resource_count}</span>
              </div>
              <p>{result.repo_summary || result.description || "No repo summary was generated."}</p>
              {result.architecture_summary && (
                <p>
                  <strong>Architecture:</strong> {result.architecture_summary}
                </p>
              )}
            </div>

            <div className="card">
              <span className="eyebrow">Signals</span>
              <h3 className="page-title">What the analyzer picked up</h3>
              <div className="stack">
                <div>
                  <strong>Languages:</strong> {result.languages.join(", ") || "Not detected"}
                </div>
                <div>
                  <strong>Patterns:</strong> {result.detected_patterns.join(", ") || "No strong patterns yet"}
                </div>
                <div>
                  <strong>Fields:</strong> {result.fields.join(", ") || "No categories yet"}
                </div>
                <div>
                  <strong>Graph links created:</strong> {result.relationships_created}
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <span className="eyebrow">Concept Map</span>
            <h3 className="page-title">Computer science concepts found in the repo</h3>
            <div className="concept-grid">
              {(result.concept_details.length ? result.concept_details : []).map((concept) => (
                <article key={concept.name} className="concept-card">
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                    <span className="chip">{concept.category}</span>
                    <span className="confidence">Confidence {Math.round(concept.confidence * 100)}%</span>
                  </div>
                  <h4>{concept.name}</h4>
                  <p>{concept.summary}</p>
                  <p>
                    <strong>Why it matters:</strong> {concept.importance}
                  </p>
                  <p>
                    <strong>Evidence:</strong> {concept.evidence.join(", ") || "No file evidence available"}
                  </p>
                  <p>
                    <strong>Learn next:</strong> {concept.learn_next}
                  </p>
                </article>
              ))}
              {!result.concept_details.length && (
                <article className="concept-card">
                  <h4>Initial concept scan</h4>
                  <p>{result.concepts.join(", ") || "No concept details available yet."}</p>
                </article>
              )}
            </div>
          </div>

          <div className="grid two">
            <div className="card">
              <span className="eyebrow">Learning Path</span>
              <h3 className="page-title">What to study next from this repo</h3>
              <div className="stack">
                {result.learning_path.length ? (
                  result.learning_path.map((step) => (
                    <div key={step.title} className="learning-step">
                      <strong>{step.title}</strong>
                      <p>{step.description}</p>
                    </div>
                  ))
                ) : (
                  <p>No learning path generated yet.</p>
                )}
              </div>
            </div>

            <div className="card">
              <span className="eyebrow">Detected Topics</span>
              <h3 className="page-title">Quick repo tags</h3>
              <div className="row">
                {result.tags.length ? result.tags.map((tag) => <span key={tag} className="chip">{tag}</span>) : <p>No tags available.</p>}
              </div>
              <p style={{ marginTop: 16 }}>
                This is the first MVP pass, so the output is intentionally grounded in observable repo signals rather
                than broad guesses.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
