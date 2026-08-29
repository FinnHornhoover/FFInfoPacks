import { parse } from "yaml";

interface Env {
  EDITOR_KEY: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER?: string;
  GITHUB_REPO?: string;
}

interface GitHubFile {
  content: string;
  encoding: "base64";
  sha: string;
}

const ITEM_KEYS = new Set([
  "backitem",
  "glassitem",
  "hatitem",
  "pantsitem",
  "shirtsitem",
  "shoesitem",
  "weaponitem",
  "vehicleitem",
  "generalitem",
  "chestitem",
]);
const FILE_PATH = "config/exclude-retrobution.yml";
const encoder = new TextEncoder();

function githubUrl(env: Env): string {
  const owner = env.GITHUB_OWNER ?? "FinnHornhoover";
  const repo = env.GITHUB_REPO ?? "FFInfoPacks";
  return `https://api.github.com/repos/${owner}/${repo}/contents/${FILE_PATH}`;
}

function githubHeaders(env: Env): HeadersInit {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    "User-Agent": "FFInfoPacks-exclusion-editor",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function decodeBase64(value: string): string {
  const binary = atob(value.replace(/\s/g, ""));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function encodeBase64(value: string): string {
  const bytes = encoder.encode(value);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

async function getCurrentFile(env: Env): Promise<{ response: Response; file?: GitHubFile }> {
  const response = await fetch(`${githubUrl(env)}?ref=main`, { headers: githubHeaders(env) });
  if (!response.ok) return { response };
  return { response, file: (await response.json()) as GitHubFile };
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

async function expectedSignature(key: string, timestamp: string, sha: string, content: string): Promise<string> {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign("HMAC", cryptoKey, encoder.encode(`${timestamp}\n${sha}\n${content}`));
  return Array.from(new Uint8Array(signed), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function yamlMapping(source: string): Record<string, unknown> {
  const parsed = parse(source);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("YAML root must be a mapping");
  }
  return parsed as Record<string, unknown>;
}

export function validateChange(currentSource: string, proposedSource: string): void {
  const current = yamlMapping(currentSource);
  const proposed = yamlMapping(proposedSource);
  const withoutItems = (value: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(value).filter(([key]) => !ITEM_KEYS.has(key)));

  if (JSON.stringify(withoutItems(current)) !== JSON.stringify(withoutItems(proposed))) {
    throw new Error("Only item exclusion lists may be changed");
  }
  if (Object.keys(current).join("\n") !== Object.keys(proposed).join("\n")) {
    throw new Error("YAML keys or key order changed");
  }

  for (const key of ITEM_KEYS) {
    const value = proposed[key];
    if (!Array.isArray(value) || value.some((id) => !Number.isSafeInteger(id))) {
      throw new Error(`${key} must be a list of integer IDs`);
    }
    if (new Set(value).size !== value.length) {
      throw new Error(`${key} contains duplicate IDs`);
    }
    for (let index = 1; index < value.length; index += 1) {
      if ((value[index - 1] as number) > (value[index] as number)) {
        throw new Error(`${key} must be sorted`);
      }
    }
  }
}

export const onRequestGet: PagesFunction<Env> = async ({ env }) => {
  if (!env.GITHUB_TOKEN) return json({ error: "GitHub access is not configured" }, 503);
  const { response, file } = await getCurrentFile(env);
  if (!file) return json({ error: `GitHub returned ${response.status}` }, 502);
  return json({ content: decodeBase64(file.content), sha: file.sha });
};

export const onRequestPut: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.GITHUB_TOKEN || !env.EDITOR_KEY) return json({ error: "Editor secrets are not configured" }, 503);
  if (Number(request.headers.get("content-length") ?? "0") > 256_000) {
    return json({ error: "Request is too large" }, 413);
  }

  let body: { content?: unknown; sha?: unknown; signature?: unknown; timestamp?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ error: "Request body must be JSON" }, 400);
  }
  const { content, sha, signature, timestamp } = body;
  if (typeof content !== "string" ||
      typeof sha !== "string" ||
      typeof signature !== "string" ||
      typeof timestamp !== "string") {
    return json({ error: "Missing submission fields" }, 400);
  }
  if (content.length > 128_000) return json({ error: "YAML is too large" }, 413);

  const submittedAt = Date.parse(timestamp);
  if (!Number.isFinite(submittedAt) || Math.abs(Date.now() - submittedAt) > 5 * 60_000) {
    return json({ error: "Submission timestamp is expired" }, 401);
  }
  const expected = await expectedSignature(env.EDITOR_KEY, timestamp, sha, content);
  if (!safeEqualHex(expected, signature)) return json({ error: "Invalid editor signature" }, 401);

  const { response: currentResponse, file: currentFile } = await getCurrentFile(env);
  if (!currentFile) return json({ error: `GitHub returned ${currentResponse.status}` }, 502);
  if (currentFile.sha !== sha) return json({ error: "The exclusion file changed; reload before submitting" }, 409);

  try {
    validateChange(decodeBase64(currentFile.content), content);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "Invalid YAML change" }, 400);
  }

  const updateResponse = await fetch(githubUrl(env), {
    method: "PUT",
    headers: { ...githubHeaders(env), "Content-Type": "application/json" },
    body: JSON.stringify({
      message: "chore(retrobution): update excluded items",
      content: encodeBase64(content),
      sha,
      branch: "main",
    }),
  });
  const update = await updateResponse.json() as {
    message?: string;
    content?: { sha: string };
    commit?: { sha: string; html_url: string };
  };
  if (!updateResponse.ok || !update.commit || !update.content) {
    return json({ error: update.message ?? `GitHub returned ${updateResponse.status}` }, updateResponse.status);
  }
  return json({
    commitUrl: update.commit.html_url,
    commitSha: update.commit.sha,
    contentSha: update.content.sha,
  });
};
