"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { CitationBadge } from "./citation-badge";
import type { Citation } from "@/lib/types";

interface MarkdownRendererProps {
  content: string;
  citations?: Citation[];
}

export function MarkdownRenderer({ content, citations = [] }: MarkdownRendererProps) {
  const citationMap = useMemo(
    () => new Map(citations.map((c, i) => [i + 1, c])),
    [citations]
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const language = match ? match[1] : "";

          return !inline && language ? (
            <SyntaxHighlighter
              style={oneDark}
              language={language}
              PreTag="div"
              className="rounded-lg"
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono" {...props}>
              {children}
            </code>
          );
        },
        p({ children }) {
          const childStr = String(children);
          if (/__CITATION_(\d+)__/.test(childStr)) {
            const parts = childStr.split(/(__CITATION_\d+__)/);
            return (
              <p className="mb-2 last:mb-0">
                {parts.map((part, i) => {
                  const match = part.match(/__CITATION_(\d+)__/);
                  if (match) {
                    const citationNum = parseInt(match[1], 10);
                    const citation = citationMap.get(citationNum);
                    return citation ? (
                      <CitationBadge key={i} citation={citation} index={citationNum} />
                    ) : null;
                  }
                  return <span key={i}>{part}</span>;
                })}
              </p>
            );
          }
          return <p className="mb-2 last:mb-0">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>;
        },
        h1({ children }) {
          return <h1 className="text-2xl font-bold mb-3">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-xl font-bold mb-2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-lg font-semibold mb-2">{children}</h3>;
        },
        blockquote({ children }) {
          return <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2">{children}</blockquote>;
        },
        a({ href, children }) {
          return (
            <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          );
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-4">
              <table className="min-w-full border border-gray-300">{children}</table>
            </div>
          );
        },
        thead({ children }) {
          return <thead className="bg-gray-100">{children}</thead>;
        },
        th({ children }) {
          return <th className="px-4 py-2 border-b text-left font-semibold">{children}</th>;
        },
        td({ children }) {
          return <td className="px-4 py-2 border-b">{children}</td>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
