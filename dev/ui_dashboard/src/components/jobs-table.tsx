"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getApiBase } from "@/lib/api";
import { JobStatus } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-200 text-gray-800",
  processing: "bg-blue-100 text-blue-900",
  succeeded: "bg-emerald-100 text-emerald-900",
  failed: "bg-red-100 text-red-900",
};

export default function JobsTable({ refreshToken }: { refreshToken: number }) {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const resp = await fetch(`${getApiBase()}/jobs`);
        if (resp.ok) {
          const data = await resp.json();
          if (!disposed) {
            setJobs(data);
            setError(null);
          }
        }
      } catch (err) {
        console.error(err);
        if (!disposed) {
          setError("Unable to reach API. Check that the FastAPI service is running on port 9000.");
        }
      } finally {
        if (!disposed) {
          timer = setTimeout(poll, 5000);
        }
      }
    };

    poll();

    return () => {
      disposed = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [refreshToken]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Jobs</CardTitle>
        {error && <CardDescription className="text-red-600">{error}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Languages</TableHead>
                <TableHead>Artifacts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.job_id}>
                  <TableCell className="font-mono text-sm">{job.job_id}</TableCell>
                  <TableCell>
                    <Badge className={STATUS_COLORS[job.status] ?? "bg-gray-100"}>{job.status}</Badge>
                  </TableCell>
                  <TableCell>{job.target_languages.join(", ")}</TableCell>
                  <TableCell className="space-x-2">
                    {job.artifacts?.map((artifact) => (
                      <Button
                        key={artifact.language}
                        variant="outline"
                        size="sm"
                        asChild
                        disabled={artifact.status !== "ready"}
                      >
                        <a href={`${getApiBase()}${artifact.download_url}`} target="_blank">
                          {artifact.language.toUpperCase()}
                        </a>
                      </Button>
                    ))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
