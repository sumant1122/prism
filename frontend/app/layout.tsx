import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Repo Teacher",
  description: "Learn computer science concepts through your own GitHub repository."
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <main>
          <header className="app-header">
            <div className="topbar">
              <div className="topbar-row">
                <div>
                  <h1 className="brand-title">Repo Teacher</h1>
                  <p className="brand-subtitle">AI-guided repo analysis that teaches the CS concepts already living in your code</p>
                </div>
                <nav className="nav">
                  <Link href="/resources">Analyze</Link>
                  <Link href="/graph">Graph</Link>
                  <Link href="/insights">Insights</Link>
                  <Link href="/chat">Chat</Link>
                </nav>
              </div>
            </div>
          </header>
          <section>
            <p className="page-subtitle">
              Turn a GitHub repo into an explainable concept map, then explore the patterns, architecture, and learning path behind it.
            </p>
          </section>
          <section>
            {children}
          </section>
        </main>
      </body>
    </html>
  );
}
