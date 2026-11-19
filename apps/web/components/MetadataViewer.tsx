"use client";

import React, { useState } from "react";
import { Search, ChevronDown, ChevronRight, Eye, EyeOff, ShieldAlert, Download, Copy, Check } from "lucide-react";

interface Field {
  group: string;
  tag: string;
  value: any;
  value_preview: string;
  sensitive: boolean;
  category?: string;
}

interface Section {
  name: string;
  field_count: number;
  sensitive_count: number;
  fields: Field[];
}

interface MetadataReportProps {
  report: {
    job_id: string;
    file_info: {
      original_filename: string;
      detected_type: string;
      size_bytes: number;
      sha256: string;
    };
    sections: Section[];
    total_fields: number;
    sensitive_summary: Record<string, number>;
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

  const exportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `metadata_${report.job_id}.json`);
    dlAnchor.click();
  };

  const sensitiveTotal = Object.values(report.sensitive_summary || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-6">
      {/* Privacy Summary Banner */}
      {sensitiveTotal > 0 && (
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold text-amber-900 dark:text-amber-200 text-sm">
                Privacy Risk: {sensitiveTotal} identifying field{sensitiveTotal > 1 ? "s" : ""} detected
              </p>
              <div className="flex flex-wrap gap-2 mt-1.5">
                {Object.entries(report.sensitive_summary || {}).map(([cat, count]) => (
                  <span
                    key={cat}
                    className="text-xs px-2 py-0.5 rounded-md font-medium bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300 capitalize"
                  >
                    {count} {cat}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <button
            onClick={exportJson}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-300 dark:border-amber-700 hover:bg-amber-100 dark:hover:bg-amber-900 text-amber-900 dark:text-amber-200 text-xs font-semibold transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export JSON</span>
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search metadata tags or values (e.g. GPS, Model, Creator, Codec)..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      </div>

      {/* Sections Accordion */}
      <div className="flex flex-col gap-4">
        {report.sections.map((sec) => {
          const filteredFields = sec.fields.filter(
            (f) =>
              f.tag.toLowerCase().includes(search.toLowerCase()) ||
              String(f.value).toLowerCase().includes(search.toLowerCase())
          );

          if (filteredFields.length === 0) return null;
          const isOpen = openSections[sec.name] ?? false;

          return (
            <div
              key={sec.name}
              className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm"
            >
              <button
                onClick={() => toggleSection(sec.name)}
                className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition border-b border-slate-100 dark:border-slate-800"
              >
                <div className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200 text-sm">
                  {isOpen ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
                  <span>{sec.name}</span>
                  <span className="text-xs font-normal text-slate-500 ml-1">({filteredFields.length} tags)</span>
                </div>

                {sec.sensitive_count > 0 && (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900">
                    {sec.sensitive_count} sensitive
                  </span>
                )}
              </button>

              {isOpen && (
                <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  {filteredFields.map((field) => {
                    const rowKey = `${sec.name}:${field.tag}`;
                    const isRevealed = revealed[rowKey];
                    const displayValue = isRevealed ? String(field.value) : field.value_preview;

                    return (
                      <div key={field.tag} className="px-5 py-2.5 flex items-center justify-between gap-4 hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                        <div className="flex items-center gap-2 min-w-[200px]">
                          <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">{field.tag}</span>
                          {field.sensitive && (
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900">
                              {field.category || "sensitive"}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 truncate justify-end">
                          <span className="font-mono text-slate-600 dark:text-slate-400 truncate max-w-md">
                            {displayValue}
                          </span>

                          {field.sensitive && (
                            <button
                              onClick={() => toggleReveal(rowKey)}
                              className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                              title={isRevealed ? "Hide" : "Reveal sensitive value"}
                            >
                              {isRevealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </button>
                          )}

                          <button
                            onClick={() => copyToClipboard(rowKey, String(field.value))}
                            className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            title="Copy value"
                          >
                            {copiedKey === rowKey ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
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
