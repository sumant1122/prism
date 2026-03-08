from __future__ import annotations

from typing import Any

from app.agents.llm_client import LLMClient, LLMError


class InsightAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def synthesize(self, insight_payload: dict[str, Any]) -> dict[str, Any]:
        if not self._llm_client:
            return self._fallback_summary(insight_payload, reason="no_llm_client")

        system_prompt = (
            "You are an enterprise intelligence analyst for a resource knowledge graph. "
            "Return strict JSON with keys: summary (string), key_findings (string array), "
            "recommended_actions (string array), graph_health_score (integer 0-100)."
        )
        user_prompt = (
            "Given the following graph analytics payload, produce concise and actionable insights.\n\n"
            f"{insight_payload}"
        )
        try:
            result = self._llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return {
                "summary": str(result.get("summary") or "").strip(),
                "key_findings": [str(x).strip() for x in result.get("key_findings", []) if str(x).strip()],
                "recommended_actions": [
                    str(x).strip() for x in result.get("recommended_actions", []) if str(x).strip()
                ],
                "graph_health_score": self._clamp_score(result.get("graph_health_score")),
            }
        except LLMError:
            return self._fallback_summary(insight_payload, reason="llm_error")

    def _fallback_summary(self, payload: dict[str, Any], reason: str) -> dict[str, Any]:
        stats = payload.get("graph_stats", {})
        resources = int(stats.get("resources", 0))
        density = float(stats.get("inter_resource_relationship_density", 0))
        central = payload.get("central_resources", {}).get("central_resources", [])
        top_name = central[0]["name"] if central else "N/A"
        gaps = payload.get("missing_topics", {}).get("missing_topics", [])
        gap_fields = [row["field"] for row in gaps[:3] if row.get("field")]
        health = min(100, int((resources * 4) + (density * 120)))
        findings = [
            f"Top central resource: {top_name}",
            f"Inter-resource relationship density: {density:.2f}",
            f"Total resources analyzed: {resources}",
        ]
        actions = [
            "Ingest resources that strengthen weak topic areas.",
            "Increase inter-resource relationships for better insight quality.",
            "Add resources around underrepresented fields to reduce graph sparsity.",
        ]
        if gap_fields:
            actions[0] = f"Add resources in sparse fields: {', '.join(gap_fields)}."
        reason_message = {
            "no_llm_client": "Generated deterministic insights because no LLM client was configured.",
            "llm_error": "Generated deterministic insights because the LLM call failed or returned invalid JSON.",
        }.get(reason, "Generated deterministic insights.")
        return {
            "summary": reason_message,
            "key_findings": findings,
            "recommended_actions": actions,
            "graph_health_score": health,
        }

    def _clamp_score(self, score: Any) -> int:
        try:
            value = int(score)
        except (TypeError, ValueError):
            value = 50
        return max(0, min(100, value))
