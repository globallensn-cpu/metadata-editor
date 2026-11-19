import React from "react";
import Link from "next/link";
import { ArrowLeft, Lock, Trash2, Clock, ShieldCheck } from "lucide-react";

export default function PrivacyPage() {
  return (
    <div className="flex-1 max-w-4xl mx-auto px-4 py-12">
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 mb-8 transition">
        <ArrowLeft className="w-4 h-4" />
        <span>Back to App</span>
      </Link>

      <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 mb-4">
        Privacy & Data Security Policy
      </h1>
      <p className="text-sm text-slate-600 dark:text-slate-300 mb-8 leading-relaxed">
        Reaboard is architected from the ground up on zero-knowledge and ephemeral principles. We treat your files as strictly private, confidential data.
      </p>

      <div className="space-y-6 text-xs text-slate-600 dark:text-slate-400">
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <Clock className="w-4 h-4 text-teal-600" />
            <span>Automatic 60-Minute Purge</span>
          </h2>
          <p className="leading-relaxed">
            All uploaded files, sanitized outputs, and inspection reports are placed in ephemeral storage. An automated sweeper task permanently deletes them from disk after 60 minutes.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <Trash2 className="w-4 h-4 text-teal-600" />
            <span>Instant "Delete Now" Guarantee</span>
          </h2>
          <p className="leading-relaxed">
            You don't need to wait for the 60-minute window. Clicking "Delete Now" immediately unlinks your original and cleaned files from storage and purges job keys from memory.
          </p>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2 flex items-center gap-2">
            <Lock className="w-4 h-4 text-teal-600" />
            <span>Zero Filename or Value Logging</span>
          </h2>
          <p className="leading-relaxed">
            Application logs record only operational performance metrics: job IDs, file sizes, processing durations, and status codes. Original filenames, GPS coordinates, author names, and serial numbers are strictly excluded from logging.
          </p>
        </div>
      </div>
    </div>
  );
}
