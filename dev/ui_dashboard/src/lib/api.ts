const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:9000";

export interface Artifact {
  language: string;
  path: string;
  mime_type: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  created_at: string;
  target_languages: string[];
  artifacts: Artifact[];
  download_urls?: Record<string, string>;
  logs_url?: string;
}

const withBase = (path: string | undefined) => {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
};

export async function listJobs(): Promise<JobStatus[]> {
  const response = await fetch(`${API_BASE}/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch jobs: ${response.status}`);
  }
  return response.json();
}

export async function uploadDocument(file: File, languages: string[]): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("target_languages", languages.join(","));

  const response = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Upload failed");
  }

  const payload = await response.json();
  return payload.job_id as string;
}

export function getDownloadUrl(job: JobStatus, language: string): string | undefined {
  const relative = job.download_urls?.[language];
  if (!relative) return undefined;
  return withBase(relative);
}
