export type ConceptDetail = {
  name: string;
  category: string;
  summary: string;
  importance: string;
  evidence: string[];
  learnNext: string;
  confidence: number;
};

export type LearningPathStep = {
  title: string;
  description: string;
};

export type RepoAnalysisResponse = {
  source: "github";
  externalId: string;
  name: string;
  owner: string;
  description: string;
  repoUrl: string;
  starCount: number;
  forkCount: number;
  updatedAt: string;
  topics: string[];
  concepts: string[];
  fields: string[];
  repoSummary: string;
  architectureSummary: string;
  conceptDetails: ConceptDetail[];
  learningPath: LearningPathStep[];
  detectedPatterns: string[];
  languages: string[];
  analysisMode: "heuristic" | "llm";
};
