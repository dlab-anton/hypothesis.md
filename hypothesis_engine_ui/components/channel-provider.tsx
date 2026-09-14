"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getApiKey, listChannels } from "@/lib/apiClient";
import type { Channel } from "@/types/hypothesis";

const STORAGE_KEY = "he_channel";

interface ChannelContextValue {
  /** Selected channel name, or "" for "All channels" */
  channel: string;
  setChannel: (ch: string) => void;
  channels: Channel[];
  refreshChannels: () => Promise<void>;
}

const ChannelContext = createContext<ChannelContextValue>({
  channel: "",
  setChannel: () => {},
  channels: [],
  refreshChannels: async () => {},
});

export function useChannel() {
  return useContext(ChannelContext);
}

export function ChannelProvider({ children }: { children: React.ReactNode }) {
  const [channel, setChannelState] = useState("");
  const [channels, setChannels] = useState<Channel[]>([]);

  // Restore persisted selection
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    // Synchronize the server-rendered default with browser-only preference state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved) setChannelState(saved);
  }, []);

  // Fetch channel list
  const refreshChannels = useCallback(async () => {
    if (!getApiKey()) {
      return;
    }

    try {
      const list = await listChannels();
      setChannels(Array.isArray(list) ? list : []);
    } catch {
      // silently ignore — channels dropdown stays empty
    }
  }, []);

  useEffect(() => {
    // Initial channel loading synchronizes with the configured external API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshChannels();
  }, [refreshChannels]);

  function setChannel(ch: string) {
    setChannelState(ch);
    if (ch) {
      localStorage.setItem(STORAGE_KEY, ch);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  return (
    <ChannelContext.Provider value={{ channel, setChannel, channels, refreshChannels }}>
      {children}
    </ChannelContext.Provider>
  );
}
