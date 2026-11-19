import React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import { LimitsNotice } from "@/components/LimitsNotice";

export default function LimitsPage() {
  return (
    <div className="flex-1 max-w-4xl mx-auto px-4 py-12">
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 mb-8 transition">
        <ArrowLeft className="w-4 h-4" />
        <span>Back to App</span>
      </Link>

      <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 mb-4">
        What Reaboard Can't Do (Honest Limits)
      </h1>
      <p className="text-sm text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
        We believe in total honesty with our users. Reaboard strips container and stream metadata tags. It does not perform content-level forensic obfuscation.
      </p>

      <LimitsNotice />

      <div className="mt-8 space-y-6 text-xs text-slate-600 dark:text-slate-400">
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
            1. Visible Content & Watermarks
          </h2>
          <p className="leading-relaxed">
            If your image or video has a date stamp burned into the bottom corner, or visible faces, Reaboard will not blur or edit the visual pixels. That requires lossy re-encoding and video editing, which violates our lossless mandate.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
            2. Sensor Noise & PRNU Fingerprints
          </h2>
          <p className="leading-relaxed">
            Every camera sensor has microscopic manufacturing imperfections that leave a persistent noise pattern across video frames (Photo-Response Non-Uniformity). Forensic labs can link images to specific camera sensors via PRNU analysis. Reaboard does not attempt to remove PRNU.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
            3. Operating System File Timestamps
          </h2>
          <p className="leading-relaxed">
            When you download a file, your local operating system (Windows, macOS, Linux) writes a new file-system creation and modification date. Reaboard removes the internal creation date atoms inside the file container, but cannot control what your OS marks upon file write.
          </p>
        </div>
      </div>
    </div>
  );
}
