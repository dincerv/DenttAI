/** @type {import('next').NextConfig} */
const nextConfig = {
  // Sadece Docker build'de standalone. Vercel'de ASLA açma.
  ...(process.env.DOCKER_STANDALONE === '1' ? { output: 'standalone' } : {}),
};

export default nextConfig;
