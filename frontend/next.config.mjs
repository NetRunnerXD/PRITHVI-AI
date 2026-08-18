/** @type {import('next').NextConfig} */
const apiBase = process.env.NEXT_PUBLIC_API_BASE;

const nextConfig = {
  async rewrites() {
    // Default: the browser calls FastAPI directly (CORS). Rewrite only if
    // the web app is configured for same-origin `/api` (empty API base).
    if (apiBase === undefined || apiBase) return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
