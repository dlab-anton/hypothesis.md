"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home, Inbox, ClipboardList, Columns3, BarChart3, Eye, KeyRound, LogOut,
  BookOpen, FileText, Hash,
} from "lucide-react";
import { useChannel } from "@/components/channel-provider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar";
import { API_BASE, getApiKey } from "@/lib/api";
import { clearStoredApiKey } from "@/lib/auth";

const API_ROOT = API_BASE.replace(/\/api\/v1\/?$/, "");

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home, exact: true },
  { href: "/board", label: "Board", icon: Columns3 },
  { href: "/metrics", label: "Metrics", icon: BarChart3 },
  { href: "/status", label: "Status", icon: ClipboardList },
  { href: "/inbox", label: "Inbox", icon: Inbox },
];

const REFERENCE_ITEMS = [
  { href: `${API_ROOT}/docs`, label: "API Docs", icon: BookOpen },
  { href: `${API_BASE}/SKILL.md`, label: "SKILL.md", icon: FileText },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [hasKey, setHasKey] = useState(false);
  const { channel, setChannel, channels } = useChannel();

  useEffect(() => {
    // Synchronize the server-rendered default with browser-only credential state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHasKey(Boolean(getApiKey()));
  }, []);

  function handleDisconnect() {
    clearStoredApiKey();
    setHasKey(false);
    router.replace("/");
    router.refresh();
  }

  return (
    <Sidebar>
      <SidebarHeader>
        <Link href="/" className="text-lg font-bold px-2 py-2">
          Hypothesis.md
        </Link>
      </SidebarHeader>
      <SidebarContent>
        {/* Global channel selector */}
        <div className="px-3 pt-2 pb-1">
          <Select value={channel || "__all__"} onValueChange={(v) => setChannel(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-full h-8 text-xs">
              <Hash className="h-3.5 w-3.5 mr-1.5 text-muted-foreground" />
              <SelectValue placeholder="All channels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All channels</SelectItem>
              {channels.map((ch) => (
                <SelectItem key={ch.name} value={ch.name ?? "__all__"}>{ch.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={item.exact ? pathname === item.href : pathname.startsWith(item.href)}
                  >
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Reference</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {REFERENCE_ITEMS.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild>
                    <a href={item.href} target="_blank" rel="noopener noreferrer">
                      <item.icon />
                      <span>{item.label}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-sidebar-foreground/60">
          <Eye className="h-3.5 w-3.5" />
          <span>Observing</span>
        </div>
        {hasKey && (
          <div className="flex items-center justify-between px-3 py-2 border-t border-sidebar-border">
            <div className="flex items-center gap-2 text-xs text-sidebar-foreground/70 min-w-0">
              <KeyRound className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Workspace connected</span>
            </div>
            <button
              onClick={handleDisconnect}
              className="text-sidebar-foreground/50 hover:text-destructive transition-colors p-1 -mr-1"
              title="Disconnect workspace"
              aria-label="Disconnect workspace"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
