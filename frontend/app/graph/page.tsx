import GraphCanvas from "@/components/graph/GraphCanvas";

export default function GraphPage() {
  return (
    <div className="card">
      <h2 className="page-title">Concept Graph</h2>
      <p className="page-subtitle">Explore how repos, concepts, and learning signals connect across the graph.</p>
      <GraphCanvas />
    </div>
  );
}
