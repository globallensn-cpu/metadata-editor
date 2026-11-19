"use client";

import React, { useState } from "react";
import { Info, AlertTriangle, ShieldCheck, HelpCircle } from "lucide-react";

interface SurvivorField {
  group: string;
  tag: string;
  survivorClass?: "structural" | "identifying" | "unknown";
  survivor_class?: "structural" | "identifying" | "unknown";
  class?: "structural" | "identifying" | "unknown";
  valuePreview?: string;
  value_preview?: string;
  reason: string;
}

interface SurvivorsListProps {
  survivors: SurvivorField[];
}

export function SurvivorsList({ survivors }: SurvivorsListProps) {
  const [tab, setTab] = useState<"structural" | "identifying" | "all">("all");

  const getSurvivorClass = (s: SurvivorField) =>
    s.survivorClass || s.survivor_class || s.class || "unknown";

  const getValuePreview = (s: SurvivorField) =>
    s.valuePreview || s.value_preview || "";

  const structuralList = survivors.filter((s) => getSurvivorClass(s) === "structural");
  const identifyingList = survivors.filter((s) => getSurvivorClass(s) === "identifying");

  const activeList =
    tab === "structural" ? structuralList : tab === "identifying" ? identifyingList : survivors;

  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Info className="w-5 h-5 text-teal-600" />
            <span>Surviving Tags ({survivors.length})</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Reaboard never claims 100% clean. These fields persist in the output and are classified below.
          </p>
        </div>

        {/* Tab filters */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-semibold">
          <button
            onClick={() => setTab("all")}
            className={`px-3 py-1 rounded-lg transition ${
              tab === "all" ? "bg-white dark:bg-slate-900 shadow-sm text-slate-900 dark:text-slate-100" : "text-slate-500"
            }`}
          >
            All ({survivors.length})
          </button>
          <button
            onClick={() => setTab("structural")}
            className={`px-3 py-1 rounded-lg transition ${
              tab === "structural"
                ? "bg-white dark:bg-slate-900 shadow-sm text-teal-600"
                : "text-slate-500"
            }`}
          >
            Structural ({structuralList.length})
          </button>
          {identifyingList.length > 0 && (
            <button
              onClick={() => setTab("identifying")}
              className={`px-3 py-1 rounded-lg transition ${
                tab === "identifying"
                  ? "bg-white dark:bg-slate-900 shadow-sm text-amber-600"
                  : "text-amber-600 font-bold"
              }`}
            >
              Identifying ({identifyingList.length})
            </button>
          )}
        </div>
      </div>

      {activeList.length === 0 ? (
        <p className="text-xs text-slate-400 py-4 text-center">No surviving tags in this category.</p>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
          {activeList.map((s, i) => {
            const sClass = getSurvivorClass(s);
            const valPrev = getValuePreview(s);
            const isStructural = sClass === "structural";
            const isIdentifying = sClass === "identifying";

            return (
              <div key={i} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2 truncate">
                  {isStructural && <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />}
                  {isIdentifying && <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />}
                  {!isStructural && !isIdentifying && <HelpCircle className="w-4 h-4 text-slate-400 flex-shrink-0" />}

                  <span className="font-mono text-slate-800 dark:text-slate-200 font-medium truncate">
                    {s.group}:{s.tag}
                  </span>

                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded capitalize ${
                      isStructural
                        ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900"
                        : isIdentifying
                        ? "bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                    }`}
                  >
                    {sClass}
                  </span>
                </div>

                <div className="flex flex-col sm:items-end text-slate-500 text-[11px] truncate">
                  <span className="font-mono text-slate-700 dark:text-slate-300 truncate max-w-xs">{valPrev}</span>
                  <span className="text-[10px] text-slate-400 mt-0.5 italic">{s.reason}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
