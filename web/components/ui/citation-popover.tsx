"use client";

import { motion } from "framer-motion";
import type { Citation } from "@/lib/types";

interface CitationPopoverProps {
  citation: Citation;
}

export function CitationPopover({ citation }: CitationPopoverProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, scale: 0.95 }}
      animate={{ opacity: 1, y: -40, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      className="absolute z-50 w-80 p-3 bg-white rounded-lg shadow-xl border border-gray-200"
    >
      <p className="text-sm font-semibold text-gray-900">{citation.document_title}</p>
      <p className="text-xs text-gray-600 mt-1">{citation.section_title}</p>
      <p className="text-xs text-gray-700 mt-2 line-clamp-2">
        {citation.quote.slice(0, 80)}...
      </p>
      <div className="mt-2 pt-2 border-t border-gray-100">
        <p className="text-xs text-gray-500">
          Score: {citation.score.toFixed(3)}
        </p>
      </div>
    </motion.div>
  );
}
