import GraphCanvas from "@/components/graph/GraphCanvas";

export default function GraphPage() {
  return (
    <div className="card">
      <h2 className="page-title">Knowledge Graph</h2>
      <p className="page-subtitle">Explore enterprise resources, platforms, concepts, and dependency links.</p>
      <GraphCanvas />
    </div>
  );
}
