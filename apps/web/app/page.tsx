import React from "react";
import { DropZone } from "@/components/DropZone";
import { LimitsNotice } from "@/components/LimitsNotice";
import { ShieldCheck, Zap, Eye, Lock } from "lucide-react";
import dict from "@/messages/en.json";

export default function HomePage() {
  return (
    <div className="flex-1 flex flex-col items-center justify-start px-4 py-12 md:py-16">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-400 text-xs font-semibold mb-4 border border-teal-200 dark:border-teal-900/60">
          <ShieldCheck className="w-4 h-4" />
          <span>Verified Dual-Pass Engine • Lossless by Default</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white leading-[1.15]">
          Clean metadata. Keep the quality. <br className="hidden sm:inline" />
          <span className="text-teal-600 dark:text-teal-400">Stay private.</span>
        </h1>
        <p className="mt-4 text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed max-w-2xl mx-auto">
          Inspect every hidden metadata atom in your video, image, or document. Losslessly clean sensitive tags with verified before-and-after reporting.
        </p>
      </div>

      {/* Main Upload Zone */}
      <div className="w-full mb-12">
        <DropZone dict={dict} />
      </div>

      {/* Why Reaboard Beats Competitors */}
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-teal-50 dark:bg-teal-950 flex items-center justify-center text-teal-600 mb-4">
            <Zap className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1.5">Lossless Stream Copy</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Never silent re-encoding. Video and audio packets are remuxed with bitexact flags, preserving 100% of the original stream fidelity.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-teal-50 dark:bg-teal-950 flex items-center justify-center text-teal-600 mb-4">
            <Eye className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1.5">Verified Diff Report</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Every output file is re-extracted and compared against the original. Transparently see what was stripped, what survived, and why.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-teal-50 dark:bg-teal-950 flex items-center justify-center text-teal-600 mb-4">
            <Lock className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1.5">Zero Retention & Tracking</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            All files live in temporary memory, never stored permanently. Hard-deleted automatically after 60 minutes or immediately on demand.
          </p>
        </div>
      </div>

      {/* Honest Limits Notice */}
      <div className="w-full">
        <LimitsNotice />
      </div>
    </div>
  );
}
