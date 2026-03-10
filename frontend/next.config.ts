import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    output: "standalone",
    experimental: {
        serverActions: {
            bodySizeLimit: '100mb',
        },
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.BACKEND_URL || 'http://127.0.0.1:8000/api/:path*', // Proxy to Backend Service (Localhost default)
            },
        ];
    },
};

export default nextConfig;
