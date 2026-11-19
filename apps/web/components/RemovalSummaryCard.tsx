"use client";

import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, Download, Trash2, ShieldCheck, Zap, HardDrive } from "lucide-react";

interface RemovalReportProps {
  report: {
    job_id: string;
    method: string;
    method_reason: string;
    size_before: number;
    size_after: number;
    playback_verified: boolean;
    stream_copy: boolean;
    counts: {
      removed: number;
      survivorsIdentifying: number;
      survivorsStructural: number;
      survivorsUnknown?: number;
    };
    hashes: {
      originalSha256: string;
      cleanedSha256: string;
    };
    download_url?: string;
  };
  onDeleteNow: () => void;
}

export function RemovalSummaryCard({ report, onDeleteNow }: RemovalReportProps) {
  const [downloading, setDownloading] = useState(false);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const hasIdentifyingSurvivors = (report.counts.survivorsIdentifying || 0) > 0;
  const sizeDiff = report.size_before - report.size_after;
  const sizeSavedStr = sizeDiff > 0 ? `-${formatBytes(sizeDiff)} (${((sizeDiff / report.size_before) * 100).toFixed(1)}%)` : "0 Bytes";

  const triggerDownload = () => {
    if (report.download_url) {
      setDownloading(true);
      window.location.href = report.download_url;
      setTimeout(() => setDownloading(false), 2000);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm">
      {/* Header status */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-xl ${
              hasIdentifyingSurvivors
                ? "bg-amber-50 dark:bg-amber-950/60 text-amber-600"
                : "bg-teal-50 dark:bg-teal-950/60 text-teal-600"
            }`}
          >
            {hasIdentifyingSurvivors ? <AlertTriangle className="w-7 h-7" /> : <CheckCircle2 className="w-7 h-7" />}
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              {hasIdentifyingSurvivors ? "Cleaning Complete with Survivors" : "Metadata Cleaned & Verified"}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Method: <span className="font-semibold capitalize">{report.method}</span> • {report.method_reason}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            onClick={triggerDownload}
            disabled={downloading}
            className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-teal-600 hover:bg-teal-700 active:scale-[0.99] transition shadow-md shadow-teal-600/20"
          >
            <Download className="w-4 h-4" />
            <span>Download Cleaned File</span>
          </button>

          <button
            onClick={onDeleteNow}
            className="p-3 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-600 dark:hover:text-red-400 text-slate-500 transition"
            title="Delete original and cleaned files immediately"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-6">
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
          <p className="text-xs text-slate-500 font-medium">Tags Removed</p>
          <p className="text-2xl font-bold text-teal-600 mt-1">{report.counts.removed}</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
          <p className="text-xs text-slate-500 font-medium">Quality Mode</p>
          <div className="flex items-center gap-1.5 mt-1 text-slate-800 dark:text-slate-200 font-semibold text-sm">
            <Zap className="w-4 h-4 text-teal-600" />
            <span>{report.stream_copy ? "100% Lossless" : "Re-encoded"}</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
          <p className="text-xs text-slate-500 font-medium">Playback Verified</p>
          <div className="flex items-center gap-1.5 mt-1 text-slate-800 dark:text-slate-200 font-semibold text-sm">
            <ShieldCheck className="w-4 h-4 text-teal-600" />
            <span>{report.playback_verified ? "Valid Stream" : "Unverified"}</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
          <p className="text-xs text-slate-500 font-medium">Size Change</p>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
            {formatBytes(report.size_after)} <span className="text-xs text-teal-600 font-normal">({sizeSavedStr})</span>
          </p>
        </div>
      </div>
    </div>
  );
}
