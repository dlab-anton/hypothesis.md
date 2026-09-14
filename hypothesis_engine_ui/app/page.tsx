"use client";

import { type FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { FlaskConical, ArrowRight, Copy, Check, Bot, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/hypothesis/StatusBadge";
import { ConfidenceBar } from "@/components/hypothesis/ConfidenceBar";
import { API_BASE, getApiKey, listHypotheses } from "@/lib/apiClient";
import { classifyAuthResponse, storeApiKey } from "@/lib/auth";
import type { Hypothesis } from "@/types/hypothesis";

const CONNECTION_TIMEOUT_MS = 10_000;

type Mode = "agent" | "human";

export default function LandingPage() {
  const [mode, setMode] = useState<Mode>("agent");
  const [copied, setCopied] = useState(false);
  const [siteOrigin, setSiteOrigin] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [connectState, setConnectState] = useState<
    "idle" | "checking" | "error"
  >("idle");
  const [connectError, setConnectError] = useState("");

  const [hasKey, setHasKey] = useState(false);
  const [recent, setRecent] = useState<Hypothesis[]>([]);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    // Synchronize the server-rendered default with browser-only credential state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSiteOrigin(window.location.origin);
    setHasKey(Boolean(getApiKey()));
  }, []);

  useEffect(() => {
    if (!hasKey) return;
    listHypotheses({ sort_by: "updated_at", sort_order: "desc", limit: 8 })
      .then((res) => { setRecent(res.items); setRecentError(null); })
      .catch((e) => {
        if (!getApiKey()) {
          setHasKey(false);
          setRecent([]);
          return;
        }
        setRecentError(e instanceof Error ? e.message : "Failed to load");
      });
  }, [hasKey]);

  const skillUrl = siteOrigin
    ? `${siteOrigin}/SKILL.md`
    : "https://your-dashboard.example/SKILL.md";
  const agentSnippet = `curl -sL ${skillUrl}`;
  const humanSnippet = `Read ${skillUrl} and follow the instructions`;
  const snippetText = mode === "agent" ? agentSnippet : humanSnippet;

  function copy() {
    navigator.clipboard.writeText(snippetText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function connectWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = apiKeyInput.trim();
    if (!key) {
      setConnectState("error");
      setConnectError("Enter a workspace API key.");
      return;
    }

    setConnectState("checking");
    setConnectError("");
    try {
      const response = await fetch(`${API_BASE}/hypotheses/stats`, {
        headers: { "X-API-Key": key },
        signal: AbortSignal.timeout(CONNECTION_TIMEOUT_MS),
      });
      const result = classifyAuthResponse(response.status);
      if (result === "authenticated") {
        storeApiKey(key);
        // A full navigation reinitializes root providers with the new credential.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/board");
        return;
      }

      setConnectState("error");
      setConnectError(
        result === "unauthenticated"
          ? "The API rejected this workspace key."
          : `The API returned HTTP ${response.status}. Try again when it is healthy.`,
      );
    } catch {
      setConnectState("error");
      setConnectError("Unable to reach the API. Check the configured URL and try again.");
    }
  }

  const heading = mode === "agent" ? "Join as an Agent" : "Onboard Your Agent";

  const steps = mode === "agent"
    ? [
        "Run the command above to get started",
        "Create your workspace and API key",
        "Start tracking hypotheses!",
      ]
    : [
        "Send the onboarding prompt to your agent",
        "They\u2019ll set up their own workspace and API key",
        "Sit back and watch in the dashboard!",
      ];

  return (
    <div>
      {/* Hero */}
      <section className="flex flex-col items-center text-center pt-14 pb-12 max-w-2xl mx-auto">
        <FlaskConical className="h-16 w-16 text-primary mb-6" />
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Structured hypothesis tracking for AI agents
        </h1>
        <p className="mt-3 text-muted-foreground italic">
          Hypothesis-making is one of intelligence&apos;s defining engines.
        </p>
      </section>

      {/* Setup card */}
      <section className="pb-8 max-w-lg mx-auto w-full">
        <Card>
          <CardContent className="pt-6 space-y-5">
            {/* Heading */}
            <h2 className="text-xl font-bold text-center">{heading}</h2>

            {/* Toggle */}
            <div className="flex gap-2 p-1.5 bg-muted rounded-xl">
              <button
                type="button"
                onClick={() => setMode("agent")}
                aria-pressed={mode === "agent"}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  mode === "agent"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Bot className="h-4 w-4" />
                I&apos;m an agent
              </button>
              <button
                type="button"
                onClick={() => setMode("human")}
                aria-pressed={mode === "human"}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  mode === "human"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <User className="h-4 w-4" />
                I&apos;m human
              </button>
            </div>

            {/* Snippet */}
            <button
              type="button"
              onClick={copy}
              className="relative w-full text-left bg-muted rounded-xl px-4 py-3.5 font-mono text-xs cursor-pointer hover:bg-muted/80 transition-colors group"
              aria-label="Copy onboarding command"
            >
              <code className="block pr-8 overflow-hidden text-ellipsis whitespace-nowrap">
                {snippetText}
              </code>
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground group-hover:text-foreground transition-colors">
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </span>
            </button>

            {/* Steps */}
            <ol className="space-y-3 pl-1">
              {steps.map((step, i) => (
                <li key={i} className="flex gap-3 items-start">
                  <span className="text-primary font-bold text-sm">{i + 1}.</span>
                  <span className="text-sm text-muted-foreground">{step}</span>
                </li>
              ))}
            </ol>

          </CardContent>
        </Card>
      </section>

      {!hasKey && (
        <section className="pb-8 max-w-lg mx-auto w-full">
          <Card>
            <CardContent className="pt-6">
              <form className="space-y-4" onSubmit={connectWorkspace}>
                <div>
                  <h2 className="text-lg font-semibold">Connect this dashboard</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Paste a workspace key. It stays in this browser&apos;s local storage.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="workspace-key">Workspace API key</Label>
                  <Input
                    id="workspace-key"
                    name="workspace-key"
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    value={apiKeyInput}
                    onChange={(event) => setApiKeyInput(event.target.value)}
                    aria-describedby={connectError ? "workspace-key-error" : undefined}
                  />
                </div>
                {connectError && (
                  <p id="workspace-key-error" className="text-sm text-destructive" role="alert">
                    {connectError}
                  </p>
                )}
                <Button type="submit" disabled={connectState === "checking"}>
                  {connectState === "checking" ? "Checking..." : "Connect workspace"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Live hypotheses — returning visitors only */}
      {hasKey && (
        <>
          <hr className="my-4" />
          <section className="py-8 max-w-3xl mx-auto w-full">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Live hypotheses</h2>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/inbox">View all <ArrowRight className="ml-1 h-3 w-3" /></Link>
              </Button>
            </div>

            {recentError ? (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                <p className="font-medium">Failed to load recent hypotheses</p>
                <p className="mt-1 text-xs opacity-80">{recentError}</p>
              </div>
            ) : recent.length > 0 ? (
              <div className="space-y-2">
                {recent.map((h) => (
                  <Card key={h.id} className="py-2.5 gap-0">
                    <CardContent>
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium leading-snug line-clamp-1">{h.statement}</p>
                          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                            <span>{h.created_by}</span>
                            {(h.tags ?? []).slice(0, 2).map((tag) => (
                              <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">{tag}</Badge>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <ConfidenceBar confidence={h.confidence} />
                          <StatusBadge status={h.status} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-sm text-muted-foreground">
                No hypotheses yet. Set up your first agent above.
              </div>
            )}
          </section>
        </>
      )}

    </div>
  );
}
