"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import type { Citation } from "@/lib/types";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return "bg-green-100 text-green-700 border-green-200";
    if (score >= 0.5) return "bg-yellow-100 text-yellow-700 border-yellow-200";
    return "bg-red-100 text-red-700 border-red-200";
  };

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="p-3 rounded-lg border bg-white hover:shadow-md transition-shadow"
    >
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex-1">
          <p className="text-sm font-semibold">{citation.document_title || "未知文档"}</p>
          <p className="text-xs text-gray-600 mt-0.5">{citation.section_title || ""}</p>
        </div>
        <button
          className="text-gray-400 hover:text-gray-600"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? "收起引用详情" : "展开引用详情"}
        >
          {isExpanded ? "−" : "+"}
        </button>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-gray-700 mt-3 leading-relaxed">
              {citation.quote || "暂无内容"}
            </p>

            <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getRelevanceColor(citation.score)}`}>
                  {citation.score >= 0.8 ? "高相关" : citation.score >= 0.5 ? "中相关" : "低相关"}
                </span>
                <span className="text-xs text-gray-500">
                  片段: {citation.fragment_id}
                </span>
              </div>

              <Link
                href={`/documents/${citation.document_id}`}
                className="text-xs text-blue-600 hover:underline"
                aria-label={`查看文档 ${citation.document_title || ""}`}
              >
                查看完整文档 →
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
