from __future__ import annotations

from pydantic import BaseModel, Field


class AddResourceRequest(BaseModel):
    source: str = Field(pattern="^(github|servicenow|manual)$")
    identifier: str = Field(min_length=1, max_length=300)
    name: str | None = None
    description: str | None = None
    owner: str | None = None
    resource_count: int | None = None
    tags: list[str] = Field(default_factory=list)


class ResourceResponse(BaseModel):
    source: str
    external_id: str
    name: str
    owner: str
    description: str = ""
    resource_count: int = 0
    tags: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    relationships_created: int = 0


class GraphResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class InsightResponse(BaseModel):
    central_resources: dict
    clusters: dict
    missing_topics: dict
    graph_stats: dict = Field(default_factory=dict)
    coverage: dict = Field(default_factory=dict)
    recommendations: list[dict] = Field(default_factory=list)
    narrative: dict = Field(default_factory=dict)
    time_delta: dict = Field(default_factory=dict)
    quality_scores: dict = Field(default_factory=dict)
    reading_paths: list[dict] = Field(default_factory=list)
    overlap_contradiction: dict = Field(default_factory=dict)
    sparse_bridges: list[dict] = Field(default_factory=list)
    field_dashboards: list[dict] = Field(default_factory=list)
    freshness: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    scope: str = Field(default="auto", pattern="^(auto|resource|platform|concept|field)$")
    k: int = Field(default=20, ge=5, le=100)


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    citations: list[str] = Field(default_factory=list)
    evidence_nodes: list[dict] = Field(default_factory=list)
    evidence_edges: list[dict] = Field(default_factory=list)
    context_size: dict = Field(default_factory=dict)
    mode: str = "fallback"
    provider: str = "none"
    fallback_reason: str | None = None
