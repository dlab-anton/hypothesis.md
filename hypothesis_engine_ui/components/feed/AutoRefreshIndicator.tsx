"use client";

import { useEffect, useState } from "react";
import { Switch } from "@/components/ui/switch";

export function AutoRefreshIndicator({
  enabled,
  onToggle,
  lastUpdated,
}: {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  lastUpdated: Date | null;
}) {
  const [secondsAgo, setSecondsAgo] = useState<number | null>(null);

  useEffect(() => {
    if (!lastUpdated) return;
    const interval = setInterval(() => {
      setSecondsAgo(
        Math.floor((Date.now() - lastUpdated.getTime()) / 1000),
      );
    }, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated]);

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground">
      <div className="flex items-center gap-1.5">
        <Switch
          checked={enabled}
          onCheckedChange={onToggle}
          className="scale-75"
        />
        <span>Auto-refresh</span>
      </div>
      {lastUpdated && (
        <span>Updated {secondsAgo ?? 0}s ago</span>
      )}
    </div>
  );
}
