// Server-only loader for the markdown docs in content/docs/. The docs live at
// the repo root, so we look next to the app (the Docker image copies them into
// /app/content) and two levels up (local `next dev` from apps/trace-ui).
import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";

export interface DocMeta {
  slug: string;
  title: string;
  summary: string;
  order: number;
}

export interface Doc extends DocMeta {
  body: string;
}

const CANDIDATE_DIRS = [
  process.env.DOCS_DIR,
  join(process.cwd(), "content", "docs"),
  join(process.cwd(), "..", "..", "content", "docs"),
].filter((dir): dir is string => Boolean(dir));

function docsDir(): string | null {
  for (const dir of CANDIDATE_DIRS) {
    try {
      if (statSync(dir).isDirectory()) return dir;
    } catch {
      // try the next candidate
    }
  }
  return null;
}

function parseFrontmatter(raw: string): {
  data: Record<string, string>;
  body: string;
} {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { data: {}, body: raw };

  const data: Record<string, string> = {};
  for (const line of match[1].split(/\r?\n/)) {
    const colon = line.indexOf(":");
    if (colon === -1) continue;

    const key = line.slice(0, colon).trim();
    let value = line.slice(colon + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    data[key] = value;
  }

  return { data, body: raw.slice(match[0].length) };
}

function titleFromSlug(slug: string): string {
  return (slug.split("/").pop() ?? slug)
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function toMeta(slug: string, data: Record<string, string>): DocMeta {
  const parsedOrder = Number.parseInt(data.order ?? "", 10);
  return {
    slug,
    title: data.title || titleFromSlug(slug),
    summary: data.summary || "",
    order: Number.isFinite(parsedOrder) ? parsedOrder : Number.MAX_SAFE_INTEGER,
  };
}

export function getDocsIndex(): DocMeta[] {
  const dir = docsDir();
  if (!dir) return [];

  return readdirSync(/* turbopackIgnore: true */ dir)
    .filter((file) => file.endsWith(".md") && file !== "index.md")
    .map((file) => {
      const slug = file.replace(/\.md$/, "");
      const raw = readFileSync(
        join(/* turbopackIgnore: true */ dir, file),
        "utf-8"
      );
      return toMeta(slug, parseFrontmatter(raw).data);
    })
    .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));
}

export function getDoc(slug: string): Doc | null {
  const dir = docsDir();
  if (!dir || !/^[a-z0-9-]+(?:\/[a-z0-9-]+)*$/i.test(slug)) return null;

  try {
    const raw = readFileSync(
      join(/* turbopackIgnore: true */ dir, `${slug}.md`),
      "utf-8"
    );
    const { data, body } = parseFrontmatter(raw);
    return { ...toMeta(slug, data), body };
  } catch {
    return null;
  }
}
