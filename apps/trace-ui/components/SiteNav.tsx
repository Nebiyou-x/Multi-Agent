"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV = [
  { href: "/traces", label: "Traces" },
  { href: "/evals", label: "Evals" },
  { href: "/docs", label: "Docs" },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SiteNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav" aria-label="Primary">
      <button
        type="button"
        className="nav__toggle"
        aria-expanded={open}
        aria-controls="primary-nav"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "Close" : "Menu"}
      </button>
      <div id="primary-nav" className={`nav__links${open ? " is-open" : ""}`}>
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="nav__link"
            aria-current={isActive(pathname, item.href) ? "page" : undefined}
            onClick={() => setOpen(false)}
          >
            {item.label}
          </Link>
        ))}
        <a
          href="https://github.com/Nebiyou-x/Multi-Agent"
          target="_blank"
          rel="noopener noreferrer"
          className="nav__link nav__link--ext"
        >
          GitHub
        </a>
      </div>
    </nav>
  );
}
