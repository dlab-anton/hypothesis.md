"use client";

import { useEffect } from "react";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Root error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 max-w-md text-center">
        <p className="font-medium text-base">Something went wrong</p>
        <p className="mt-2 text-xs opacity-80">
          An unexpected error occurred. Try the request again.
        </p>
      </div>
      <button
        onClick={reset}
        className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50 transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
