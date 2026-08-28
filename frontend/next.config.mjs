/** @type {import('next').NextConfig} */
const apiBase = process.env.NEXT_PUBLIC_API_BASE;
const internalApi = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Browser calls FastAPI directly when NEXT_PUBLIC_API_BASE is set (CORS).
    // Empty base = same-origin `/api` proxied to the API process.
    if (apiBase === undefined || apiBase) return [];
    return [
      { source: "/api/:path*", destination: `${internalApi}/api/:path*` },
      { source: "/docs", destination: `${internalApi}/docs` },
      { source: "/openapi.json", destination: `${internalApi}/openapi.json` },
    ];
  },
};

export default nextConfig;
