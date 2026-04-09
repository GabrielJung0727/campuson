/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@campuson/shared'],
  experimental: {
    typedRoutes: true,
  },
};

export default nextConfig;
