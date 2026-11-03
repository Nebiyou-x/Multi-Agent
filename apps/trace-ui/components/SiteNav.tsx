"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { ActiveLink } from "./ActiveLink";

const NAV = [
  { href: "/traces", label: "Traces" },
  { href: "/evals", label: "Evals" },
  { href: "/docs", label: "Docs" },
];

export default function SiteNav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav" aria-label="Primary">
      {/* Mobile menu button and GitHub link remain unchanged */}
      <div id="primary-nav" className={`nav__links${open ? " is-open" : ""}`}>
        {NAV.map((item) => (
          <Suspense
            key={item.href}
            fallback={
              <Link href={item.href} className="nav__link" onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            }
          >
            <ActiveLink
              href={item.href}
              label={item.label}
              onClick={() => setOpen(false)}
            />
          </Suspense>
        ))}
        {/* GitHub external link remains unchanged */}
      </div>
    </nav>
  );
}