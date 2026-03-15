import { NextResponse } from "next/server";

import { analyzeGithubRepository } from "@/lib/repo-analysis";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as { identifier?: string };
    const identifier = payload.identifier?.trim() || "";
    if (!identifier) {
      return NextResponse.json({ error: "Enter a GitHub repository URL or owner/repo." }, { status: 400 });
    }

    const analysis = await analyzeGithubRepository(identifier);
    return NextResponse.json(analysis, { status: 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to analyze this repository right now.";
    const status = /enter a github repository|does not look like a repository/i.test(message) ? 400 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
