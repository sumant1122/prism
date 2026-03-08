from __future__ import annotations

from typing import Any

from app.agents.llm_client import LLMClient, LLMError


class ChatAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def answer(
        self,
        *,
        question: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        graph_stats: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._llm_client:
            return self._fallback(question, nodes, edges)

        context = {
            "graph_stats": graph_stats,
            "nodes": nodes[:120],
            "edges": edges[:220],
        }
        system_prompt = (
            "You answer user questions about a book knowledge graph. "
            "Use only provided graph context. Return strict JSON with keys: "
            "answer (string), confidence (number 0..1), citations (array of node ids)."
        )
        user_prompt = f"Question: {question}\n\nGraph context:\n{context}"
        try:
            payload = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return {
                "answer": str(payload.get("answer") or "").strip(),
                "confidence": self._normalize_confidence(payload.get("confidence")),
                "citations": [str(x) for x in payload.get("citations", [])][:12],
            }
        except LLMError:
            return self._fallback(question, nodes, edges)

    def _fallback(self, question: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
        books = [n for n in nodes if n.get("type") == "book"]
        concepts = [n for n in nodes if n.get("type") == "concept"]
        mentions = [e for e in edges if e.get("type") == "MENTIONS"]
        answer = (
            f"I analyzed {len(nodes)} nodes and {len(edges)} edges for your question: '{question}'. "
            f"The subgraph contains {len(books)} books, {len(concepts)} concepts, and {len(mentions)} mention links."
        )
        citations = [str(n["id"]) for n in books[:3] if n.get("id")]
        return {"answer": answer, "confidence": 0.45, "citations": citations}

    def _normalize_confidence(self, value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, parsed))

