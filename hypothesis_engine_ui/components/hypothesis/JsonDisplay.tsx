"use client";

function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) return <span className="text-muted-foreground">—</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number" || typeof value === "string") return <span>{String(value)}</span>;
  if (Array.isArray(value)) {
    return <span>{value.map(String).join(", ")}</span>;
  }
  if (typeof value === "object") {
    return (
      <pre className="text-xs text-muted-foreground mt-0.5 whitespace-pre-wrap">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span>{String(value)}</span>;
}

export function JsonDisplay({
  data,
  className = "",
}: {
  data: Record<string, unknown>;
  className?: string;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  return (
    <dl className={`space-y-1 text-sm ${className}`}>
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-2">
          <dt className="text-muted-foreground min-w-[120px] shrink-0">
            {key.replace(/_/g, " ")}:
          </dt>
          <dd className="break-words">{renderValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
