import type { ExclusionFile } from "./types";

export async function fetchExclusions(): Promise<ExclusionFile> {
  const response = await fetch("/api/exclusions", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error((await response.text()) || "Could not load the current exclusion file.");
  }
  return response.json() as Promise<ExclusionFile>;
}

export async function submitExclusions(
  content: string,
  sha: string,
  signature: string,
  timestamp: string,
): Promise<{ commitUrl: string; commitSha: string; contentSha: string }> {
  const response = await fetch("/api/exclusions", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, sha, signature, timestamp }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: string } | null;
    const error = new Error(body?.error ?? "GitHub rejected the update.");
    if (response.status === 409) error.name = "ConflictError";
    throw error;
  }
  return response.json() as Promise<{ commitUrl: string; commitSha: string; contentSha: string }>;
}
