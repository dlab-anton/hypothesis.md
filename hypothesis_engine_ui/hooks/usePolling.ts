"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UsePollingOptions {
  intervalMs: number;
  storageKey: string;
  enabled?: boolean;
}

interface UsePollingResult {
  autoRefresh: boolean;
  setAutoRefresh: (enabled: boolean) => void;
  lastUpdated: Date | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function usePolling(
  fetchFn: () => Promise<void>,
  options: UsePollingOptions,
): UsePollingResult {
  const { intervalMs, storageKey, enabled = true } = options;

  const [autoRefresh, setAutoRefreshState] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(storageKey) !== "false";
    }
    return true;
  });
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef(fetchFn);
  const inFlightRef = useRef(false);

  useEffect(() => {
    fetchRef.current = fetchFn;
  }, [fetchFn]);

  const setAutoRefresh = useCallback(
    (value: boolean) => {
      setAutoRefreshState(value);
      if (typeof window !== "undefined") {
        localStorage.setItem(storageKey, String(value));
      }
    },
    [storageKey],
  );

  const refresh = useCallback(async () => {
    if (inFlightRef.current) return; // prevent overlapping fetches
    inFlightRef.current = true;
    setLoading(true);
    try {
      await fetchRef.current();
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (enabled) refresh();
  }, [enabled, refresh]);

  // Polling interval
  useEffect(() => {
    if (!autoRefresh || !enabled) return;
    const interval = setInterval(refresh, intervalMs);
    return () => clearInterval(interval);
  }, [autoRefresh, enabled, intervalMs, refresh]);

  return { autoRefresh, setAutoRefresh, lastUpdated, loading, refresh };
}
