import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Prism",
  description: "Enterprise knowledge graph explorer"
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
                  <h1 className="brand-title">Prism</h1>
                  <p className="brand-subtitle">AI Knowledge Graph for enterprise systems, resources, and dependencies</p>
                </div>
                <nav className="nav">
                  <Link href="/resources">Resources</Link>
                  <Link href="/graph">Graph</Link>
                  <Link href="/insights">Insights</Link>
                  <Link href="/chat">Chat</Link>
                </nav>
              </div>
            </div>
          </header>
          <section>
            <p className="page-subtitle">
              Add enterprise resources, enrich with AI, explore graph structure, and ask grounded questions.
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
