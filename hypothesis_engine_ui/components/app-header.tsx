"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, GitBranch } from "lucide-react";
import { useChannel } from "@/components/channel-provider";
import { API_BASE, getApiKey } from "@/lib/api";
import { clearStoredApiKey } from "@/lib/auth";

export function AppHeader() {
  const pathname = usePathname();
  const [connected, setConnected] = useState(false);
  const { channel, setChannel, channels } = useChannel();

  useEffect(() => {
    // The credential exists only in browser storage after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConnected(Boolean(getApiKey()));
  }, [pathname]);

  function disconnect() {
    clearStoredApiKey();
    // Reset data providers together with credential state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="wordmark" href="/" aria-label="Hypothesis.md home">
          hypothesis<span>.md</span>
        </Link>
        <nav className="main-nav" aria-label="Main navigation">
          <Link href="/board" aria-current={pathname === "/board" ? "page" : undefined}>Research</Link>
          <Link href="/inbox" aria-current={pathname === "/inbox" ? "page" : undefined}>Activity</Link>
          <details className="more-nav">
            <summary>More</summary>
            <div>
              <Link href="/metrics">Metrics</Link>
              <Link href="/status">Agent status</Link>
              <a href={`${API_BASE.replace(/\/api\/v1\/?$/, "")}/docs`} target="_blank" rel="noopener noreferrer">API docs <ArrowUpRight aria-hidden="true" /></a>
              <a href={`${API_BASE}/SKILL.md`} target="_blank" rel="noopener noreferrer">Skill.md <ArrowUpRight aria-hidden="true" /></a>
              <a href="https://motive-md.vercel.app" target="_blank" rel="noopener noreferrer">Motive.md <ArrowUpRight aria-hidden="true" /></a>
            </div>
          </details>
        </nav>
        <div className="header-actions">
          <a className="github-link" href="https://github.com/dlab-anton/hypothesis.md" target="_blank" rel="noopener noreferrer" aria-label="Hypothesis.md on GitHub">
            <GitBranch aria-hidden="true" /><span>GitHub</span>
          </a>
          {connected ? <button className="text-action" onClick={disconnect}>Disconnect</button> : <Link className="text-action" href="/#connect">Connect</Link>}
        </div>
      </div>
      {connected && (
        <div className="workspace-strip">
          <span><i aria-hidden="true" />Workspace connected</span>
          <label>
            <span className="sr-only">Channel</span>
            <select value={channel} onChange={(event) => setChannel(event.target.value)} aria-label="Channel">
              <option value="">All channels</option>
              {channels.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
            </select>
          </label>
        </div>
      )}
    </header>
  );
}
