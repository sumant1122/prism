import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Repo Teacher",
  description: "Turn a GitHub repository into a clear, visual lesson on the computer science ideas inside it.",
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
                  <p className="brand-subtitle">A richer way to learn software through the code you already ship</p>
                </div>
                <nav className="nav">
                  <a href="#analyzer">Analyze</a>
                  <a href="#how-it-works">How It Works</a>
                  <a href="#results">Results</a>
                </nav>
              </div>
            </div>
          </header>
          <section>
            {children}
          </section>
        </main>
      </body>
    </html>
  );
}
