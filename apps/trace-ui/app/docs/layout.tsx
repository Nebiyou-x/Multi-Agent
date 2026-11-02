"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const DOCS_NAV = [
  { label: "Overview", href: "/docs" },
  { label: "Getting started", href: "/docs/getting-started" },
  {
    label: "Usage",
    children: [
      { label: "Running a task", href: "/docs/running-a-task" },
      { label: "Tools", href: "/docs/tools" },
      { label: "Sandbox", href: "/docs/sandbox" },
    ],
  },
  { label: "Architecture", href: "/docs/architecture" },
  { label: "Design decisions", href: "/docs/design-decisions" },
  {
    label: "Evaluation",
    children: [
      { label: "Methodology", href: "/docs/methodology" },
      { label: "Results", href: "/docs/results" },
    ],
  },
  { label: "Roadmap", href: "/docs/roadmap" },
];

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="shell docs-shell">
      <button
        type="button"
        className="btn btn--quiet btn--small docs-mobile-toggle"
        aria-expanded={mobileOpen}
        aria-controls="docs-nav"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? "Close docs menu" : "Docs menu"}
      </button>

      <aside className={`docs-side${mobileOpen ? " is-open" : ""}`}>
        <nav id="docs-nav" className="docs-nav" aria-label="Documentation">
          {DOCS_NAV.map((item) =>
            item.children ? (
              <div key={item.label} className="docs-nav__group">
                <div className="docs-nav__label">{item.label}</div>
                {item.children.map((child) => (
                  <Link
                    key={child.href}
                    href={child.href}
                    className="docs-nav__link"
                    aria-current={pathname === child.href ? "page" : undefined}
                  >
                    {child.label}
                  </Link>
                ))}
              </div>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className="docs-nav__link"
                aria-current={pathname === item.href ? "page" : undefined}
              >
                {item.label}
              </Link>
            )
          )}
        </nav>
      </aside>

      <div className="docs-main">{children}</div>
    </div>
  );
}
