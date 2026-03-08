# BookGraph

BookGraph is an open-source MVP that transforms a list of books into a knowledge graph of books, authors, concepts, fields, and cross-book relationships using AI.

## Project Structure

```text
bookgraph/
├── backend/
│   ├── app/
│   │   ├── ingestion/
│   │   ├── enrichment/
│   │   ├── agents/
│   │   ├── graph/
│   │   ├── insights/
│   │   ├── api/
│   │   └── main.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── components/
│   └── graph/
├── docker/
│   └── docker-compose.yml
└── README.md
```

## Backend MVP Features

- `POST /books` ingests a book title, fetches Open Library metadata, enriches with AI concepts/fields, and creates graph relationships.
- `GET /graph` returns graph nodes and edges for visualization.
- `GET /insights` returns central books, clusters, missing-topic coverage, graph stats, actionable recommendations, and an optional LLM-synthesized narrative.
- `POST /chat` answers graph-aware questions by retrieving a relevant subgraph and grounding responses in node/edge evidence.

## Architecture

```mermaid
flowchart LR
    UI["Next.js Frontend"] --> API["FastAPI Backend"]
    API --> ING["Open Library Ingestion"]
    API --> AGENTS["Concept + Relationship Agents"]
    AGENTS --> LLM["Pluggable LLM Layer (OpenAI/OpenRouter/Ollama)"]
    API --> NEO["Neo4j Graph DB"]
    NEO --> INS["Insight Engine (PageRank/Centrality/Clusters)"]
    INS --> API
```

## Graph Model

### Nodes
- `Book`
- `Author`
- `Concept`
- `Field`

### Relationships
- `WRITTEN_BY`
- `MENTIONS`
- `RELATED_TO`
- `INFLUENCED_BY`
- `CONTRADICTS`
- `EXPANDS`
- `BELONGS_TO`

## Run Locally

### Option 1: Docker Compose

1. From `bookgraph/docker`, run:
   ```bash
   docker compose up --build
   ```
2. Open:
   - Frontend: `http://localhost:3000`
   - Backend docs: `http://localhost:8000/docs`
   - Neo4j Browser: `http://localhost:7474` (user `neo4j`, password `bookgraph`)

### Option 2: Backend only (local Python)

1. Create env and install:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy env:
   ```bash
   cp .env.example .env
   ```
3. Start API:
   ```bash
   uvicorn main:app --reload
   ```

## LLM Provider Configuration

Switch providers without code changes via environment variables:

- OpenAI
  - `MODEL_PROVIDER=openai`
  - `OPENAI_API_KEY=<your_key>`
  - Optional: `OPENAI_MODEL=gpt-4o-mini`
- OpenRouter
  - `MODEL_PROVIDER=openrouter`
  - `OPENROUTER_API_KEY=<your_key>`
  - Optional: `OPENROUTER_MODEL=openai/gpt-4o-mini`
- Ollama
  - `MODEL_PROVIDER=ollama`
  - Optional: `OLLAMA_BASE_URL=http://localhost:11434/v1`
  - Optional: `OLLAMA_MODEL=llama3.1:8b`

Auto mode: `MODEL_PROVIDER=auto` uses OpenRouter first, then OpenAI (if keys are present). If no usable provider credentials are set, BookGraph falls back to deterministic heuristics.

## API Examples

### Add Book

```bash
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{"title":"Clean Code"}'
```

### Get Graph

```bash
curl http://localhost:8000/graph
```

### Get Insights

```bash
curl http://localhost:8000/insights
```

## Contribution Guide

1. Fork the repo and create a branch with prefix `codex/`.
2. Keep modules small and typed; use service-layer orchestration, not route-level business logic.
3. Add tests for ingestion, agent parsing, and graph query behavior before merging larger changes.
4. Open a PR with architecture notes and sample payloads.

## Roadmap

- Reading path generation
- Knowledge gap detection
- Multi-source ingestion (papers, videos)
- Semantic question answering over graph
