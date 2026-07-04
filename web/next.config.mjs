/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // proxy /api/* to the FastAPI backend so the browser calls same-origin (no CORS)
    return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }];
  },
};

export default nextConfig;
