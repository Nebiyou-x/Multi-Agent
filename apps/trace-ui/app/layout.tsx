import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Forge · multi-agent orchestration",
  description: "Inspect traces, read architecture, understand evaluation results",
};

export default function RootLayout({ children }: any) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full flex flex-col">
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header className="titleblock">
          <div className="container titleblock__in">
            <Link href="/" className="titleblock__mark">
              Agent Forge
              <span className="titleblock__sub">multi-agent orchestration</span>
            </Link>
            <nav className="titleblock__links" aria-label="Primary">
              <Link href="/docs" className="titleblock__link">
                Docs
              </Link>
              <Link href="/traces" className="titleblock__link">
                Traces
              </Link>
              <Link href="/evals" className="titleblock__link">
                Evals
              </Link>
              <a
                href="https://github.com/Nebiyou-x/Multi-Agent"
                target="_blank"
                rel="noopener noreferrer"
                className="titleblock__link"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main id="main" className="flex-1">
          {children}
        </main>
        <footer className="colophon">
          <div className="container colophon__in">
            <div>
              <div className="colophon__mark">Agent Forge</div>
              <p className="colophon__line">Multi-agent AI system with sandboxed tool execution.</p>
            </div>
            <div className="colophon__links">
              <Link href="/docs/design-decisions">Design decisions</Link>
              <a href="https://github.com/Nebiyou-x/Multi-Agent" target="_blank" rel="noopener noreferrer">
                Source
              </a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
