"use client";

import { FormEvent, useState } from "react";

import type { RepoAnalysisResponse } from "@/lib/types";

const sampleRepos = [
  "vercel/next.js",
  "openai/openai-cookbook",
  "tailwindlabs/tailwindcss",
  "supabase/supabase",
];

const featureList = [
  "Reads public GitHub repos without needing a separate backend service",
  "Explains the CS concepts already showing up in the code",
  "Connects each concept to real file evidence and a learning next step",
];

const workflowSteps = [
  {
    title: "Ingest the repo",
    body: "We pull the README, language mix, tree structure, and a handful of key files from GitHub.",
  },
  {
    title: "Detect concepts",
    body: "A server-side analysis pass maps repo signals to software engineering and computer science ideas.",
  },
  {
    title: "Teach through context",
    body: "The result is written like a mentor: what the concept is, why it matters here, and what to study next.",
  },
];

export default function RepoTeacherExperience() {
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RepoAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitAnalysis(repoValue: string) {
    const trimmed = repoValue.trim();
    if (!trimmed) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: trimmed }),
      });
      const payload = (await response.json()) as RepoAnalysisResponse & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Unable to analyze that repository.");
      }
      setResult(payload);
      setIdentifier(trimmed);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await submitAnalysis(identifier);
  }

  return (
    <div className="experience-shell">
      <section className="hero-panel" id="top">
        <div className="hero-column">
          <span className="hero-kicker">Single-app AI repo teacher</span>
          <h1 className="hero-heading">Turn any public GitHub repo into a guided CS lesson.</h1>
          <p className="hero-copy">
            Repo Teacher gives beginners something better than generic theory: a breakdown of the concepts already
            living inside their own project, explained in plain language with code evidence.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="#analyzer">
              Analyze a repo
            </a>
            <a className="secondary-link" href="#how-it-works">
              See how it works
            </a>
          </div>
          <div className="hero-proof">
            {featureList.map((item) => (
              <div key={item} className="proof-card">
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="hero-spotlight">
          <div className="spotlight-card spotlight-card-primary">
            <span className="eyebrow">What users learn</span>
            <h2>Architecture, async flow, state, testing, data modeling, and more.</h2>
            <p>
              The analysis is built to feel like a senior engineer walking through the repo with you, not a sterile
              machine summary.
            </p>
          </div>
          <div className="spotlight-metrics">
            <div className="metric-tile">
              <strong>Repo-first</strong>
              <span>Learning starts with code the user already cares about.</span>
            </div>
            <div className="metric-tile">
              <strong>Server-side AI</strong>
              <span>Keys stay safe and the client stays lightweight.</span>
            </div>
            <div className="metric-tile">
              <strong>Evidence-backed</strong>
              <span>Each concept points back to real repo structure and files.</span>
            </div>
          </div>
        </div>
      </section>

      <section className="analysis-stage" id="analyzer">
        <div className="analysis-shell">
          <div className="analysis-intro">
            <span className="eyebrow">Analyzer</span>
            <h2 className="section-title">Paste a repo. Get a rich breakdown.</h2>
            <p className="section-copy">
              Start with public repositories. Add a `GITHUB_TOKEN` if you want higher GitHub API limits, and an OpenAI
              or OpenRouter key if you want the LLM-enriched version of the explanations.
            </p>
          </div>

          <form className="analysis-form" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="repo-input">
              GitHub repository
            </label>
            <input
              id="repo-input"
              className="analysis-input"
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              placeholder="openai/openai-cookbook or https://github.com/openai/openai-cookbook"
            />
            <button className="analysis-button" type="submit" disabled={loading}>
              {loading ? "Reading the repo..." : "Analyze repository"}
            </button>
          </form>

          <div className="sample-strip">
            {sampleRepos.map((repo) => (
              <button
                key={repo}
                type="button"
                className="sample-pill"
                onClick={() => {
                  setIdentifier(repo);
                  void submitAnalysis(repo);
                }}
              >
                {repo}
              </button>
            ))}
          </div>

          {error && <div className="error-banner">{error}</div>}
        </div>
      </section>

      <section className="workflow-panel" id="how-it-works">
        <div className="section-head">
          <span className="eyebrow">Workflow</span>
          <h2 className="section-title">A cleaner architecture for the product too.</h2>
        </div>
        <div className="workflow-grid">
          {workflowSteps.map((step, index) => (
            <article key={step.title} className="workflow-card">
              <span className="workflow-index">0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      {result && (
        <section className="result-suite" id="results">
          <div className="result-banner">
            <div>
              <span className="eyebrow">Analysis result</span>
              <h2 className="result-title">{result.externalId}</h2>
              <p className="result-copy">{result.repoSummary}</p>
            </div>
            <div className="result-badges">
              <span className="status-badge">{result.analysisMode === "llm" ? "LLM-enriched" : "Heuristic mode"}</span>
              <a className="repo-link" href={result.repoUrl} target="_blank" rel="noreferrer">
                View on GitHub
              </a>
            </div>
          </div>

          <div className="result-grid-top">
            <article className="feature-panel">
              <span className="eyebrow">Project pulse</span>
              <div className="metrics-grid">
                <div className="big-metric">
                  <strong>{result.languages.join(", ") || "Mixed stack"}</strong>
                  <span>Primary languages</span>
                </div>
                <div className="stat-stack">
                  <div className="mini-stat">
                    <strong>{result.starCount.toLocaleString()}</strong>
                    <span>Stars</span>
                  </div>
                  <div className="mini-stat">
                    <strong>{result.forkCount.toLocaleString()}</strong>
                    <span>Forks</span>
                  </div>
                  <div className="mini-stat">
                    <strong>{new Date(result.updatedAt).toLocaleDateString()}</strong>
                    <span>Last updated</span>
                  </div>
                </div>
              </div>
              <p className="architecture-copy">{result.architectureSummary}</p>
            </article>

            <article className="feature-panel">
              <span className="eyebrow">Detected signals</span>
              <div className="signal-cluster">
                <SignalBlock label="Patterns" values={result.detectedPatterns} />
                <SignalBlock label="Fields" values={result.fields} />
                <SignalBlock label="Topics" values={result.topics} />
              </div>
            </article>
          </div>

          <article className="concept-suite">
            <div className="section-head">
              <span className="eyebrow">Concepts</span>
              <h2 className="section-title">What this repository is already teaching</h2>
            </div>
            <div className="concept-showcase">
              {result.conceptDetails.map((concept) => (
                <article key={concept.name} className="concept-sheet">
                  <div className="concept-topline">
                    <span className="concept-category">{concept.category}</span>
                    <span className="concept-confidence">{Math.round(concept.confidence * 100)}% confidence</span>
                  </div>
                  <h3>{concept.name}</h3>
                  <p>{concept.summary}</p>
                  <p>
                    <strong>Why it matters:</strong> {concept.importance}
                  </p>
                  <div className="evidence-cloud">
                    {concept.evidence.length ? (
                      concept.evidence.map((item) => (
                        <span key={`${concept.name}-${item}`} className="evidence-chip">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="evidence-chip">No direct file evidence found</span>
                    )}
                  </div>
                  <p className="learn-next">
                    <strong>Learn next:</strong> {concept.learnNext}
                  </p>
                </article>
              ))}
            </div>
          </article>

          <div className="result-grid-bottom">
            <article className="feature-panel">
              <span className="eyebrow">Learning path</span>
              <h2 className="section-title">A study order based on this repo</h2>
              <div className="path-stack">
                {result.learningPath.map((step, index) => (
                  <div key={step.title} className="path-step">
                    <span className="path-index">{index + 1}</span>
                    <div>
                      <strong>{step.title}</strong>
                      <p>{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="feature-panel">
              <span className="eyebrow">Product angle</span>
              <h2 className="section-title">Why this experience works for vibecoders</h2>
              <div className="value-list">
                <div>
                  <strong>Context beats abstraction</strong>
                  <p>It is easier to care about async programming when it is already inside your project.</p>
                </div>
                <div>
                  <strong>Repo evidence builds trust</strong>
                  <p>The app shows why it believes a concept is present instead of making vague claims.</p>
                </div>
                <div>
                  <strong>Learning turns into momentum</strong>
                  <p>Users leave with a practical next step, not just an analysis artifact.</p>
                </div>
              </div>
            </article>
          </div>
        </section>
      )}
    </div>
  );
}

function SignalBlock({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="signal-block">
      <strong>{label}</strong>
      <div className="signal-tags">
        {values.length ? values.map((value) => <span key={`${label}-${value}`} className="signal-tag">{value}</span>) : <span className="signal-empty">Not detected yet</span>}
      </div>
    </div>
  );
}
