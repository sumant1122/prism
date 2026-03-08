# Prism

Prism is an enterprise intelligence platform that maps systems, resources, concepts, ownership, and cross-platform relationships using AI.

## What It Does

- Ingests enterprise resources from:
  - GitHub repositories
  - ServiceNow configuration items (stubbed connector pattern)
  - Manual/custom sources
- Builds a graph of:
  - `Resource`, `Platform`, `Field`, `Concept`, and related nodes
- Extracts concepts and relationships using pluggable LLM providers
- Exposes:
  - `POST /resources`
  - `GET /graph`
  - `GET /insights`
  - `POST /chat`

## Product Focus

- Platform engineering visibility
- Dependency intelligence and blast-radius exploration
- Ownership and domain coverage analytics
- Graph-grounded natural language Q&A

## Architecture

```mermaid
flowchart LR
    UI["Next.js Frontend"] --> API["FastAPI Backend"]
    API --> CONN["Connector Layer (GitHub / ServiceNow / Manual)"]
    API --> AGENTS["AI Agents (Concept / Relationship / Insight / Chat)"]
    AGENTS --> LLM["OpenRouter / OpenAI / Ollama"]
    API --> NEO["Neo4j Knowledge Graph"]
    NEO --> INS["Insight & Governance Engine"]
    INS --> API
```

## Enterprise Resource Ingestion Example

```bash
curl -X POST http://localhost:8000/resources \
  -H "Content-Type: application/json" \
  -d '{
    "source": "github",
    "identifier": "kubernetes/kubernetes",
    "tags": ["platform", "infrastructure"]
  }'
```

## Run

1. `cd prism/docker`
2. `docker compose up --build`

Open:
- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`
- Neo4j Browser: `http://localhost:7474`

## Notes

- ServiceNow ingestion is currently a connector stub pattern; replace with real API auth/query flow for production.
- Default Neo4j credentials in compose are isolated for Prism (`neo4j/prismneo`) with a dedicated Docker volume.
