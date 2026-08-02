/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker image için standalone; Vercel kendi runtime'ını kullanır.
  ...(process.env.VERCEL ? {} : { output: 'standalone' }),
};

export default nextConfig;
