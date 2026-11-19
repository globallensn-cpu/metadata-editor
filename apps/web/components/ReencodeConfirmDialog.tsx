"use client";

import React from "react";
import { AlertCircle, Film, ShieldAlert, X } from "lucide-react";

interface ReencodeConfirmDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  isProcessing?: boolean;
}

export function ReencodeConfirmDialog({
  isOpen,
  onConfirm,
  onCancel,
  isProcessing = false,
}: ReencodeConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600">
              <Film className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Re-encoding Required
              </h3>
              <p className="text-xs text-slate-500">Lossless stream copy unsupported</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={isProcessing}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3 text-xs text-slate-600 dark:text-slate-300 leading-relaxed mb-6">
          <p>
            Reaboard always defaults to <span className="font-semibold text-slate-900 dark:text-slate-100">100% lossless remuxing</span>. However, this specific container or codec combination embeds metadata in streams that cannot be stripped without re-encoding.
          </p>
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" />
            <span>
              If you proceed, Reaboard will re-encode the stream using visually transparent <span className="font-mono font-semibold">CRF 18</span> quality and strip all metadata.
            </span>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isProcessing}
            className="px-4 py-2.5 rounded-xl text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isProcessing}
            className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-700 text-white transition shadow-md shadow-teal-600/20 disabled:opacity-50"
          >
            {isProcessing ? "Re-encoding..." : "Proceed with Re-encode"}
          </button>
        </div>
      </div>
    </div>
  );
}
