import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/types/api";
import {
  API_KEY_STORAGE_KEY,
  clearStoredApiKey,
  getStoredApiKey,
} from "./auth";

/** Full API base including /api/v1 prefix (used for raw fetch in auth-guard). */
export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(
    /\/+$/,
    "",
  );

// Generated paths include /api/v1 prefix, so client baseUrl is the server root
const BASE_URL = API_BASE.replace(/\/api\/v1\/?$/, "");

export const STORAGE_KEY = API_KEY_STORAGE_KEY;
const REQUEST_TIMEOUT_MS = 30_000;

export function getApiKey(): string {
  return getStoredApiKey();
}

/** Clear stored key and redirect to login on auth failure. */
export function handleAuthFailure(): void {
  if (typeof window !== "undefined") {
    clearStoredApiKey();
    if (window.location.pathname !== "/") {
      // This utility runs outside React and must reset all root credential state.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/");
    }
  }
}

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const apiKey = getApiKey();
    if (apiKey) request.headers.set("X-API-Key", apiKey);
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401 || response.status === 403) {
      handleAuthFailure();
      throw new Error("Authentication failed");
    }
    // Non-auth errors are handled by openapi-fetch via { data, error }
    return response;
  },
};

const timeoutFetch: typeof globalThis.fetch = async (input, init) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
};

export const client = createClient<paths>({
  baseUrl: BASE_URL,
  fetch: timeoutFetch,
});
client.use(authMiddleware);
