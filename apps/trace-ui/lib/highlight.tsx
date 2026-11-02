// Dependency-free syntax highlighter for the three languages the trace shows:
// python (generated sandbox code), json (tool outputs, plans), sql (sql_query).
// Emits React spans with Tailwind color classes - keeps the bundle small and
// the CI build clean (no react-syntax-highlighter / shiki / prism).
import type { ReactNode } from "react";

const PY_KEYWORDS = new Set(
  "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass print raise return try while with yield def print".split(
    /\s+/
  )
);
const PY_BUILTINS = new Set(
  "len range sum int str float list dict set bool print open file min max zip map filter isinstance abs round enumerate any all sorted reversed".split(
    /\s+/
  )
);

function tokenize(src: string, lang: "python" | "json" | "sql"): ReactNode[] {
  // Word / number / string / comment regex; anything else passes through.
  const tokenRe = lang === "json" ? /("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?)|([a-zA-Z_$][\w$]*)|(\s+)|(.)/g : /("""[\s\S]*?"""|''''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(#[^\n]*)|(-?\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|(\s+)|(.)/g;
  const out: ReactNode[] = [];
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = tokenRe.exec(src))) {
    out.push(
      <span key={i++} className={`tok-${classFor(lang, m[0])}`}>
        {m[0]}
      </span>
    );
    if (tokenRe.lastIndex === m.index) tokenRe.lastIndex++;
  }
  return out;
}

function classFor(lang: "python" | "json" | "sql", tok: string): string {
  const t = tok.trim();
  if (tok === t && t.length > 0) {
    // single-char or word token
    if (lang === "python") {
      if (PY_KEYWORDS.has(t)) return "kw";
      if (PY_BUILTINS.has(t)) return "bi";
      if (/^[A-Z][A-Za-z0-9_]*$/.test(t)) return "type";
    }
    if (lang === "sql") {
      if (/^(select|from|where|insert|update|delete|create|drop|alter|join|left|inner|group|by|order|having|limit|as|and|or|not|in|is|null|distinct|case|when|then|else|end|union|with|table|values|set|on)/i.test(t)) return "kw";
    }
  }
  const first = tok[0];
  if (first === '"' || first === "'") return "str";
  if (/^\d/.test(tok)) return "num";
  if (first === "#") return "com";
  if (lang === "json" && /^(true|false|null)$/.test(t)) return "kw";
  if (lang === "sql" && /^(true|false|now|interval|date|timestamp)$/i.test(t)) return "bi";
  return "";
}

export function highlight(src: string, lang: "python" | "json" | "sql"): ReactNode {
  if (!src) return null;
  return <code className="hl text-[13px] leading-relaxed font-mono">{tokenize(src, lang)}</code>;
}
