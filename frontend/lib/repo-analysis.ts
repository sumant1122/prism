import "server-only";

import { Buffer } from "node:buffer";

import type { ConceptDetail, LearningPathStep, RepoAnalysisResponse } from "@/lib/types";

type RepoContext = {
  name: string;
  fullName: string;
  description: string;
  owner: string;
  repoUrl: string;
  starCount: number;
  forkCount: number;
  updatedAt: string;
  topics: string[];
  languages: string[];
  readmePath: string;
  readmeExcerpt: string;
  treePaths: string[];
  fileSamples: Array<{ path: string; excerpt: string }>;
};

type LlmPayload = {
  repoSummary?: unknown;
  architectureSummary?: unknown;
  fields?: unknown;
  detectedPatterns?: unknown;
  concepts?: unknown;
  learningPath?: unknown;
  languages?: unknown;
};

type ConceptRule = {
  name: string;
  category: string;
  summary: string;
  importance: string;
  learnNext: string;
  contentTerms: string[];
  pathTerms: string[];
};

const GITHUB_API_BASE = "https://api.github.com";

export async function analyzeGithubRepository(input: string): Promise<RepoAnalysisResponse> {
  const repoPath = normalizeGithubIdentifier(input);
  const repository = await fetchGitHubJson<{
    full_name: string;
    name: string;
    description: string | null;
    html_url: string;
    default_branch: string;
    stargazers_count: number;
    forks_count: number;
    updated_at: string;
    owner?: { login?: string };
    topics?: string[];
    languages_url?: string;
  }>(`${GITHUB_API_BASE}/repos/${repoPath}`);

  const [languages, readme, treePaths] = await Promise.all([
    fetchLanguages(repository.languages_url),
    fetchReadme(repoPath),
    fetchTree(repoPath, repository.default_branch || "HEAD"),
  ]);
  const fileSamples = await fetchKeyFileSamples(repoPath, treePaths);

  const context: RepoContext = {
    name: repository.name || repoPath.split("/")[1] || repoPath,
    fullName: repository.full_name || repoPath,
    description: (repository.description || "").trim(),
    owner: repository.owner?.login || repoPath.split("/")[0] || "unknown",
    repoUrl: repository.html_url || `https://github.com/${repoPath}`,
    starCount: Number(repository.stargazers_count || 0),
    forkCount: Number(repository.forks_count || 0),
    updatedAt: repository.updated_at || new Date().toISOString(),
    topics: sanitizeStrings(repository.topics || []),
    languages,
    readmePath: readme.path,
    readmeExcerpt: readme.excerpt,
    treePaths,
    fileSamples,
  };

  const llmReport = await analyzeWithLlm(context);
  if (llmReport) {
    return {
      source: "github",
      externalId: context.fullName,
      name: context.name,
      owner: context.owner,
      description: context.description,
      repoUrl: context.repoUrl,
      starCount: context.starCount,
      forkCount: context.forkCount,
      updatedAt: context.updatedAt,
      topics: dedupeStrings([...context.topics, ...context.languages]),
      concepts: llmReport.conceptDetails.map((concept) => concept.name),
      fields: llmReport.fields,
      repoSummary: llmReport.repoSummary,
      architectureSummary: llmReport.architectureSummary,
      conceptDetails: llmReport.conceptDetails,
      learningPath: llmReport.learningPath,
      detectedPatterns: llmReport.detectedPatterns,
      languages: llmReport.languages.length ? llmReport.languages : context.languages,
      analysisMode: "llm",
    };
  }

  const heuristic = analyzeHeuristically(context);
  return {
    source: "github",
    externalId: context.fullName,
    name: context.name,
    owner: context.owner,
    description: context.description,
    repoUrl: context.repoUrl,
    starCount: context.starCount,
    forkCount: context.forkCount,
    updatedAt: context.updatedAt,
    topics: dedupeStrings([...context.topics, ...context.languages]),
    concepts: heuristic.conceptDetails.map((concept) => concept.name),
    fields: heuristic.fields,
    repoSummary: heuristic.repoSummary,
    architectureSummary: heuristic.architectureSummary,
    conceptDetails: heuristic.conceptDetails,
    learningPath: heuristic.learningPath,
    detectedPatterns: heuristic.detectedPatterns,
    languages: context.languages,
    analysisMode: "heuristic",
  };
}

async function fetchGitHubJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: buildGitHubHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("GitHub repository not found. Check the repo URL or owner/name.");
    }
    if (response.status === 403) {
      throw new Error("GitHub API rate limit reached. Add a GITHUB_TOKEN to increase the limit.");
    }
    throw new Error(`GitHub request failed with status ${response.status}.`);
  }

  return (await response.json()) as T;
}

function buildGitHubHeaders(): HeadersInit {
  const headers: HeadersInit = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  }
  return headers;
}

function normalizeGithubIdentifier(identifier: string): string {
  const cleaned = identifier.trim();
  if (!cleaned) {
    throw new Error("Enter a GitHub repository URL or owner/repo.");
  }
  if (!cleaned.includes("github.com")) {
    return cleaned.replace(/\.git$/, "").replace(/^\/+|\/+$/g, "");
  }
  const normalizedUrl = cleaned.startsWith("http://") || cleaned.startsWith("https://") ? cleaned : `https://${cleaned}`;
  const url = new URL(normalizedUrl);
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length < 2) {
    throw new Error("That GitHub URL does not look like a repository.");
  }
  return `${parts[0]}/${parts[1].replace(/\.git$/, "")}`;
}

async function fetchLanguages(languagesUrl?: string): Promise<string[]> {
  if (!languagesUrl) {
    return [];
  }
  try {
    const payload = await fetchGitHubJson<Record<string, number>>(languagesUrl);
    return Object.keys(payload).slice(0, 8);
  } catch {
    return [];
  }
}

async function fetchReadme(repoPath: string): Promise<{ path: string; excerpt: string }> {
  try {
    const payload = await fetchGitHubJson<{ path?: string; content?: string; encoding?: string }>(
      `${GITHUB_API_BASE}/repos/${repoPath}/readme`,
    );
    const excerpt = decodeBase64Content(payload.content, payload.encoding);
    return {
      path: payload.path || "README.md",
      excerpt: extractReadmeExcerpt(excerpt),
    };
  } catch {
    return {
      path: "README.md",
      excerpt: "",
    };
  }
}

async function fetchTree(repoPath: string, branch: string): Promise<string[]> {
  try {
    const payload = await fetchGitHubJson<{ tree?: Array<{ path?: string }> }>(
      `${GITHUB_API_BASE}/repos/${repoPath}/git/trees/${encodeURIComponent(branch)}?recursive=1`,
    );
    return sanitizeStrings((payload.tree || []).map((entry) => entry.path || "")).slice(0, 400);
  } catch {
    return [];
  }
}

async function fetchKeyFileSamples(repoPath: string, treePaths: string[]): Promise<Array<{ path: string; excerpt: string }>> {
  const candidates = pickInterestingPaths(treePaths);
  const payloads = await Promise.all(
    candidates.map(async (path) => {
      const content = await fetchFileContent(repoPath, path);
      if (!content) {
        return null;
      }
      return {
        path,
        excerpt: content.slice(0, 2200),
      };
    }),
  );
  return payloads.filter((entry): entry is { path: string; excerpt: string } => Boolean(entry));
}

async function fetchFileContent(repoPath: string, path: string): Promise<string> {
  try {
    const payload = await fetchGitHubJson<{ content?: string; encoding?: string; type?: string }>(
      `${GITHUB_API_BASE}/repos/${repoPath}/contents/${path.split("/").map(encodeURIComponent).join("/")}`,
    );
    if ((payload.type || "file") !== "file") {
      return "";
    }
    return decodeBase64Content(payload.content, payload.encoding).trim();
  } catch {
    return "";
  }
}

function decodeBase64Content(content?: string, encoding?: string): string {
  if (!content || (encoding || "").toLowerCase() !== "base64") {
    return "";
  }
  try {
    return Buffer.from(content, "base64").toString("utf8");
  } catch {
    return "";
  }
}

function extractReadmeExcerpt(markdown: string): string {
  if (!markdown.trim()) {
    return "";
  }
  const lines: string[] = [];
  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      if (lines.length) {
        break;
      }
      continue;
    }
    if (line.startsWith("#") && !lines.length) {
      continue;
    }
    lines.push(line);
    if (lines.join(" ").length > 700) {
      break;
    }
  }
  return lines.join(" ").slice(0, 1200);
}

function pickInterestingPaths(treePaths: string[]): string[] {
  const exactNames = new Set([
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "vite.config.ts",
    "requirements.txt",
    "pyproject.toml",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "schema.prisma",
  ]);
  const preferredFragments = ["app/", "src/", "components/", "lib/", "api/", "pages/", "server/"];
  const selected: string[] = [];

  for (const path of treePaths) {
    const lower = path.toLowerCase();
    const basename = lower.split("/").pop() || lower;
    if (exactNames.has(basename) || exactNames.has(lower)) {
      selected.push(path);
      continue;
    }
    if (
      preferredFragments.some((fragment) => lower.includes(fragment)) &&
      [".ts", ".tsx", ".js", ".jsx", ".py"].some((extension) => lower.endsWith(extension))
    ) {
      selected.push(path);
    }
    if (selected.length >= 12) {
      break;
    }
  }

  return dedupeStrings(selected).slice(0, 10);
}

async function analyzeWithLlm(context: RepoContext): Promise<{
  repoSummary: string;
  architectureSummary: string;
  fields: string[];
  detectedPatterns: string[];
  conceptDetails: ConceptDetail[];
  learningPath: LearningPathStep[];
  languages: string[];
} | null> {
  const client = resolveLlmClient();
  if (!client) {
    return null;
  }

  const payload = {
    name: context.name,
    fullName: context.fullName,
    description: context.description,
    languages: context.languages.slice(0, 8),
    topics: context.topics.slice(0, 12),
    readmeExcerpt: context.readmeExcerpt.slice(0, 3500),
    treePaths: context.treePaths.slice(0, 160),
    fileSamples: context.fileSamples.slice(0, 8),
  };

  try {
    const response = await fetch(client.endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${client.apiKey}`,
        ...(client.extraHeaders || {}),
      },
      cache: "no-store",
      body: JSON.stringify({
        model: client.model,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content:
              "You are a patient computer science teacher. Analyze a GitHub repository snapshot and explain the core CS and software engineering concepts that are visibly used. Return strict JSON only.",
          },
          {
            role: "user",
            content:
              'Return JSON with keys: repoSummary (string), architectureSummary (string), fields (string array), detectedPatterns (string array), concepts (array of objects with keys name, category, summary, importance, evidence, learnNext, confidence), learningPath (array of objects with keys title, description), languages (string array). Repository snapshot:\n' +
              JSON.stringify(payload),
          },
        ],
      }),
    });

    if (!response.ok) {
      return null;
    }

    const raw = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = raw.choices?.[0]?.message?.content;
    if (!content) {
      return null;
    }
    const parsed = JSON.parse(content) as LlmPayload;
    const conceptDetails = normalizeConcepts(parsed.concepts);
    const learningPath = normalizeLearningPath(parsed.learningPath);
    if (!conceptDetails.length) {
      return null;
    }
    return {
      repoSummary: asText(parsed.repoSummary) || `${context.fullName} uses several teachable software engineering patterns.`,
      architectureSummary: asText(parsed.architectureSummary),
      fields: sanitizeStrings(asStringArray(parsed.fields)).slice(0, 6),
      detectedPatterns: sanitizeStrings(asStringArray(parsed.detectedPatterns)).slice(0, 6),
      conceptDetails: conceptDetails.slice(0, 8),
      learningPath: learningPath.slice(0, 5),
      languages: sanitizeStrings(asStringArray(parsed.languages)).slice(0, 8),
    };
  } catch {
    return null;
  }
}

function resolveLlmClient():
  | { endpoint: string; apiKey: string; model: string; extraHeaders?: HeadersInit }
  | null {
  const provider = (process.env.MODEL_PROVIDER || "auto").trim().toLowerCase();

  const openAi = process.env.OPENAI_API_KEY
    ? {
        endpoint: `${(process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "")}/chat/completions`,
        apiKey: process.env.OPENAI_API_KEY,
        model: process.env.OPENAI_MODEL || "gpt-4o-mini",
      }
    : null;

  const openRouter = process.env.OPENROUTER_API_KEY
    ? {
        endpoint: `${(process.env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1").replace(/\/$/, "")}/chat/completions`,
        apiKey: process.env.OPENROUTER_API_KEY,
        model: process.env.OPENROUTER_MODEL || "openai/gpt-4o-mini",
        extraHeaders: {
          "HTTP-Referer": process.env.OPENROUTER_SITE_URL || "http://localhost:3000",
          "X-Title": "Repo Teacher",
        },
      }
    : null;

  if (provider === "openai") {
    return openAi || openRouter;
  }
  if (provider === "openrouter") {
    return openRouter || openAi;
  }
  return openAi || openRouter;
}

function analyzeHeuristically(context: RepoContext): {
  repoSummary: string;
  architectureSummary: string;
  fields: string[];
  detectedPatterns: string[];
  conceptDetails: ConceptDetail[];
  learningPath: LearningPathStep[];
} {
  const corpus = buildCorpus(context);
  const detectedPatterns = detectPatterns(corpus);
  const conceptDetails = conceptCatalog()
    .map((rule) => {
      const evidence = collectEvidence(context, rule.contentTerms, rule.pathTerms);
      if (!evidence.length) {
        return null;
      }
      return {
        name: rule.name,
        category: rule.category,
        summary: rule.summary,
        importance: rule.importance,
        evidence,
        learnNext: rule.learnNext,
        confidence: roundConfidence(0.58 + evidence.length * 0.08),
      } satisfies ConceptDetail;
    })
    .filter((entry): entry is ConceptDetail => Boolean(entry))
    .sort((left, right) => right.confidence - left.confidence);

  if (!conceptDetails.length) {
    conceptDetails.push({
      name: "Abstraction and Modularity",
      category: "Software Design",
      summary:
        "Even from the repository structure alone, this project teaches modular thinking by splitting the app into smaller units with narrower responsibilities.",
      importance:
        "Modularity is one of the first habits that makes code easier to change, test, and understand as projects get bigger.",
      evidence: context.treePaths.slice(0, 3),
      learnNext: "Pick one feature and label which files belong to UI, logic, and external data access.",
      confidence: 0.54,
    });
  }

  const fields = deriveFields(conceptDetails, context.languages);
  const learningPath = conceptDetails.slice(0, 4).map((concept) => ({
    title: `Study ${concept.name}`,
    description: concept.learnNext,
  }));
  const projectShape = describeProjectShape(corpus, detectedPatterns);
  const repoSummary = `${context.fullName} looks like ${projectShape}. It appears to use ${joinList(context.languages) || "a mixed stack"} and leans on ${joinList(
    conceptDetails.slice(0, 3).map((concept) => concept.name),
  ) || "core software design ideas"}.`;

  const architectureSummary =
    corpus.includes("next") && (corpus.includes("api/") || corpus.includes("route.ts") || corpus.includes("server"))
      ? "The repository appears to separate interface concerns from server-side analysis logic, which is a clean example of boundary design in modern web apps."
      : `The repository is organized in a way that highlights ${joinList(
          conceptDetails.slice(0, 3).map((concept) => concept.name),
        )}. ${detectedPatterns.length ? `Implementation patterns include ${joinList(detectedPatterns.slice(0, 3))}.` : ""}`;

  return {
    repoSummary,
    architectureSummary,
    fields,
    detectedPatterns,
    conceptDetails: conceptDetails.slice(0, 8),
    learningPath,
  };
}

function buildCorpus(context: RepoContext): string {
  return [
    context.description,
    context.readmeExcerpt,
    ...context.languages,
    ...context.topics,
    ...context.treePaths.slice(0, 160),
    ...context.fileSamples.map((sample) => `${sample.path}\n${sample.excerpt}`),
  ]
    .join("\n")
    .toLowerCase();
}

function detectPatterns(corpus: string): string[] {
  const patterns: string[] = [];
  if (corpus.includes("next.config") || corpus.includes("app/page.tsx") || corpus.includes("next")) {
    patterns.push("Next.js app router");
  }
  if (corpus.includes("route.ts") || corpus.includes("fetch(") || corpus.includes("api/")) {
    patterns.push("Server-side API handlers");
  }
  if (corpus.includes("dockerfile") || corpus.includes("docker-compose")) {
    patterns.push("Containerized deployment");
  }
  if (["pytest", "jest", "vitest", ".test.", ".spec."].some((term) => corpus.includes(term))) {
    patterns.push("Automated testing");
  }
  if (["openai", "openrouter", "llm", "prompt", "agent"].some((term) => corpus.includes(term))) {
    patterns.push("AI-assisted analysis");
  }
  if (["postgres", "mysql", "sqlite", "prisma", "schema"].some((term) => corpus.includes(term))) {
    patterns.push("Structured data layer");
  }
  return patterns;
}

function conceptCatalog(): ConceptRule[] {
  return [
    {
      name: "Client-Server Architecture",
      category: "Application Architecture",
      summary:
        "This repo appears to split responsibilities between a user-facing interface and a server-side analysis layer, which is the core client-server model.",
      importance:
        "Understanding this boundary helps beginners reason about where requests are made, where secrets live, and where data gets transformed before it reaches the UI.",
      learnNext: "Trace one button click all the way through the request, analysis logic, and returned JSON.",
      contentTerms: ["route.ts", "fetch(", "api/", "request", "response", "headers"],
      pathTerms: ["app/api/", "api/", "server/"],
    },
    {
      name: "State Management",
      category: "Frontend Engineering",
      summary:
        "The UI likely tracks changing values such as the input repo, loading states, and analysis results, which makes state management a core idea in the app.",
      importance:
        "State determines what users see and when the screen updates. Poor state design often creates stale data, duplicate truth, and inconsistent interfaces.",
      learnNext: "List which values in the UI are input state, loading state, and derived display state.",
      contentTerms: ["usestate", "transition", "loading", "setstate", "useeffect"],
      pathTerms: ["components/", "app/", "hooks/"],
    },
    {
      name: "Asynchronous Programming",
      category: "Concurrency",
      summary:
        "The project performs network requests and deferred analysis work, so it relies on asynchronous control flow to stay responsive.",
      importance:
        "Async code teaches an important systems lesson: some work finishes later, can fail independently, or may need retries and loading feedback.",
      learnNext: "Find every async request in one feature and map what happens for loading, success, and failure.",
      contentTerms: ["async ", "await ", "promise", "fetch(", "loading", "pending"],
      pathTerms: ["api/", "server/", "actions/"],
    },
    {
      name: "Data Modeling and Persistence",
      category: "Data Systems",
      summary:
        "The repository shows signs of structured payloads and response objects, which introduces schema thinking and data modeling even without a full database.",
      importance:
        "Data modeling controls how information is shaped, validated, and passed between parts of the app. It is one of the hidden foundations of reliable software.",
      learnNext: "Map one response object from the server route to the UI components that render it.",
      contentTerms: ["type ", "interface ", "schema", "model", "zod", "payload"],
      pathTerms: ["lib/", "types/", "models/"],
    },
    {
      name: "Testing and Verification",
      category: "Quality",
      summary:
        "The repo contains automated checks or test files, which means expected behavior is being encoded as repeatable verification.",
      importance:
        "Tests work like executable examples. They make refactors safer and help AI-generated changes stay grounded in real behavior.",
      learnNext: "Run one test file and explain what user-visible behavior it protects.",
      contentTerms: ["pytest", "jest", "vitest", ".test.", ".spec.", "assert "],
      pathTerms: ["tests/", "__tests__/"],
    },
    {
      name: "Abstraction and Separation of Concerns",
      category: "Software Design",
      summary:
        "The folder structure suggests that UI, analysis logic, and infrastructure are separated into different modules instead of being jammed into one file.",
      importance:
        "This is one of the most important ideas in maintainable software. Separation of concerns reduces coupling and makes code easier to extend.",
      learnNext: "Choose one feature and label which files handle presentation, analysis, and external API access.",
      contentTerms: ["component", "service", "client", "analyze", "lib/"],
      pathTerms: ["components/", "lib/", "app/api/"],
    },
    {
      name: "Prompt-Oriented AI Integration",
      category: "Applied AI",
      summary:
        "This app uses large language models as part of the product logic, which introduces prompt design, fallback behavior, and structured output parsing.",
      importance:
        "Once AI is in the loop, you have to think about uncertainty, confidence, retries, and graceful degradation instead of assuming every call is deterministic.",
      learnNext: "Compare the heuristic path with the LLM path and note where the app protects itself from unreliable model output.",
      contentTerms: ["openai", "openrouter", "response_format", "prompt", "model"],
      pathTerms: ["app/api/", "lib/"],
    },
  ];
}

function collectEvidence(context: RepoContext, contentTerms: string[], pathTerms: string[]): string[] {
  const evidence: string[] = [];
  const seen = new Set<string>();

  for (const sample of context.fileSamples) {
    const haystack = `${sample.path}\n${sample.excerpt}`.toLowerCase();
    if (contentTerms.some((term) => haystack.includes(term))) {
      if (!seen.has(sample.path)) {
        evidence.push(sample.path);
        seen.add(sample.path);
      }
    }
    if (evidence.length >= 4) {
      return evidence;
    }
  }

  for (const path of context.treePaths) {
    const lower = path.toLowerCase();
    if (pathTerms.some((term) => lower.includes(term))) {
      if (!seen.has(path)) {
        evidence.push(path);
        seen.add(path);
      }
    }
    if (evidence.length >= 4) {
      return evidence;
    }
  }

  if (!evidence.length) {
    const description = `${context.description}\n${context.readmeExcerpt}`.toLowerCase();
    if (contentTerms.some((term) => description.includes(term))) {
      evidence.push(context.readmePath || "README.md");
    }
  }

  return evidence;
}

function deriveFields(concepts: ConceptDetail[], languages: string[]): string[] {
  const fields: string[] = [];
  const categoryToField: Record<string, string> = {
    "Application Architecture": "Web Systems",
    "Frontend Engineering": "Interactive UIs",
    Concurrency: "Concurrent Systems",
    "Data Systems": "Data Modeling",
    Quality: "Software Quality",
    "Software Design": "Software Design",
    "Applied AI": "AI Product Engineering",
  };

  for (const concept of concepts) {
    const field = categoryToField[concept.category];
    if (field && !fields.includes(field)) {
      fields.push(field);
    }
  }

  if (languages.includes("TypeScript") || languages.includes("JavaScript")) {
    fields.push("Frontend Development");
  }
  if (languages.includes("Python")) {
    fields.push("Backend Development");
  }

  return dedupeStrings(fields).slice(0, 6);
}

function describeProjectShape(corpus: string, patterns: string[]): string {
  if (patterns.includes("Next.js app router") && patterns.includes("Server-side API handlers")) {
    return "a full-stack web app with a single framework handling both UI and server logic";
  }
  if (corpus.includes("react") || corpus.includes("next")) {
    return "an interactive web application";
  }
  return "a software project with multiple collaborating modules";
}

function sanitizeStrings(values: string[]): string[] {
  return values.map((value) => value.trim()).filter(Boolean);
}

function dedupeStrings(values: string[]): string[] {
  const deduped: string[] = [];
  for (const value of values) {
    if (value && !deduped.includes(value)) {
      deduped.push(value);
    }
  }
  return deduped;
}

function joinList(values: string[]): string {
  const filtered = values.filter(Boolean);
  if (!filtered.length) {
    return "";
  }
  if (filtered.length === 1) {
    return filtered[0];
  }
  if (filtered.length === 2) {
    return `${filtered[0]} and ${filtered[1]}`;
  }
  return `${filtered.slice(0, -1).join(", ")}, and ${filtered.at(-1)}`;
}

function roundConfidence(value: number): number {
  return Math.max(0.45, Math.min(0.98, Number(value.toFixed(2))));
}

function normalizeConcepts(input: unknown): ConceptDetail[] {
  if (!Array.isArray(input)) {
    return [];
  }
  const output: ConceptDetail[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const record = raw as Record<string, unknown>;
    const name = asText(record.name);
    if (!name) {
      continue;
    }
    output.push({
      name,
      category: asText(record.category) || "Core Concept",
      summary: asText(record.summary),
      importance: asText(record.importance),
      evidence: sanitizeStrings(asStringArray(record.evidence)).slice(0, 4),
      learnNext: asText(record.learnNext),
      confidence: roundConfidence(Number(record.confidence ?? 0.65)),
    });
  }
  return output;
}

function normalizeLearningPath(input: unknown): LearningPathStep[] {
  if (!Array.isArray(input)) {
    return [];
  }
  const output: LearningPathStep[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const record = raw as Record<string, unknown>;
    const title = asText(record.title);
    const description = asText(record.description);
    if (!title || !description) {
      continue;
    }
    output.push({ title, description });
  }
  return output;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
