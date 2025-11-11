"use client";

import { Suspense, useState } from "react";

import UploadPanel from "@/components/upload-panel";
import JobsTable from "@/components/jobs-table";
import { Toaster } from "@/components/ui/sonner";

export function DashboardClient() {
  const [token, setToken] = useState(0);

  return (
    <div className="flex flex-col gap-6">
      <UploadPanel onJobCreated={() => setToken((value) => value + 1)} />
      <Suspense fallback={<p>Loading jobs…</p>}>
        <JobsTable refreshToken={token} />
      </Suspense>
      <Toaster position="bottom-right" />
    </div>
  );
}
