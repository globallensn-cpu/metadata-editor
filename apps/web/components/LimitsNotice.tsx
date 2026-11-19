import React from "react";
import { ShieldAlert, Info } from "lucide-react";

export function LimitsNotice() {
  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 p-6 text-xs text-slate-600 dark:text-slate-400">
      <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-200 text-sm mb-3">
        <ShieldAlert className="w-4 h-4 text-slate-500" />
        <span>What Reaboard Can't Do (Honest Limits)</span>
      </div>

      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 list-disc list-inside">
        <li>Does not alter visible video pixels, audio waveform samples, or document body text.</li>
        <li>Does not strip imperceptible sensor fingerprints (Photo-Response Non-Uniformity - PRNU).</li>
        <li>Does not remove visual watermarks, steganographic payloads, or burned-in timestamps.</li>
        <li>Filesystem creation dates are governed by your operating system when saving to local disk.</li>
        <li>Original filename is preserved unless you explicitly enabled randomized download names.</li>
        <li>Cannot guarantee proprietary/unknown vendor atoms are absent (reports only verified fields).</li>
      </ul>
    </div>
  );
}
