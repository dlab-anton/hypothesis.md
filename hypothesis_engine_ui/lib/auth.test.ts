import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import {
  API_KEY_STORAGE_KEY,
  classifyAuthResponse,
  clearStoredApiKey,
  getStoredApiKey,
  storeApiKey,
} from "./auth.ts";

const originalWindow = globalThis.window;

function stubWindow(initialKey?: string) {
  const values = new Map<string, string>();
  if (initialKey !== undefined) values.set(API_KEY_STORAGE_KEY, initialKey);

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    },
  });
  return values;
}

afterEach(() => {
  if (originalWindow === undefined) {
    Reflect.deleteProperty(globalThis, "window");
  } else {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});

describe("workspace API key storage", () => {
  it("has no server-side or environment fallback", () => {
    process.env.NEXT_PUBLIC_HYPOTHESIS_API_KEY = "must-not-be-used";
    assert.equal(getStoredApiKey(), "");
    delete process.env.NEXT_PUBLIC_HYPOTHESIS_API_KEY;
  });

  it("reads, trims, writes, and clears only browser localStorage", () => {
    const values = stubWindow("  workspace-key  ");
    assert.equal(getStoredApiKey(), "workspace-key");

    storeApiKey("  replacement-key  ");
    assert.equal(values.get(API_KEY_STORAGE_KEY), "replacement-key");

    clearStoredApiKey();
    assert.equal(getStoredApiKey(), "");
  });
});

describe("auth response classification", () => {
  for (const status of [200, 201, 204, 299]) {
    it(`accepts successful status ${status}`, () => {
      assert.equal(classifyAuthResponse(status), "authenticated");
    });
  }

  for (const status of [401, 403]) {
    it(`rejects credential status ${status}`, () => {
      assert.equal(classifyAuthResponse(status), "unauthenticated");
    });
  }

  for (const status of [300, 400, 404, 429, 500, 503]) {
    it(`does not authenticate failed status ${status}`, () => {
      assert.equal(classifyAuthResponse(status), "error");
    });
  }
});
