"use client";

import { useEffect } from "react";
import useSWR from "swr";

import { getDownloadUrl, JobStatus, listJobs } from "@/lib/api";

interface JobsTableProps {
  refreshToken?: number;
}

const fetcher = () => listJobs();

export default function JobsTable({ refreshToken }: JobsTableProps) {
  const { data, isLoading, error, mutate } = useSWR("jobs", fetcher, {
    refreshInterval: 5000,
  });

  useEffect(() => {
    if (refreshToken !== undefined) {
      void mutate();
    }
  }, [refreshToken, mutate]);

  const jobs = data ?? [];

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-900">Jobs</h2>
          <p className="text-sm text-zinc-600">
            Latest runs from <code>to_translate/</code> → <code>translations/</code>
          </p>
        </div>
        {isLoading && <span className="text-sm text-zinc-500">Refreshing…</span>}
      </div>

      {error && (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
          Failed to load jobs. Ensure the FastAPI service is running on
          <code className="ml-1">{process.env.NEXT_PUBLIC_API_BASE}</code>
        </p>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[600px] border-collapse text-left text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-zinc-500">
              <th className="pb-3">Job ID</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Targets</th>
              <th className="pb-3">Artifacts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {jobs.map((job) => (
              <tr key={job.job_id} className="align-top">
                <td className="py-3 font-mono text-xs text-zinc-600">
                  {job.job_id.slice(0, 8)}
                </td>
                <td className="py-3">
                  <StatusPill status={job.status} />
                </td>
                <td className="py-3 text-zinc-700">
                  {job.target_languages.join(", ")}
                </td>
                <td className="py-3">
                  <ArtifactButtons job={job} />
                </td>
              </tr>
            ))}
            {!jobs.length && !isLoading && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-sm text-zinc-500">
                  No jobs yet. Upload a document to kick things off.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const color =
    status === "succeeded"
      ? "bg-emerald-100 text-emerald-700"
      : status === "failed"
        ? "bg-red-100 text-red-700"
        : "bg-amber-100 text-amber-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}

function ArtifactButtons({ job }: { job: JobStatus }) {
  return (
    <div className="flex flex-wrap gap-2">
      {job.target_languages.map((language) => {
        const downloadUrl = getDownloadUrl(job, language);
        const disabled = !downloadUrl || job.status !== "succeeded";
        return (
          <a
            key={language}
            href={downloadUrl}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              disabled
                ? "cursor-not-allowed bg-zinc-100 text-zinc-400"
                : "bg-black text-white hover:bg-zinc-900"
            }`}
            aria-disabled={disabled}
            onClick={(event) => {
              if (disabled) {
                event.preventDefault();
              }
            }}
          >
            {language.toUpperCase()}
          </a>
        );
      })}
    </div>
  );
}
