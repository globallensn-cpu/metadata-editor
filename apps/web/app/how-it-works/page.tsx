import React from "react";
import Link from "next/link";
import { ArrowLeft, Cpu, ShieldCheck, Zap, RefreshCw } from "lucide-react";

export default function HowItWorksPage() {
  return (
    <div className="flex-1 max-w-4xl mx-auto px-4 py-12">
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 mb-8 transition">
        <ArrowLeft className="w-4 h-4" />
        <span>Back to App</span>
      </Link>

      <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 mb-4">
        How Reaboard Works: The Verification Engine
      </h1>
      <p className="text-sm text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
        Most metadata removers either silently degrade video quality through re-encoding or fail to strip buried stream-level tags. Reaboard operates with a transparent, verified dual-pass pipeline.
      </p>

      <div className="space-y-6 text-sm text-slate-700 dark:text-slate-300">
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <Zap className="w-4 h-4 text-teal-600" />
            <span>1. Lossless Stream Copy (Never Silent Re-Encoding)</span>
          </h2>
          <p className="text-xs text-slate-500 leading-relaxed">
            For MP4, MOV, MKV, and WebM video, Reaboard executes <code className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-mono">-c copy</code> remuxing with <code className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-mono">-fflags +bitexact</code> and explicit track handler blanking. Video and audio elementary packets remain bit-for-bit identical, verified by stream-level MD5 hashing.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-teal-600" />
            <span>2. Dual-Pass Verification Diffing</span>
          </h2>
          <p className="text-xs text-slate-500 leading-relaxed">
            Reaboard re-inspects the generated output file with ExifTool and FFprobe. It diffs every tag against the original input and classifies survivors into <span className="font-semibold text-emerald-600">structural</span> (codecs, dimensions, rotation) and <span className="font-semibold text-amber-600">identifying</span>. If identifying tags survive, an automated secondary pass is triggered.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-teal-600" />
            <span>3. Atomic Output Copies</span>
          </h2>
          <p className="text-xs text-slate-500 leading-relaxed">
            Original files are never modified in place. Operations are performed in an isolated temporary work directory on a separate file copy, protecting file integrity from aborted or interrupted operations.
          </p>
        </div>
      </div>
    </div>
  );
}
