"use client";

import React, { useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ProgressStepper } from "../../../components/ProgressStepper";
import { MetadataViewer } from "../../../components/MetadataViewer";
import { RemovalSummaryCard } from "../../../components/RemovalSummaryCard";
import { DiffView } from "../../../components/DiffView";
import { SurvivorsList } from "../../../components/SurvivorsList";
import { LimitsNotice } from "../../../components/LimitsNotice";
import { ReencodeConfirmDialog } from "../../../components/ReencodeConfirmDialog";
import { ArrowLeft, AlertCircle, RefreshCw } from "lucide-react";

export default function JobResultPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const jobId = params?.id as string;
  const initialMode = searchParams.get("mode") || "remove";

  const [status, setStatus] = useState<string>("queued");
  const [stage, setStage] = useState<string>("queued");
  const [progress, setProgress] = useState<number>(0);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [showReencodeDialog, setShowReencodeDialog] = useState<boolean>(false);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  // SSE Event listener
  useEffect(() => {
    if (!jobId) return;

    const eventSource = new EventSource(`/api/v1/jobs/${jobId}/events`);

    eventSource.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status || "queued");
        setStage(data.stage || "analyzing");
        setProgress(data.progress || 0);
      } catch (e) {
        console.error("SSE parse error", e);
      }
    });

    eventSource.addEventListener("completed", async (event) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data.status || "completed");
      } catch {
        setStatus("completed");
      }
      setStage("completed");
      setProgress(100);
      eventSource.close();
      await fetchReport();
    });

    eventSource.addEventListener("error", (event) => {
      try {
        // @ts-ignore
        const data = JSON.parse(event.data);
        const code = data.error?.code || "";
        setErrorCode(code);
        setError(data.error?.message || "Job processing failed");
        if (code === "REENCODE_REQUIRED") {
          setShowReencodeDialog(true);
        }
      } catch {
        fetchStatus();
      }
    });

    // Initial status fetch
    fetchStatus();

    return () => {
      eventSource.close();
    };
  }, [jobId]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}`);
      if (!res.ok) throw new Error("Job not found");
      const job = await res.json();
      setStatus(job.status);
      setStage(job.currentStage || job.current_stage || "queued");
      setProgress(job.progressPercent || job.progress_percent || 0);

      if (job.status === "completed" || job.status === "completed_with_warnings") {
        await fetchReport();
      } else if (job.status === "failed") {
        const code = job.error?.code || "";
        setErrorCode(code);
        setError(job.error?.message || "Processing failed");
        if (code === "REENCODE_REQUIRED") {
          setShowReencodeDialog(true);
        }
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const fetchReport = async () => {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/report`);
      if (res.ok) {
        const data = await res.json();
        // Attach downloadUrl from job if present
        const jobRes = await fetch(`/api/v1/jobs/${jobId}`);
        if (jobRes.ok) {
          const job = await jobRes.json();
          data.downloadUrl = job.downloadUrl || job.download_url;
        }
        setReport(data);
      }
    } catch (e) {
      console.error("Failed to load report", e);
    }
  };

  const handleDeleteNow = async () => {
    if (confirm("Are you sure you want to permanently purge this file now?")) {
      await fetch(`/api/v1/jobs/${jobId}`, { method: "DELETE" });
      router.push("/");
    }
  };

  const handleConfirmReencode = async () => {
    setIsRetrying(true);
    setError(null);
    setShowReencodeDialog(false);

    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allowReencode: true }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error?.message || "Re-encoding request failed");
      }
      setStatus("queued");
      setStage("cleaning");
      setProgress(20);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsRetrying(false);
    }
  };

  const isCompleted = status === "completed" || status === "completed_with_warnings";

  return (
    <div className="flex-1 flex flex-col px-4 py-8 max-w-6xl mx-auto w-full">
      {/* Top Navigation */}
      <div className="flex items-center justify-between mb-8">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Upload Another File</span>
        </Link>

        <span className="text-xs font-mono text-slate-400">
          Job: {jobId?.slice(0, 8)}...
        </span>
      </div>

      {/* Re-encode Confirmation Modal */}
      <ReencodeConfirmDialog
        isOpen={showReencodeDialog}
        onConfirm={handleConfirmReencode}
        onCancel={() => setShowReencodeDialog(false)}
        isProcessing={isRetrying}
      />

      {/* Error State */}
      {error && !showReencodeDialog && (
        <div className="p-6 rounded-2xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 max-w-2xl mx-auto w-full text-center">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
          <h3 className="font-bold text-red-900 dark:text-red-200 text-base">Processing Failed</h3>
          <p className="text-xs text-red-700 dark:text-red-400 mt-1 max-w-md mx-auto">{error}</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            {errorCode === "REENCODE_REQUIRED" && (
              <button
                onClick={() => setShowReencodeDialog(true)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-teal-600 text-white hover:bg-teal-700 transition"
              >
                Authorize Re-encode
              </button>
            )}
            <button
              onClick={() => router.push("/")}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 hover:bg-slate-300 transition"
            >
              Return to Upload
            </button>
          </div>
        </div>
      )}

      {/* In-Progress Stepper */}
      {!error && !isCompleted && (
        <div className="my-auto py-12">
          <ProgressStepper currentStage={stage} progressPercent={progress} />
        </div>
      )}

      {/* Completed State */}
      {!error && isCompleted && report && (
        <div className="flex flex-col gap-8 pb-12">
          {report.method ? (
            /* Remove Mode Completed */
            <>
              <RemovalSummaryCard report={report} onDeleteNow={handleDeleteNow} />
              {report.removed && report.removed.length > 0 && (
                <DiffView removed={report.removed} />
              )}
              {report.survivors && (
                <SurvivorsList survivors={report.survivors} />
              )}
              <LimitsNotice />
            </>
          ) : (
            /* View Mode Completed */
            <>
              <MetadataViewer report={report} />
              <LimitsNotice />
            </>
          )}
        </div>
      )}
    </div>
  );
}
