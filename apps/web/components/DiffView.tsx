"use client";

import React, { useState } from "react";
import { Check, X, ShieldAlert, Sparkles } from "lucide-react";

interface RemovedField {
  group: string;
  tag: string;
  value_preview: string;
  category?: string;
}

interface DiffViewProps {
  removed: RemovedField[];
}

export function DiffView({ removed }: DiffViewProps) {
  const [filter, setFilter] = useState("");

  const filtered = removed.filter(
    (r) =>
      r.tag.toLowerCase().includes(filter.toLowerCase()) ||
      r.group.toLowerCase().includes(filter.toLowerCase()) ||
      r.value_preview.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-teal-600" />
            <span>Removed Tags ({removed.length})</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            These metadata atoms existed in the uploaded file and were verified as removed from the cleaned output.
          </p>
        </div>

        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter removed tags..."
          className="px-3.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-teal-500 w-full sm:w-56"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-slate-400 py-4 text-center">No removed tags matching filter.</p>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
          {filtered.map((r, i) => (
            <div key={i} className="py-2.5 flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 truncate">
                <span className="text-red-500 flex-shrink-0">
                  <X className="w-4 h-4" />
                </span>
                <span className="font-mono line-through text-slate-400 dark:text-slate-500 font-medium truncate">
                  {r.group}:{r.tag}
                </span>
                {r.category && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900 capitalize">
                    {r.category}
                  </span>
                )}
              </div>

              <span className="font-mono text-slate-400 dark:text-slate-500 truncate max-w-sm line-through text-right">
                {r.value_preview}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
