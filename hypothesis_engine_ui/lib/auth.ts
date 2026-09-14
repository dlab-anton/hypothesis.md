export const API_KEY_STORAGE_KEY = "he_api_key";

export type AuthCheckResult = "authenticated" | "unauthenticated" | "error";

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";

  try {
    return window.localStorage.getItem(API_KEY_STORAGE_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

export function storeApiKey(key: string): void {
  window.localStorage.setItem(API_KEY_STORAGE_KEY, key.trim());
}

export function clearStoredApiKey(): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.removeItem(API_KEY_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}

export function classifyAuthResponse(status: number): AuthCheckResult {
  if (status === 401 || status === 403) return "unauthenticated";
  if (status >= 200 && status < 300) return "authenticated";
  return "error";
}
