"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const DOCS_NAV = [
  { label: "Overview", href: "/docs" },
  { label: "Getting Started", href: "/docs/getting-started" },
  {
    label: "Usage",
    children: [
      { label: "Running a Task", href: "/docs/running-a-task" },
      { label: "Tools", href: "/docs/tools" },
      { label: "Sandbox", href: "/docs/sandbox" },
    ],
  },
  { label: "Architecture", href: "/docs/architecture" },
  { label: "Design Decisions", href: "/docs/design-decisions" },
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
    <div className="flex flex-col sm:flex-row gap-8 mx-auto w-full max-w-7xl px-6 py-10">
      <aside className={`${mobileOpen ? "block" : "hidden"} sm:block sm:w-56 flex-shrink-0`}>
        <nav className="space-y-1 sticky top-24">
          {DOCS_NAV.map((item) =>
            item.children ? (
              <div key={item.label}>
                <div className="px-3 py-2 text-xs font-semibold text-neutral-500 uppercase tracking-wider mt-4">
                  {item.label}
                </div>
                <div className="space-y-1 pl-2">
                  {item.children.map((child) => (
                    <Link
                      key={child.href}
                      href={child.href}
                      className={`block px-3 py-2 text-sm rounded transition-colors ${
                        pathname === child.href
                          ? "bg-indigo-600/20 text-indigo-300 font-medium"
                          : "text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900/30"
                      }`}
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              </div>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 text-sm rounded transition-colors ${
                  pathname === item.href
                    ? "bg-indigo-600/20 text-indigo-300 font-medium"
                    : "text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900/30"
                }`}
              >
                {item.label}
              </Link>
            )
          )}
        </nav>
      </aside>

      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="sm:hidden mb-4 px-3 py-2 text-sm text-neutral-400 border border-neutral-700 rounded hover:text-neutral-100"
      >
        {mobileOpen ? "Close menu" : "Open menu"}
      </button>

      <div className="flex-1 min-w-0">
        <div className="prose prose-invert max-w-none text-neutral-300">
          {children}
        </div>
      </div>
    </div>
  );
}
