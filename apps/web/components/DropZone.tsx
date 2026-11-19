"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Upload, FileCode, CheckCircle2, AlertCircle, Sparkles, Settings2, ShieldCheck, Eye } from "lucide-react";

interface StagedFile {
  file: File;
  name: string;
  size: number;
}

export function DropZone({ dict }: { dict: any }) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [staged, setStaged] = useState<StagedFile | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Removal Options state
  const [keepIcc, setKeepIcc] = useState(true);
  const [keepOrientation, setKeepOrientation] = useState(true);
  const [randomizeName, setRandomizeName] = useState(false);

  // Clipboard paste listener
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      if (e.clipboardData?.files && e.clipboardData.files.length > 0) {
        const file = e.clipboardData.files[0];
        handleFileSelect(file);
      }
    };
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, []);

  const handleFileSelect = (file: File) => {
    setError(null);
    if (file.size > 500 * 1024 * 1024) {
      setError("File exceeds maximum allowed size of 500 MB.");
      return;
    }
    setStaged({
      file,
      name: file.name,
      size: file.size,
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const executeAction = async (action: "remove" | "view") => {
    if (!staged) return;
    setError(null);
    setUploadProgress(10);

    const formData = new FormData();
    formData.append("file", staged.file);

    try {
      // 1. Upload file
      const uploadRes = await fetch("/api/v1/jobs", {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const errJson = await uploadRes.json();
        throw new Error(errJson.error?.message || "Upload failed");
      }

      const jobData = await uploadRes.json();
      const jobId = jobData.jobId;
      setUploadProgress(100);

      // 2. Trigger Action
      if (action === "remove") {
        await fetch(`/api/v1/jobs/${jobId}/remove`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            keepIccProfile: keepIcc,
            keepOrientation: keepOrientation,
            randomizeFilename: randomizeName,
          }),
        });
        router.push(`/job/${jobId}?mode=remove`);
      } else {
        await fetch(`/api/v1/jobs/${jobId}/view`, {
          method: "POST",
        });
        router.push(`/job/${jobId}?mode=view`);
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred during upload.");
      setUploadProgress(null);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Drop Target */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !staged && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all cursor-pointer ${
          isDragging
            ? "border-teal-500 bg-teal-50/50 dark:bg-teal-950/20 scale-[1.01]"
            : staged
            ? "border-teal-500/50 bg-white dark:bg-slate-900 cursor-default"
            : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-teal-500/60 dark:hover:border-teal-500/60"
        } shadow-sm`}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
        />

        {!staged ? (
          <div className="flex flex-col items-center gap-4">
            <div className="p-4 rounded-full bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
              <Upload className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
                {dict?.dropzone?.title || "Drop your file here, paste from clipboard, or browse"}
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                {dict?.dropzone?.supported || "Supports MP4, MOV, MKV, WebM, AVI, JPEG, PNG, WebP, HEIC, TIFF, PDF"}
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400 mt-2">
              <ShieldCheck className="w-4 h-4 text-teal-600" />
              <span>{dict?.dropzone?.sizeLimit || "Max 500 MB • Lossless remux by default • 60-min TTL"}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-6 text-left">
            {/* File info card */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-3 truncate">
                <FileCode className="w-8 h-8 text-teal-600 flex-shrink-0" />
                <div className="truncate">
                  <p className="font-semibold text-slate-900 dark:text-slate-100 truncate">{staged.name}</p>
                  <p className="text-xs text-slate-500">{formatBytes(staged.size)}</p>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setStaged(null);
                  setError(null);
                }}
                className="text-xs font-medium text-slate-500 hover:text-red-500 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-red-300 transition"
              >
                Change File
              </button>
            </div>

            {/* Options bar */}
            <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-700 dark:text-slate-300">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={keepIcc}
                  onChange={(e) => setKeepIcc(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                />
                <span>Keep ICC Color Profile (Images)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={keepOrientation}
                  onChange={(e) => setKeepOrientation(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                />
                <span>Keep Orientation (Structural)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={randomizeName}
                  onChange={(e) => setRandomizeName(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                />
                <span>Randomize Output Filename</span>
              </label>
            </div>

            {/* Action buttons */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <button
                disabled={uploadProgress !== null}
                onClick={(e) => {
                  e.stopPropagation();
                  executeAction("remove");
                }}
                className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white bg-teal-600 hover:bg-teal-700 active:scale-[0.99] transition shadow-md shadow-teal-600/20 disabled:opacity-50"
              >
                <Sparkles className="w-4 h-4" />
                <span>{dict?.actions?.remove || "Remove Metadata (Lossless)"}</span>
              </button>

              <button
                disabled={uploadProgress !== null}
                onClick={(e) => {
                  e.stopPropagation();
                  executeAction("view");
                }}
                className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 active:scale-[0.99] transition border border-slate-200 dark:border-slate-700 disabled:opacity-50"
              >
                <Eye className="w-4 h-4" />
                <span>{dict?.actions?.view || "View Metadata"}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Progress or error */}
      {uploadProgress !== null && (
        <div className="mt-4">
          <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-teal-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <p className="text-xs text-center text-slate-500 mt-2">Uploading file to isolated sandbox...</p>
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 flex items-start gap-3 text-red-700 dark:text-red-400 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Upload Failed</p>
            <p className="text-xs mt-0.5">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
