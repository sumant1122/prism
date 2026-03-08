"use client";

import { FormEvent, useState } from "react";

type ChatResponse = {
  answer: string;
  confidence: number;
  citations: string[];
  evidence_nodes: Array<{ id: string; label: string; type: string }>;
  evidence_edges: Array<{ id: string; source: string; target: string; type: string }>;
  context_size: { nodes: number; edges: number };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("auto");
  const [k, setK] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResponse | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, scope, k })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Unable to query graph");
      }
      setResult(payload);
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
        <h2 style={{ marginTop: 0 }}>Graph Chat</h2>
        <form onSubmit={onSubmit} className="grid">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What are the most connected software engineering books in my graph?"
            style={{ minHeight: 110, padding: 10, borderRadius: 10, border: "1px solid #c7cfc7" }}
          />
          <div style={{ display: "flex", gap: 10 }}>
            <select
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #c7cfc7" }}
            >
              <option value="auto">Auto scope</option>
              <option value="book">Books</option>
              <option value="author">Authors</option>
              <option value="concept">Concepts</option>
              <option value="field">Fields</option>
            </select>
            <input
              type="number"
              min={5}
              max={100}
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
              style={{ width: 110 }}
            />
            <button type="submit" disabled={loading}>
              {loading ? "Thinking..." : "Ask"}
            </button>
          </div>
        </form>
        {error && <p style={{ color: "#ad1f1f" }}>{error}</p>}
      </div>

      {result && (
        <div className="grid two">
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Answer</h3>
            <p>{result.answer}</p>
            <p>
              <strong>Confidence:</strong> {(result.confidence * 100).toFixed(0)}%
            </p>
            <p>
              <strong>Context:</strong> {result.context_size.nodes} nodes, {result.context_size.edges} edges
            </p>
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Evidence Nodes</h3>
            <p>
              {result.evidence_nodes
                .slice(0, 8)
                .map((node) => `${node.label} [${node.type}]`)
                .join(", ") || "No evidence nodes returned."}
            </p>
            <p>
              <strong>Citations:</strong> {result.citations.join(", ") || "None"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

