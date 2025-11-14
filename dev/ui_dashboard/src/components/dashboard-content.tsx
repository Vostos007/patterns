"use client";

import { useState } from "react";

import JobsTable from "@/components/jobs-table";
import UploadPanel from "@/components/upload-panel";

export default function DashboardContent() {
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          Hollywool Control Room
        </p>
        <h1 className="text-3xl font-semibold text-zinc-900">
          Translation Jobs
        </h1>
        <p className="text-sm text-zinc-600">
          Upload knitting PDFs into <code>to_translate/</code> and monitor their
          journey to <code>translations/</code> in real time.
        </p>
      </header>

      <UploadPanel onUploaded={() => setRefreshToken((token) => token + 1)} />
      <JobsTable refreshToken={refreshToken} />
    </div>
  );
}
