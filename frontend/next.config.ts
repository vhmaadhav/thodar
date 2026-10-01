import type { NextConfig } from "next";

// In the single-container deploy the API runs beside Next on 127.0.0.1:8000 and the browser calls
// same-origin /api/* (set NEXT_PUBLIC_API_URL=/api and API_INTERNAL_URL at build time).
const internal = process.env.API_INTERNAL_URL;

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return internal ? [{ source: "/api/:path*", destination: `${internal}/:path*` }] : [];
  },
};

export default nextConfig;
