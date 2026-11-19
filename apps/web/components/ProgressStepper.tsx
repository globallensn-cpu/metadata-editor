"use client";

import React from "react";
import { CheckCircle2, Loader2, Clock, Sparkles, ShieldCheck } from "lucide-react";

interface StepProps {
  currentStage: string;
  progressPercent: number;
}

const STAGES = [
  { id: "queued", label: "Queued", desc: "Waiting for worker container" },
  { id: "analyzing", label: "Analyzing", desc: "Inspecting metadata & detecting type" },
  { id: "cleaning", label: "Cleaning", desc: "Lossless stream remuxing / stripping" },
  { id: "verifying", label: "Verifying", desc: "Diffing tags & checking stream MD5" },
  { id: "completed", label: "Completed", desc: "Verified report ready" },
];

export function ProgressStepper({ currentStage, progressPercent }: StepProps) {
  const getStageIndex = (stage: string) => {
    switch (stage) {
      case "queued": return 0;
      case "analyzing": return 1;
      case "cleaning": return 2;
      case "verifying": return 3;
      case "completed": return 4;
      default: return 0;
    }
  };

  const currentIndex = getStageIndex(currentStage);

  return (
    <div className="w-full max-w-3xl mx-auto p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm" aria-live="polite">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
          {currentIndex < 4 ? <Loader2 className="w-5 h-5 text-teal-600 animate-spin" /> : <ShieldCheck className="w-5 h-5 text-teal-600" />}
          <span>{STAGES[currentIndex]?.label}: {STAGES[currentIndex]?.desc}</span>
        </h3>
        <span className="text-xs font-bold text-teal-600 bg-teal-50 dark:bg-teal-950 px-2.5 py-1 rounded-full">
          {progressPercent}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 mb-6 overflow-hidden">
        <div
          className="bg-teal-600 h-2 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${Math.max(progressPercent, 5)}%` }}
        />
      </div>

      {/* Step Indicators */}
      <div className="grid grid-cols-5 gap-2">
        {STAGES.map((s, idx) => {
          const isDone = idx < currentIndex;
          const isCurrent = idx === currentIndex;
          return (
            <div key={s.id} className="flex flex-col items-center text-center">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  isDone
                    ? "bg-teal-600 text-white"
                    : isCurrent
                    ? "border-2 border-teal-600 text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-400 border border-slate-200 dark:border-slate-700"
                }`}
              >
                {isDone ? <CheckCircle2 className="w-4 h-4" /> : idx + 1}
              </div>
              <span
                className={`text-[11px] font-medium mt-1.5 ${
                  isCurrent ? "text-teal-600 dark:text-teal-400 font-semibold" : "text-slate-500"
                }`}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
