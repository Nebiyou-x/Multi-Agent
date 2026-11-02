import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { getDoc, getDocsIndex } from "@/lib/docs";

const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="docs-h1">{children}</h1>,
  h2: ({ children }) => <h2 className="docs-h2">{children}</h2>,
  h3: ({ children }) => <h3 className="docs-h3">{children}</h3>,
  h4: ({ children }) => <h4 className="docs-h4">{children}</h4>,
  p: ({ children }) => <p className="docs-p">{children}</p>,
  ul: ({ children }) => <ul className="docs-md-list">{children}</ul>,
  ol: ({ children }) => <ol className="docs-md-list">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  blockquote: ({ children }) => <blockquote className="docs-blockquote">{children}</blockquote>,
  a: ({ href, children }) => (
    <a href={href} className="docs-link">
      {children}
    </a>
  ),
  code: ({ className, children }) =>
    className ? <code className={className}>{children}</code> : <code className="docs-code">{children}</code>,
  pre: ({ children }) => <pre className="docs-pre">{children}</pre>,
  table: ({ children }) => (
    <div className="docs-table-wrap">
      <table className="docs-table">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  th: ({ children }) => <th>{children}</th>,
  td: ({ children }) => <td>{children}</td>,
  hr: () => <hr className="docs-hr" />,
  strong: ({ children }) => <strong className="docs-strong">{children}</strong>,
  em: ({ children }) => <em className="docs-em">{children}</em>,
  img: ({ src, alt }) => <img src={src} alt={alt ?? ""} className="docs-img" />,
};

export function generateStaticParams() {
  return [
    { slug: [] as string[] },
    ...getDocsIndex().map((doc) => ({ slug: doc.slug.split("/") })),
  ];
}

function DocsIndex() {
  const docs = getDocsIndex();

  return (
    <div className="docs-content">
      <h1 className="docs-h1">Documentation</h1>
      <p className="docs-p">
        How Agent Forge runs a task, isolates generated code, records traces, and evaluates a configuration.
      </p>
      <ul className="doc-index">
        {docs.map((doc) => (
          <li key={doc.slug} className="doc-index__item">
            <Link href={`/docs/${doc.slug}`} className="doc-index__title">
              {doc.title}
            </Link>
            {doc.summary && <p className="doc-index__summary">{doc.summary}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function Page({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { slug: slugParam } = await params;
  const slug = slugParam?.join("/") || "index";
  const doc = getDoc(slug);

  if (!doc) {
    if (slug === "index") return <DocsIndex />;

    return (
      <div className="empty">
        <h1 className="empty__title">Page not found</h1>
        <p className="empty__line">The documentation page &quot;{slug}&quot; does not exist.</p>
      </div>
    );
  }

  return (
    <div className="docs-md docs-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {doc.body}
      </ReactMarkdown>
    </div>
  );
}
