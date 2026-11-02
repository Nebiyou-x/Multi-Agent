import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { getDoc, getDocsIndex } from "@/lib/docs";

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-4xl font-bold mb-6 mt-8 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-2xl font-bold mb-4 mt-10 border-b border-neutral-800 pb-2">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xl font-semibold mb-3 mt-6">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-lg font-semibold mb-2 mt-5">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="mb-4 text-neutral-300 leading-relaxed max-w-2xl">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-outside mb-4 ml-5 space-y-2 text-neutral-300 max-w-2xl">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside mb-4 ml-5 space-y-2 text-neutral-300 max-w-2xl">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1 leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-indigo-500 pl-4 italic text-neutral-400 my-4">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-indigo-300 underline underline-offset-2 hover:text-indigo-200"
    >
      {children}
    </a>
  ),
  code: ({ className, children }) => (
    <code className={className}>{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="bg-neutral-900 p-4 rounded-lg overflow-x-auto mb-6 text-sm font-mono text-neutral-300">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto mb-6">
      <table className="w-full border-collapse text-sm text-left">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-neutral-700">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="py-2 pr-6 font-semibold text-neutral-100 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="py-2 pr-6 align-top text-neutral-300 border-t border-neutral-800">
      {children}
    </td>
  ),
  hr: () => <hr className="my-8 border-neutral-800" />,
  strong: ({ children }) => (
    <strong className="font-semibold text-neutral-100">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-neutral-200">{children}</em>,
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
    <div className="max-w-3xl">
      <h1 className="text-4xl font-bold mb-6 mt-8 first:mt-0">Documentation</h1>
      <p className="mb-8 text-neutral-300 leading-relaxed max-w-2xl">
        How Agent Forge runs a task, isolates generated code, records traces, and evaluates a configuration.
      </p>
      <ul className="divide-y divide-neutral-800 border-t border-neutral-800">
        {docs.map((doc) => (
          <li key={doc.slug} className="py-5">
            <Link
              href={`/docs/${doc.slug}`}
              className="text-lg font-semibold text-neutral-100 underline decoration-neutral-700 underline-offset-4 hover:decoration-neutral-100"
            >
              {doc.title}
            </Link>
            {doc.summary && (
              <p className="mt-2 text-neutral-400 leading-relaxed">{doc.summary}</p>
            )}
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
      <div className="text-center py-12">
        <h1 className="text-2xl font-bold mb-2">Page not found</h1>
        <p className="text-neutral-400">The documentation page &quot;{slug}&quot; does not exist.</p>
      </div>
    );
  }

  return (
    <div className="docs-md max-w-3xl">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {doc.body}
      </ReactMarkdown>
    </div>
  );
}
