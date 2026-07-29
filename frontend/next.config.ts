import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
    // Strip trailing /api if present so we don't double it
    const backendBase = apiUrl.replace(/\/api\/?$/, '')
    return [
      {
        source: '/api/:path*',
        destination: `${backendBase}/api/:path*`,
      },
    ]
  },
};

export default nextConfig;
