import path from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig(() => {
  let apiProxySource = 'http://localhost:30000/api/v1';
  for (const value of [
    process.env.VITE_DEV_API_PROXY_TARGET,
    process.env.API_PROXY_TARGET,
    process.env.VITE_API_BASE_URL,
  ]) {
    if (typeof value === 'string' && value.length > 0) {
      apiProxySource = value;
      break;
    }
  }

  const apiProxyTarget = (() => {
    try {
      return new URL(apiProxySource).origin;
    } catch {
      return 'http://localhost:30000';
    }
  })();

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5174,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
