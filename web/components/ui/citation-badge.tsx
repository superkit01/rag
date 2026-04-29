"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Citation } from "@/lib/types";
import { CitationPopover } from "./citation-popover";

interface CitationBadgeProps {
  citation: Citation;
  index: number;
}

export function CitationBadge({ citation, index }: CitationBadgeProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setIsHovered(true)}
      onBlur={() => setIsHovered(false)}
      tabIndex={0}
      role="button"
      aria-label={`Show citation ${index} details`}
    >
      <sup className="inline-flex items-center justify-center w-5 h-5 text-xs font-semibold text-blue-700 bg-blue-100 rounded cursor-pointer hover:bg-blue-200 transition-colors">
        {index}
      </sup>
      <AnimatePresence>
        {isHovered && (
          <CitationPopover citation={citation} />
        )}
      </AnimatePresence>
    </span>
  );
}
