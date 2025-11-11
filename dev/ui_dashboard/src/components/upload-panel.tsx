"use client";

import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getApiBase } from "@/lib/api";

const UploadSchema = z.object({
  targetLanguages: z.string().default("en"),
});

export default function UploadPanel({ onJobCreated }: { onJobCreated?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<z.infer<typeof UploadSchema>>({
    resolver: zodResolver(UploadSchema),
    defaultValues: { targetLanguages: "en" },
  });

  const handleSubmit = async (values: z.infer<typeof UploadSchema>) => {
    if (!file) {
      toast.error("Select a file to upload");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_languages", values.targetLanguages);

    setSubmitting(true);
    setProgress(25);
    try {
      const response = await fetch(`${getApiBase()}/jobs`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Upload failed");
      }
      setProgress(100);
      toast.success("Job submitted successfully");
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      form.reset();
      onJobCreated?.();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to create job";
      toast.error(message);
    } finally {
      setSubmitting(false);
      setTimeout(() => setProgress(0), 800);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Document</CardTitle>
        <CardDescription>Choose a PDF/DOCX and specify target languages (comma separated).</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form className="space-y-6" onSubmit={form.handleSubmit(handleSubmit)}>
            <FormField
              control={form.control}
              name="targetLanguages"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Target Languages</FormLabel>
                  <FormControl>
                    <Textarea placeholder="e.g. en, fr" {...field} />
                  </FormControl>
                  <FormDescription>Use ISO codes separated by commas.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-2">
              <FormLabel>Source File</FormLabel>
              <Input
                type="file"
                accept=".pdf,.doc,.docx"
                ref={fileInputRef}
                onChange={(event) => {
                  const nextFile = event.target.files?.[0] ?? null;
                  setFile(nextFile);
                }}
              />
            </div>

            {progress > 0 && <Progress value={progress} />}

            <Button type="submit" disabled={submitting}>
              {submitting ? "Submitting..." : "Create Translation Job"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
