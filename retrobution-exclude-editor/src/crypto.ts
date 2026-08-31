import type { Catalog } from "./types";

const MAGIC = new TextEncoder().encode("FFIPED01");
const PBKDF2_ITERATIONS = 600_000;

function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

async function decompressGzip(bytes: Uint8Array): Promise<string> {
  if (!("DecompressionStream" in globalThis)) {
    throw new Error("This browser does not support secure catalog decompression.");
  }
  const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).text();
}

export async function decryptCatalog(envelope: ArrayBuffer, passphrase: string): Promise<Catalog> {
  const bytes = new Uint8Array(envelope);
  if (bytes.length < 53 || !equalBytes(bytes.slice(0, 8), MAGIC)) {
    throw new Error("The encrypted catalog is missing or invalid.");
  }

  const salt = bytes.slice(8, 24);
  const nonce = bytes.slice(24, 36);
  const ciphertext = bytes.slice(36);
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: PBKDF2_ITERATIONS },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"],
  );

  let compressed: ArrayBuffer;
  try {
    compressed = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce, additionalData: MAGIC },
      key,
      ciphertext,
    );
  } catch {
    throw new Error("That key is not valid.");
  }

  const catalog = JSON.parse(await decompressGzip(new Uint8Array(compressed))) as Catalog;
  if (catalog.formatVersion !== 1 || typeof catalog.builtAt !== "string" || !Array.isArray(catalog.items) || catalog.icons === null) {
    throw new Error("The decrypted catalog format is not supported.");
  }
  return catalog;
}

export async function signSubmission(
  passphrase: string,
  timestamp: string,
  sha: string,
  content: string,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const message = new TextEncoder().encode(`${timestamp}\n${sha}\n${content}`);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, message));
  return Array.from(signature, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function signCatalogRefresh(
  passphrase: string,
  timestamp: string,
  requestId: string,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const message = new TextEncoder().encode(`${timestamp}\n${requestId}\nrefresh-catalog`);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, message));
  return Array.from(signature, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
