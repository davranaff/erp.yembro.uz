import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(() => {
  const apiProxySource =
    process.env.VITE_DEV_API_PROXY_TARGET ??
    process.env.API_PROXY_TARGET ??
    process.env.VITE_API_BASE_URL ??
    'http://localhost:30000/api/v1';

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
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup/vitest.setup.ts',
      include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    },
  };
});
