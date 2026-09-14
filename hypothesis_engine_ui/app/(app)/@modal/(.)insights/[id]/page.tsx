"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getInsight } from "@/lib/apiClient";
import { InsightContent } from "@/app/(app)/insights/[id]/page";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Insight } from "@/types/hypothesis";

export default function InsightModal() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [insight, setInsight] = useState<Insight | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInsight(id)
      .then(setInsight)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load insight"));
  }, [id]);

  return (
    <Dialog
      defaultOpen
      onOpenChange={(open) => {
        if (!open) router.back();
      }}
    >
      <DialogContent className="max-w-xl p-6">
        <DialogTitle className="sr-only">Insight detail</DialogTitle>
        {error ? (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <p className="font-medium">Failed to load insight</p>
            <p className="mt-1 text-xs opacity-80">{error}</p>
          </div>
        ) : !insight ? (
          <div className="text-muted-foreground text-sm">Loading...</div>
        ) : (
          <InsightContent insight={insight} />
        )}
      </DialogContent>
    </Dialog>
  );
}
