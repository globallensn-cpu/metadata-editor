"use client";

import React, { useState } from "react";
import { Search, ChevronDown, ChevronRight, Eye, EyeOff, ShieldAlert, Download, Copy, Check } from "lucide-react";

interface Field {
  group: string;
  tag: string;
  value: any;
  valuePreview?: string;
  value_preview?: string;
  sensitive: boolean;
  category?: string;
}

interface Section {
  name: string;
  fieldCount?: number;
  field_count?: number;
  sensitiveCount?: number;
  sensitive_count?: number;
  fields: Field[];
}

interface MetadataReportProps {
  report: {
    jobId?: string;
    job_id?: string;
    fileInfo?: {
      originalFilename?: string;
      original_filename?: string;
      detectedType?: string;
      detected_type?: string;
      sizeBytes?: number;
      size_bytes?: number;
      sha256?: string;
    };
    file_info?: {
      original_filename?: string;
      detected_type?: string;
      size_bytes?: number;
      sha256?: string;
    };
    sections: Section[];
    totalFields?: number;
    total_fields?: number;
    sensitiveSummary?: Record<string, number>;
    sensitive_summary?: Record<string, number>;
  };
}

export function MetadataViewer({ report }: MetadataReportProps) {
  const [search, setSearch] = useState("");
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    QuickTime: true,
    EXIF: true,
    General: true,
    Format: true,
  });
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const toggleSection = (name: string) => {
    setOpenSections((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const toggleReveal = (key: string) => {
    setRevealed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const copyToClipboard = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const jobId = report.jobId || report.job_id || "report";
  const sensitiveSummary = report.sensitiveSummary || report.sensitive_summary || {};
  const sensitiveTotal = Object.values(sensitiveSummary).reduce((a, b) => a + b, 0);

  const exportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `metadata_${jobId}.json`);
    dlAnchor.click();
  };

  const filteredSections = report.sections.map((section) => {
    const filteredFields = section.fields.filter((field) => {
      const q = search.toLowerCase();
      const valStr = String(field.valuePreview || field.value_preview || field.value || "").toLowerCase();
      return field.tag.toLowerCase().includes(q) || valStr.includes(q);
    });
    return {
      ...section,
      fields: filteredFields,
    };
  }).filter((section) => section.fields.length > 0 || search === "");

  return (
    <div className="w-full max-w-4xl mx-auto rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-sm">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <span>Metadata Inspection</span>
            {sensitiveTotal > 0 && (
              <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 font-semibold">
                <ShieldAlert className="w-3.5 h-3.5" />
                {sensitiveTotal} Sensitive
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Total {report.totalFields ?? report.total_fields ?? 0} fields discovered across container atoms and streams
          </p>
        </div>

        <button
          onClick={exportJson}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export JSON</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="py-4">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search metadata tags or values (e.g., GPS, Model, Creator)..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition"
          />
        </div>
      </div>

      {/* Sections Accordion */}
      <div className="space-y-3 pt-2">
        {filteredSections.map((sec) => {
          const isOpen = openSections[sec.name] ?? false;
          const sCount = sec.sensitiveCount ?? sec.sensitive_count ?? 0;
          const fCount = sec.fieldCount ?? sec.field_count ?? sec.fields.length;

          return (
            <div
              key={sec.name}
              className="rounded-xl border border-slate-100 dark:border-slate-800 overflow-hidden bg-slate-50/50 dark:bg-slate-800/20"
            >
              <button
                onClick={() => toggleSection(sec.name)}
                className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-slate-100/50 dark:hover:bg-slate-800/40 transition"
              >
                <div className="flex items-center gap-2">
                  {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                  <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">{sec.name}</span>
                  <span className="text-[10px] text-slate-400">({fCount} tags)</span>
                </div>
                {sCount > 0 && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                    {sCount} sensitive
                  </span>
                )}
              </button>

              {isOpen && (
                <div className="border-t border-slate-100 dark:border-slate-800 px-4 py-2 divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-slate-900">
                  {sec.fields.map((f) => {
                    const fieldKey = `${sec.name}:${f.tag}`;
                    const isRevealed = revealed[fieldKey] || false;
                    const preview = f.valuePreview ?? f.value_preview ?? String(f.value);
                    const isMasked = f.sensitive && !isRevealed;

                    return (
                      <div key={f.tag} className="py-2.5 flex items-start justify-between gap-4 text-xs">
                        <div className="flex items-center gap-2 max-w-[40%]">
                          <span className="font-mono text-slate-700 dark:text-slate-300 font-medium truncate" title={f.tag}>
                            {f.tag}
                          </span>
                          {f.category && (
                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-900 capitalize flex-shrink-0">
                              {f.category}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 max-w-[60%] justify-end">
                          <span className="font-mono text-slate-600 dark:text-slate-400 text-right truncate">
                            {isMasked ? preview : String(f.value)}
                          </span>

                          {f.sensitive && (
                            <button
                              onClick={() => toggleReveal(fieldKey)}
                              className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
                              title={isRevealed ? "Mask value" : "Reveal sensitive value"}
                            >
                              {isRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </button>
                          )}

                          <button
                            onClick={() => copyToClipboard(fieldKey, String(f.value))}
                            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
                            title="Copy value"
                          >
                            {copiedKey === fieldKey ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
