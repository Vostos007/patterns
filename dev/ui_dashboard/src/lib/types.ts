export type Artifact = {
  language: string;
  file_name: string;
  download_url: string;
  status: string;
};

export type JobStatus = {
  job_id: string;
  status: string;
  target_languages: string[];
  source_filename: string;
  artifacts: Artifact[];
  logs_url?: string;
};
