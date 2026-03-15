from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.agents.llm_client import LLMClient, LLMError


@dataclass(slots=True)
class ConceptExtractionResult:
    concepts: list[str]
    fields: list[str]


@dataclass(slots=True)
class RepoConceptInsight:
    name: str
    category: str
    summary: str
    importance: str
    evidence: list[str]
    learn_next: str
    confidence: float


@dataclass(slots=True)
class LearningPathStep:
    title: str
    description: str


@dataclass(slots=True)
class RepoEducationReport:
    repo_summary: str
    architecture_summary: str
    concepts: list[RepoConceptInsight]
    fields: list[str]
    detected_patterns: list[str]
    learning_path: list[LearningPathStep]
    languages: list[str]


class ConceptAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def extract(self, resource_summary: str, fallback_subjects: list[str] | None = None) -> ConceptExtractionResult:
        fallback_subjects = fallback_subjects or []
        summary = (resource_summary or "").strip()
        if not summary and not fallback_subjects:
            return ConceptExtractionResult(concepts=[], fields=[])

        if not self._llm_client:
            return self._heuristic_extract(summary, fallback_subjects)

        system_prompt = (
            "You extract concepts from enterprise resources. Return strict JSON with keys: "
            "concepts (string array) and fields (string array)."
        )
        user_prompt = (
            "Extract important concepts from the following resource.\n\n"
            f"Resource summary:\n{summary}\n\n"
            "Return JSON:\n"
            '{"concepts": [], "fields": []}'
        )

        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            concepts = [str(x).strip() for x in payload.get("concepts", []) if str(x).strip()]
            fields = [str(x).strip() for x in payload.get("fields", []) if str(x).strip()]
            if concepts or fields:
                return ConceptExtractionResult(concepts=concepts[:12], fields=fields[:6])
        except LLMError:
            pass

        return self._heuristic_extract(summary, fallback_subjects)

    def analyze_repository(self, repo_context: dict[str, Any]) -> RepoEducationReport:
        normalized_context = self._normalize_repo_context(repo_context)
        if self._llm_client:
            try:
                llm_report = self._analyze_repository_with_llm(normalized_context)
                if llm_report.concepts:
                    return llm_report
            except LLMError:
                pass
        return self._heuristic_repository_analysis(normalized_context)

    def _heuristic_extract(self, summary: str, subjects: list[str]) -> ConceptExtractionResult:
        tokens = [segment.strip() for segment in subjects if segment.strip()]
        concepts = tokens[:8]
        field_candidates = [t for t in tokens if "engineering" in t.lower() or "science" in t.lower()]
        fields = field_candidates[:4] or (tokens[:2] if tokens else [])
        if not concepts and summary:
            words = [w.strip(".,:;!?()[]{}").lower() for w in summary.split()]
            concepts = [w for w in words if len(w) > 7][:8]
        return ConceptExtractionResult(concepts=concepts, fields=fields)

    def _analyze_repository_with_llm(self, repo_context: dict[str, Any]) -> RepoEducationReport:
        prompt_payload = {
            "name": repo_context["name"],
            "full_name": repo_context["full_name"],
            "description": repo_context["description"],
            "languages": repo_context["languages"][:8],
            "topics": repo_context["topics"][:12],
            "readme_excerpt": repo_context["readme_excerpt"][:4000],
            "tree_paths": repo_context["tree_paths"][:160],
            "file_samples": repo_context["file_samples"][:8],
        }
        system_prompt = (
            "You are a patient computer science teacher. "
            "Analyze a GitHub repository snapshot and explain which core CS or software engineering "
            "concepts are actively used in the codebase. Return strict JSON only."
        )
        user_prompt = (
            "Return JSON with keys: repo_summary (string), architecture_summary (string), "
            "fields (string array), detected_patterns (string array), concepts (array of objects with keys "
            "name, category, summary, importance, evidence, learn_next, confidence), "
            "learning_path (array of objects with keys title, description), languages (string array).\n\n"
            f"Repository snapshot:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
        )
        payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        concepts = []
        for item in payload.get("concepts", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            concepts.append(
                RepoConceptInsight(
                    name=name,
                    category=str(item.get("category") or "Core Concept").strip() or "Core Concept",
                    summary=str(item.get("summary") or "").strip(),
                    importance=str(item.get("importance") or "").strip(),
                    evidence=[str(x).strip() for x in item.get("evidence", []) if str(x).strip()][:4],
                    learn_next=str(item.get("learn_next") or "").strip(),
                    confidence=self._clamp_confidence(item.get("confidence")),
                )
            )
        learning_path = []
        for item in payload.get("learning_path", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            if title and description:
                learning_path.append(LearningPathStep(title=title, description=description))
        if not concepts:
            raise LLMError("Repository analysis response was missing concepts")
        return RepoEducationReport(
            repo_summary=str(payload.get("repo_summary") or "").strip(),
            architecture_summary=str(payload.get("architecture_summary") or "").strip(),
            concepts=concepts[:8],
            fields=[str(x).strip() for x in payload.get("fields", []) if str(x).strip()][:6],
            detected_patterns=[str(x).strip() for x in payload.get("detected_patterns", []) if str(x).strip()][:6],
            learning_path=learning_path[:5],
            languages=[str(x).strip() for x in payload.get("languages", []) if str(x).strip()][:8]
            or repo_context["languages"][:8],
        )

    def _heuristic_repository_analysis(self, repo_context: dict[str, Any]) -> RepoEducationReport:
        corpus = self._build_repository_corpus(repo_context)
        concepts: list[RepoConceptInsight] = []
        detected_patterns = self._detect_patterns(repo_context, corpus)

        for rule in self._concept_catalog():
            evidence = self._collect_evidence(
                repo_context=repo_context,
                content_terms=rule["content_terms"],
                path_terms=rule["path_terms"],
            )
            if not evidence:
                continue
            confidence = min(0.95, 0.56 + (len(evidence) * 0.08))
            concepts.append(
                RepoConceptInsight(
                    name=rule["name"],
                    category=rule["category"],
                    summary=rule["summary"],
                    importance=rule["importance"],
                    evidence=evidence[:4],
                    learn_next=rule["learn_next"],
                    confidence=round(confidence, 2),
                )
            )

        if not concepts:
            concepts.append(
                RepoConceptInsight(
                    name="Abstraction and Modularity",
                    category="Software Design",
                    summary=(
                        "Even from the repo structure alone, this project is teaching modular design: code is broken "
                        "into separate files and directories so each part carries a narrower responsibility."
                    ),
                    importance=(
                        "Modularity is one of the first scalable CS ideas teams rely on. It makes code easier to "
                        "change, reason about, and test without rewriting everything at once."
                    ),
                    evidence=repo_context["tree_paths"][:3] or ["Repository structure"],
                    learn_next="Trace one feature end to end and note which files own UI, logic, and data access.",
                    confidence=0.52,
                )
            )

        concepts.sort(key=lambda item: item.confidence, reverse=True)
        concept_names = [concept.name for concept in concepts]
        fields = self._derive_fields(concepts, repo_context)
        languages = repo_context["languages"][:8]
        project_shape = self._describe_project_shape(repo_context, detected_patterns)
        repo_summary = (
            f"{repo_context['full_name']} looks like {project_shape}. "
            f"It appears to use {self._join_list(languages) or 'a mixed stack'} and leans on "
            f"{self._join_list(concept_names[:3]) or 'core software design patterns'}."
        ).strip()
        architecture_summary = self._build_architecture_summary(repo_context, detected_patterns, concepts, corpus)
        learning_path = self._build_learning_path(concepts)
        return RepoEducationReport(
            repo_summary=repo_summary,
            architecture_summary=architecture_summary,
            concepts=concepts[:8],
            fields=fields,
            detected_patterns=detected_patterns[:6],
            learning_path=learning_path[:5],
            languages=languages,
        )

    def _normalize_repo_context(self, repo_context: dict[str, Any]) -> dict[str, Any]:
        file_samples = []
        for sample in repo_context.get("file_samples", []):
            if not isinstance(sample, dict):
                continue
            path = str(sample.get("path") or "").strip()
            excerpt = str(sample.get("excerpt") or sample.get("content") or "").strip()
            if path:
                file_samples.append({"path": path, "excerpt": excerpt[:2400]})
        languages = [str(x).strip() for x in repo_context.get("languages", []) if str(x).strip()]
        topics = [str(x).strip() for x in repo_context.get("topics", []) if str(x).strip()]
        tree_paths = [str(x).strip() for x in repo_context.get("tree_paths", []) if str(x).strip()]
        return {
            "name": str(repo_context.get("name") or repo_context.get("full_name") or "Repository").strip(),
            "full_name": str(repo_context.get("full_name") or repo_context.get("name") or "Repository").strip(),
            "description": str(repo_context.get("description") or "").strip(),
            "languages": languages,
            "topics": topics,
            "tree_paths": tree_paths[:300],
            "readme_excerpt": str(repo_context.get("readme_excerpt") or "").strip(),
            "file_samples": file_samples[:12],
        }

    def _build_repository_corpus(self, repo_context: dict[str, Any]) -> str:
        pieces = [repo_context["description"], repo_context["readme_excerpt"]]
        pieces.extend(repo_context["languages"])
        pieces.extend(repo_context["topics"])
        pieces.extend(path for path in repo_context["tree_paths"][:160])
        pieces.extend(sample["excerpt"] for sample in repo_context["file_samples"])
        return "\n".join(piece for piece in pieces if piece).lower()

    def _collect_evidence(
        self,
        *,
        repo_context: dict[str, Any],
        content_terms: list[str],
        path_terms: list[str],
    ) -> list[str]:
        evidence: list[str] = []
        seen: set[str] = set()
        for sample in repo_context["file_samples"]:
            path = sample["path"]
            haystack = f"{path}\n{sample['excerpt']}".lower()
            if any(term in haystack for term in content_terms):
                if path not in seen:
                    evidence.append(path)
                    seen.add(path)
            if len(evidence) >= 4:
                return evidence
        for path in repo_context["tree_paths"]:
            lower_path = path.lower()
            if any(term in lower_path for term in path_terms):
                if path not in seen:
                    evidence.append(path)
                    seen.add(path)
            if len(evidence) >= 4:
                return evidence
        if not evidence:
            descriptor = repo_context["description"].lower()
            readme_excerpt = repo_context["readme_excerpt"].lower()
            if any(term in descriptor or term in readme_excerpt for term in content_terms):
                evidence.append("README or repository description")
        return evidence

    def _derive_fields(
        self,
        concepts: list[RepoConceptInsight],
        repo_context: dict[str, Any],
    ) -> list[str]:
        fields: list[str] = []
        category_to_field = {
            "Application Architecture": "Web Systems",
            "Frontend Engineering": "Interactive Applications",
            "Concurrency": "Concurrent Systems",
            "Data Systems": "Data Systems",
            "Security": "Security Fundamentals",
            "Quality": "Software Quality",
            "Performance": "Performance Engineering",
            "Software Design": "Software Design",
            "Data Structures": "Data Structures",
        }
        for concept in concepts:
            field = category_to_field.get(concept.category)
            if field and field not in fields:
                fields.append(field)
        if "TypeScript" in repo_context["languages"] or "JavaScript" in repo_context["languages"]:
            fields.append("Frontend Development")
        if "Python" in repo_context["languages"]:
            fields.append("Backend Development")
        deduped: list[str] = []
        for field in fields:
            if field not in deduped:
                deduped.append(field)
        return deduped[:6]

    def _build_learning_path(self, concepts: list[RepoConceptInsight]) -> list[LearningPathStep]:
        steps = []
        for concept in concepts[:4]:
            steps.append(
                LearningPathStep(
                    title=f"Study {concept.name}",
                    description=concept.learn_next,
                )
            )
        return steps

    def _describe_project_shape(self, repo_context: dict[str, Any], detected_patterns: list[str]) -> str:
        corpus = self._build_repository_corpus(repo_context)
        if "next.js app router frontend" in [pattern.lower() for pattern in detected_patterns] and any(
            marker in corpus for marker in ("fastapi", "express", "django", "server/")
        ):
            return "like a full-stack web application with a distinct frontend and backend"
        if any(marker in corpus for marker in ("react", "next", "vue", "svelte")):
            return "like an interactive web application"
        if any(marker in corpus for marker in ("fastapi", "express", "flask", "django")):
            return "like a backend service"
        return "like a software project with multiple collaborating modules"

    def _build_architecture_summary(
        self,
        repo_context: dict[str, Any],
        detected_patterns: list[str],
        concepts: list[RepoConceptInsight],
        corpus: str,
    ) -> str:
        pattern_sentence = (
            f"Detected implementation patterns include {self._join_list(detected_patterns[:3])}."
            if detected_patterns
            else "The repository structure suggests a layered design rather than one monolithic file."
        )
        if any(marker in corpus for marker in ("api/", "routes", "fastapi", "express")) and any(
            marker in corpus for marker in ("components/", "app/", "pages/", "react", "next")
        ):
            return (
                "The codebase appears to separate presentation concerns from server-side logic, which is a useful "
                "example of client-server architecture and boundary design. "
                f"{pattern_sentence}"
            )
        top_concepts = self._join_list([concept.name for concept in concepts[:3]])
        return (
            "The repository is organized in a way that exposes learners to multiple layers of engineering concerns. "
            f"It especially highlights {top_concepts}. {pattern_sentence}"
        )

    def _detect_patterns(self, repo_context: dict[str, Any], corpus: str) -> list[str]:
        patterns: list[str] = []
        if any(term in corpus for term in ("next", "next.config", "app/page.tsx")):
            patterns.append("Next.js app router frontend")
        elif any(term in corpus for term in ("react", "jsx", "tsx", "components/")):
            patterns.append("React component-driven frontend")
        if any(term in corpus for term in ("fastapi", "apirouter", "uvicorn")):
            patterns.append("FastAPI service layer")
        elif any(term in corpus for term in ("express", "router()", "koa", "nestjs")):
            patterns.append("HTTP API backend")
        if any(term in corpus for term in ("dockerfile", "docker-compose", "compose.yml")):
            patterns.append("Containerized local environment")
        if any(term in corpus for term in ("pytest", "jest", "vitest", "cypress", ".test.", ".spec.")):
            patterns.append("Automated testing workflow")
        if any(term in corpus for term in ("neo4j", "postgres", "mysql", "mongodb", "prisma", "sqlite")):
            patterns.append("Persistent data layer")
        if any(term in corpus for term in ("openai", "openrouter", "llm", "embedding", "agent")):
            patterns.append("AI-assisted feature flow")
        return patterns

    def _concept_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "Client-Server Architecture",
                "category": "Application Architecture",
                "summary": (
                    "This repo appears to split responsibilities between a user-facing interface and an API or "
                    "service layer, which is the core client-server model."
                ),
                "importance": (
                    "Understanding this boundary helps beginners reason about where data is fetched, validated, and "
                    "rendered. It is also where latency, contracts, and errors show up."
                ),
                "learn_next": "Pick one UI action and trace the request, server logic, and response payload end to end.",
                "content_terms": ["fastapi", "apirouter", "fetch(", "axios", "endpoint", "graphql", "route"],
                "path_terms": ["api/", "server/", "routes.py", "controllers/"],
            },
            {
                "name": "State Management",
                "category": "Frontend Engineering",
                "summary": (
                    "The frontend likely tracks changing values over time, which makes state management one of the "
                    "key ideas in this codebase."
                ),
                "importance": (
                    "State controls what users see and how updates propagate. Poor state design often causes stale "
                    "screens, duplicate sources of truth, and tricky bugs."
                ),
                "learn_next": "Write down which values are local UI state, server state, and derived state in one screen.",
                "content_terms": ["usestate", "usereducer", "context", "redux", "zustand", "store"],
                "path_terms": ["store/", "state/", "hooks/", "components/"],
            },
            {
                "name": "Asynchronous Programming",
                "category": "Concurrency",
                "summary": (
                    "The project performs work that does not complete instantly, so it relies on asynchronous control "
                    "flow to keep the app responsive."
                ),
                "importance": (
                    "Async code teaches an important CS lesson: operations can finish later or fail independently, "
                    "so sequencing, retries, and loading states matter."
                ),
                "learn_next": "Find every async call in one feature and note what happens for loading, success, and failure.",
                "content_terms": ["async ", "await ", "promise", "background", "queue", "worker", "task"],
                "path_terms": ["workers/", "jobs/", "tasks/", "queue/"],
            },
            {
                "name": "Data Modeling and Persistence",
                "category": "Data Systems",
                "summary": (
                    "The repo shows signs of storing structured information, which brings in schemas, models, and "
                    "query design."
                ),
                "importance": (
                    "Data modeling determines how information can be validated, retrieved, and evolved over time. "
                    "It is the backbone of most real applications."
                ),
                "learn_next": "Map one stored entity from schema or model definition to the code that reads and writes it.",
                "content_terms": ["schema", "model", "migration", "database", "postgres", "mysql", "sqlite", "prisma", "neo4j", "mongo"],
                "path_terms": ["models/", "migrations/", "prisma/", "db/", "database/", "graph/"],
            },
            {
                "name": "Authentication and Authorization",
                "category": "Security",
                "summary": (
                    "The repository includes identity or permission signals, which means it is dealing with access control."
                ),
                "importance": (
                    "Authentication proves who a user is, while authorization controls what they are allowed to do. "
                    "Mixing those up creates security holes."
                ),
                "learn_next": "Document where identity is created, stored, and checked before protected actions run.",
                "content_terms": ["auth", "jwt", "session", "login", "oauth", "clerk", "nextauth", "permission", "role"],
                "path_terms": ["auth/", "middleware/", "permissions/"],
            },
            {
                "name": "Testing and Verification",
                "category": "Quality",
                "summary": (
                    "The repo contains automated checks, which means the team is using tests to encode expected behavior."
                ),
                "importance": (
                    "Tests act like executable examples. They reduce regressions and make refactors much safer, "
                    "especially when AI-generated changes start piling up."
                ),
                "learn_next": "Run one test file and explain which behavior it protects and which edge cases it ignores.",
                "content_terms": ["pytest", "jest", "vitest", "cypress", ".test.", ".spec."],
                "path_terms": ["tests/", "__tests__/", "specs/"],
            },
            {
                "name": "Caching and Performance",
                "category": "Performance",
                "summary": (
                    "The codebase hints at performance optimization techniques such as caching, memoization, or indexing."
                ),
                "importance": (
                    "Performance work is really about time and space tradeoffs. This is where algorithmic thinking starts "
                    "to show up in product code."
                ),
                "learn_next": "List the slow or repeated operations in the app and note which ones are avoided through caching.",
                "content_terms": ["cache", "redis", "memo", "throttle", "debounce", "index"],
                "path_terms": ["cache/", "redis/", "indexes/"],
            },
            {
                "name": "Abstraction and Separation of Concerns",
                "category": "Software Design",
                "summary": (
                    "The folder structure suggests that UI, business logic, and infrastructure code are separated into "
                    "different modules."
                ),
                "importance": (
                    "This is one of the biggest habits that helps code scale. Separating concerns reduces coupling and "
                    "lets people change one part of the system without breaking everything else."
                ),
                "learn_next": "Choose one feature and label which files belong to presentation, logic, and infrastructure.",
                "content_terms": ["service", "repository", "component", "hook", "client"],
                "path_terms": ["components/", "services/", "hooks/", "lib/", "clients/", "repositories/"],
            },
            {
                "name": "Graph and Relationship Modeling",
                "category": "Data Structures",
                "summary": (
                    "The repository appears to reason about entities and connections, which is the essence of graph modeling."
                ),
                "importance": (
                    "Graphs are a foundational data structure for representing relationships. They show up in social apps, "
                    "recommendation systems, dependency mapping, and search."
                ),
                "learn_next": "Identify the nodes and edges in the domain model, then sketch how a query would traverse them.",
                "content_terms": ["graph", "edge", "node", "neo4j", "relationship", "traversal"],
                "path_terms": ["graph/", "edges/", "nodes/"],
            },
        ]

    def _join_list(self, values: list[str]) -> str:
        filtered = [value for value in values if value]
        if not filtered:
            return ""
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) == 2:
            return f"{filtered[0]} and {filtered[1]}"
        return f"{', '.join(filtered[:-1])}, and {filtered[-1]}"

    def _clamp_confidence(self, value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.65
        return round(min(0.99, max(0.0, numeric)), 2)
