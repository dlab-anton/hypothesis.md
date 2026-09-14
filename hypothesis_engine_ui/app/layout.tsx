import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppHeader } from "@/components/app-header";
import { ChannelProvider } from "@/components/channel-provider";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hypothesis.md",
  description: "Hypothesis tracking for AI agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <TooltipProvider>
          <ChannelProvider>
            <a className="skip-link" href="#main-content">Skip to content</a>
            <AppHeader />
            <main id="main-content" className="app-main">{children}</main>
          </ChannelProvider>
        </TooltipProvider>
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
