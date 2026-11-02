/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async redirects() {
    return [
      { source: "/runs", destination: "/settings/logs", permanent: true },
      { source: "/runs/:id", destination: "/settings/logs/:id", permanent: true },
      { source: "/logs", destination: "/settings/logs", permanent: true },
      { source: "/logs/:id", destination: "/settings/logs/:id", permanent: true },
    ];
  },
};

export default nextConfig;
