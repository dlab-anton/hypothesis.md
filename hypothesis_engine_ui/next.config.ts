import type { NextConfig } from "next";

const API_BACKEND =
  (process.env.HYPOTHESIS_API_URL || "http://localhost:8000/api/v1").replace(
    /\/+$/,
    "",
  );

// Extract origin (scheme + host) for CSP — path-based connect-src is too strict
const API_ORIGIN = (() => {
  try { return new URL(API_BACKEND).origin; } catch { return API_BACKEND; }
})();

const scriptSources = ["'self'", "'unsafe-inline'"];
if (process.env.NODE_ENV !== "production") scriptSources.push("'unsafe-eval'");

const cspDirectives = [
  "default-src 'self'",
  "connect-src 'self'",
  `script-src ${scriptSources.join(" ")}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "geolocation=(), camera=(), microphone=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "Content-Security-Policy", value: cspDirectives },
];

const nextConfig: NextConfig = {
  agentRules: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    return [
      // Agent instruction files
      { source: "/SKILL.md", destination: "/api/v1/SKILL.md" },
      { source: "/skill.md", destination: "/api/v1/skill.md" },
      { source: "/REFERENCE.md", destination: "/api/v1/references/REFERENCE.md" },
      { source: "/HEARTBEAT.md", destination: "/api/v1/references/HEARTBEAT.md" },
      { source: "/references/:path*", destination: "/api/v1/references/:path*" },
    ];
  },
  async redirects() {
    return [{ source: "/docs", destination: `${API_ORIGIN}/docs`, permanent: false }];
  },
};

export default nextConfig;
