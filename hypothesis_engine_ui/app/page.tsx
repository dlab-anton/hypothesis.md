"use client";

import { type FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API_BASE, getApiKey, listHypotheses } from "@/lib/apiClient";
import { classifyAuthResponse, storeApiKey } from "@/lib/auth";
import { STATUS_CONFIG } from "@/lib/constants";
import type { Hypothesis } from "@/types/hypothesis";

export default function LandingPage() {
  const [siteOrigin, setSiteOrigin] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [recent, setRecent] = useState<Hypothesis[]>([]);
  const [recentError, setRecentError] = useState("");
  const [recentLoading, setRecentLoading] = useState(true);

  useEffect(() => {
    // Read browser-only connection state after the server render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSiteOrigin(window.location.origin);
    setHasKey(Boolean(getApiKey()));
  }, []);

  useEffect(() => {
    if (!hasKey) return;
    let active = true;
    listHypotheses({ sort_by: "updated_at", sort_order: "desc", limit: 5 })
      .then((result) => { if (active) setRecent(result.items); })
      .catch(() => { if (active) setRecentError("Recent research could not be loaded."); })
      .finally(() => { if (active) setRecentLoading(false); });
    return () => { active = false; };
  }, [hasKey]);

  const skillUrl = siteOrigin ? `${siteOrigin}/SKILL.md` : "/SKILL.md";
  const agentApi = API_BASE.startsWith("/") ? `${siteOrigin}${API_BASE}` : API_BASE;
  const snippet = `Read ${skillUrl} and follow the instructions. Use ${agentApi} as the API base URL.`;

  async function copyGuide() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setCopyError(false);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
      setCopyError(true);
    }
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = keyInput.trim();
    if (!key) { setError("Enter a workspace API key."); return; }
    setChecking(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/hypotheses/stats`, {
        headers: { "X-API-Key": key }, signal: AbortSignal.timeout(10_000),
      });
      const result = classifyAuthResponse(response.status);
      if (result === "authenticated") {
        storeApiKey(key);
        // Reinitialize data providers with the connected workspace.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/board");
        return;
      }
      setError(result === "unauthenticated"
        ? "The API rejected this workspace key."
        : `The API returned HTTP ${response.status}. Please try again.`);
    } catch {
      setError("Unable to connect. Check the API and try again.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="home-page">
      <header className="page-intro">
        <p className="eyebrow">Hypotheses · Evidence · Insights</p>
        <h1>Shared memory for research.</h1>
        <p>Keep the question, the evidence, and what you learn in one place.</p>
        {hasKey && <Link className="inline-link" href="/board">Open research <ArrowRight aria-hidden="true" /></Link>}
      </header>

      <div className="getting-started">
        <section aria-labelledby="agent-heading">
          <h2 id="agent-heading">Connect your agent</h2>
          <p>Give your agent the guide. It can create a workspace and start recording its work.</p>
          <div className="guide-line">
            <code>{snippet}</code>
            <button type="button" onClick={copyGuide} aria-label="Copy agent instructions" title="Copy instructions">
              {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
            </button>
          </div>
          {copyError && <p role="status">Select and copy the instructions above.</p>}
          <a className="inline-link" href={skillUrl}>Skill.md <ArrowRight aria-hidden="true" /></a>
        </section>

        <section id="connect" aria-labelledby="workspace-heading">
          <h2 id="workspace-heading">{hasKey ? "Your workspace" : "Open your workspace"}</h2>
          {hasKey ? <>
            <p>Your workspace is connected in this browser.</p>
            <Link className="inline-link" href="/board">Browse hypotheses and insights <ArrowRight aria-hidden="true" /></Link>
          </> : <form onSubmit={connect} className="connect-form">
            <p>Use the workspace key from your agent. Never use a server master key.</p>
            <Label htmlFor="workspace-key">Workspace API key</Label>
            <div className="connect-fields">
              <Input id="workspace-key" name="workspace-key" type="password" autoComplete="off" spellCheck={false}
                value={keyInput} onChange={(event) => setKeyInput(event.target.value)}
                aria-describedby={error ? "workspace-error" : "workspace-note"} />
              <Button type="submit" disabled={checking}>{checking ? "Checking…" : "Connect"}</Button>
            </div>
            {error ? <p id="workspace-error" className="text-destructive" role="alert">{error}</p>
              : <p id="workspace-note" className="connection-note">Stored only in this browser. Disconnect at any time.</p>}
          </form>}
        </section>
      </div>

      {hasKey && <section className="recent-research" aria-labelledby="recent-heading">
        <div className="section-heading"><h2 id="recent-heading">Recently updated</h2><Link href="/board">View research <ArrowRight aria-hidden="true" /></Link></div>
        {recentLoading ? <p className="research-empty" role="status">Loading recent research…</p>
          : recentError ? <p role="alert" className="research-empty">{recentError} <Link href="/board">Try the research list.</Link></p>
          : recent.length ? <div className="research-list">{recent.map((item) => <Link className="research-row" key={item.id} href={`/hypotheses/${item.id}`}>
            <div className="research-title">{item.statement}</div>
            <div className="research-meta"><span>{STATUS_CONFIG[item.status]?.label ?? item.status}</span>{item.channel && <span>{item.channel}</span>}<span>{item.created_by}</span></div>
          </Link>)}</div> : <p className="research-empty">No hypotheses yet. Your agent can add the first one.</p>}
      </section>}
    </div>
  );
}
