"use client";

import { ChangeEvent, FormEvent, useState } from "react";

import { uploadDocument } from "@/lib/api";

interface UploadPanelProps {
  onUploaded?: (jobId: string) => void;
}

const LANGUAGE_PRESETS = [
  { code: "en", label: "English" },
  { code: "fr", label: "French" },
];

export default function UploadPanel({ onUploaded }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [languages, setLanguages] = useState<Record<string, boolean>>({
    en: true,
    fr: false,
  });
  const [customLanguage, setCustomLanguage] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    setFile(selected ?? null);
  };

  const toggleLanguage = (code: string) => {
    setLanguages((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Please choose a PDF or DOCX file.");
      return;
    }

    const selectedLanguages = [
      ...Object.entries(languages)
        .filter(([, enabled]) => enabled)
        .map(([code]) => code),
    ];

    if (customLanguage.trim()) {
      selectedLanguages.push(customLanguage.trim());
    }

    if (!selectedLanguages.length) {
      setError("Pick at least one target language.");
      return;
    }

    try {
      setIsUploading(true);
      setError(null);
      setMessage("Uploading…");
      const jobId = await uploadDocument(file, selectedLanguages);
      setMessage(`Job ${jobId} queued`);
      setFile(null);
      setCustomLanguage("");
      event.currentTarget.reset();
      if (onUploaded) {
        onUploaded(jobId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-semibold text-zinc-900">Upload document</h2>
      <p className="mt-1 text-sm text-zinc-600">
        Drop a PDF/DOCX and select target languages. The Control Room pushes it
        into <code>to_translate/</code> for processing.
      </p>

      <div className="mt-4 space-y-4">
        <label className="flex flex-col text-sm font-medium text-zinc-700">
          Document
          <input
            type="file"
            accept="application/pdf,.doc,.docx"
            onChange={handleFileChange}
            className="mt-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          />
        </label>

        <fieldset>
          <legend className="text-sm font-medium text-zinc-700">
            Target languages
          </legend>
          <div className="mt-2 flex flex-wrap gap-4">
            {LANGUAGE_PRESETS.map((lang) => (
              <label key={lang.code} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(languages[lang.code])}
                  onChange={() => toggleLanguage(lang.code)}
                  className="rounded border-zinc-300 text-black"
                />
                {lang.label} ({lang.code.toUpperCase()})
              </label>
            ))}
          </div>
          <input
            type="text"
            placeholder="Add custom language code (e.g. de)"
            value={customLanguage}
            onChange={(event) => setCustomLanguage(event.target.value)}
            className="mt-3 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
          />
        </fieldset>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="submit"
          disabled={isUploading || !file}
          className="rounded-full bg-black px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-400"
        >
          {isUploading ? "Uploading…" : "Upload Document"}
        </button>
        {message && <span className="text-sm text-emerald-600">{message}</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </form>
  );
}
