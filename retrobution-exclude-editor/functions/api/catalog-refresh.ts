interface Env {
  EDITOR_KEY: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER?: string;
  GITHUB_REPO?: string;
}

interface WorkflowRun {
  display_title: string;
  status: string;
  conclusion: string | null;
  html_url: string;
}

const encoder = new TextEncoder();
const WORKFLOW_FILE = "editor.yml";
const REQUEST_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function githubApiUrl(env: Env, suffix: string): string {
  const owner = env.GITHUB_OWNER ?? "FinnHornhoover";
  const repo = env.GITHUB_REPO ?? "FFInfoPacks";
  return `https://api.github.com/repos/${owner}/${repo}/${suffix}`;
}

function githubHeaders(env: Env): HeadersInit {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    "Content-Type": "application/json",
    "User-Agent": "FFInfoPacks-exclusion-editor",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function json(data: unknown, status = 200): Response {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src 'none'",
    },
  });
}

function safeEqualHex(expected: string, supplied: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(supplied) || expected.length !== supplied.length) return false;
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= expected.charCodeAt(index) ^ supplied.charCodeAt(index);
  }
  return difference === 0;
}

async function expectedSignature(key: string, timestamp: string, requestId: string): Promise<string> {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign(
    "HMAC",
    cryptoKey,
    encoder.encode(`${timestamp}\n${requestId}\nrefresh-catalog`),
  );
  return Array.from(new Uint8Array(signed), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function normalizeStatus(status: string): "pending" | "queued" | "in_progress" | "completed" {
  if (status === "queued" || status === "in_progress" || status === "completed") return status;
  return "pending";
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.GITHUB_TOKEN || !env.EDITOR_KEY) return json({ error: "Editor secrets are not configured" }, 503);

  let body: { requestId?: unknown; timestamp?: unknown; signature?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "Request body must be JSON" }, 400);
  }

  const { requestId, timestamp, signature } = body;
  if (typeof requestId !== "string" || !REQUEST_ID_PATTERN.test(requestId) ||
      typeof timestamp !== "string" || typeof signature !== "string") {
    return json({ error: "Invalid refresh request" }, 400);
  }

  const submittedAt = Date.parse(timestamp);
  if (!Number.isFinite(submittedAt) || Math.abs(Date.now() - submittedAt) > 5 * 60_000) {
    return json({ error: "Refresh timestamp is expired" }, 401);
  }
  const expected = await expectedSignature(env.EDITOR_KEY, timestamp, requestId);
  if (!safeEqualHex(expected, signature)) return json({ error: "Invalid editor signature" }, 401);

  const response = await fetch(githubApiUrl(env, `actions/workflows/${WORKFLOW_FILE}/dispatches`), {
    method: "POST",
    headers: githubHeaders(env),
    body: JSON.stringify({ ref: "main", inputs: { request_id: requestId } }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null) as { message?: string } | null;
    return json({ error: error?.message ?? `GitHub returned ${response.status}` }, response.status);
  }

  return json({ requestId, status: "pending", conclusion: null, runUrl: null }, 202);
};

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.GITHUB_TOKEN) return json({ error: "GitHub access is not configured" }, 503);
  const requestId = new URL(request.url).searchParams.get("id") ?? "";
  if (!REQUEST_ID_PATTERN.test(requestId)) return json({ error: "Invalid refresh request ID" }, 400);

  const query = new URLSearchParams({ event: "workflow_dispatch", branch: "main", per_page: "50" });
  const response = await fetch(
    githubApiUrl(env, `actions/workflows/${WORKFLOW_FILE}/runs?${query}`),
    { headers: githubHeaders(env) },
  );
  const result = await response.json().catch(() => null) as { workflow_runs?: WorkflowRun[]; message?: string } | null;
  if (!response.ok || !result?.workflow_runs) {
    return json({ error: result?.message ?? `GitHub returned ${response.status}` }, response.status);
  }

  const title = `Refresh exclusion editor (${requestId})`;
  const run = result.workflow_runs.find((candidate) => candidate.display_title === title);
  if (!run) return json({ requestId, status: "pending", conclusion: null, runUrl: null });
  return json({
    requestId,
    status: normalizeStatus(run.status),
    conclusion: run.conclusion,
    runUrl: run.html_url,
  });
};
