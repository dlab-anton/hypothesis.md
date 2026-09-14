"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-sm text-destructive max-w-md text-center">
        <p className="font-medium text-base">Something went wrong</p>
        <p className="mt-2 text-xs opacity-80">
          An unexpected error occurred. Try the request again.
        </p>
      </div>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
