import type { Metadata } from "next";
import Link from "next/link";
import SiteNav from "@/components/SiteNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Forge, multi-agent orchestration",
  description: "Inspect traces, read architecture, and understand evaluation results.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Mono:wght@400;500&family=Host+Grotesk:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header className="appbar">
          <div className="shell appbar__in">
            <Link href="/" className="brand" aria-label="Agent Forge home">
              <span className="brand__mark">Agent Forge</span>
              <span className="brand__sub">trace viewer</span>
            </Link>
            <SiteNav />
          </div>
        </header>
        <main id="main">{children}</main>
        <footer className="colophon">
          <div className="shell colophon__in">
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
