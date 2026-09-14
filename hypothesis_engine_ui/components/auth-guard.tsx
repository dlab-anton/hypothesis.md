"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { KeyRound, ArrowRight } from "lucide-react";
import { API_BASE, getApiKey } from "@/lib/apiClient";
import { classifyAuthResponse, clearStoredApiKey } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const AUTH_CHECK_TIMEOUT_MS = 10_000;

function ConnectKeyPrompt() {
  return (
    <div className="flex items-center justify-center h-full p-8">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-muted p-4">
          <KeyRound className="h-8 w-8 text-muted-foreground" />
        </div>
        <h2 className="text-lg font-semibold">Connect your API key</h2>
        <p className="text-sm text-muted-foreground">
          Set up your workspace and API key to access the dashboard.
        </p>
        <Button asChild>
          <Link href="/">
            Go to setup <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<
    "loading" | "authenticated" | "unauthenticated" | "error"
  >("loading");

  const checkAuth = useCallback(async () => {
    setState("loading");
    const key = getApiKey();
    if (!key) {
      setState("unauthenticated");
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/hypotheses/stats`, {
        headers: { "X-API-Key": key },
        signal: AbortSignal.timeout(AUTH_CHECK_TIMEOUT_MS),
      });
      const result = classifyAuthResponse(response.status);
      if (result === "unauthenticated") clearStoredApiKey();
      setState(result);
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    // Initial authentication is an external API synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void checkAuth();
  }, [checkAuth]);

  if (state === "loading") {
    return (
      <div className="flex items-center justify-center h-full p-8 text-muted-foreground text-sm">
        Checking authentication...
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="flex flex-col items-center gap-4 text-center max-w-sm">
          <p className="text-sm text-muted-foreground">
            Unable to reach the API server. Check your connection and try again.
          </p>
          <Button onClick={checkAuth} variant="outline">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (state === "unauthenticated") {
    return <ConnectKeyPrompt />;
  }

  return <>{children}</>;
}
