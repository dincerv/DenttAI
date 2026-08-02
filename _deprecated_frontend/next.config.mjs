/** @type {import('next').NextConfig} */
const nextConfig = {
  // Deprecated duplicate of ui/. Vercel'de deploy etme.
  ...(process.env.DOCKER_STANDALONE === '1' ? { output: 'standalone' } : {}),
};

export default nextConfig;
