/** @type {import('next').NextConfig} */
const nextConfig = {
  // Sadece Docker build'de standalone. Vercel'de ASLA açma.
  ...(process.env.DOCKER_STANDALONE === '1' ? { output: 'standalone' } : {}),

  // Lokal UI → bulut API (CORS bypass). .env.local içinde API_PROXY_TARGET set et.
  async rewrites() {
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    return [
      {
        source: '/api/:path*',
        destination: `${target.replace(/\/$/, '')}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
