import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return { plugins: [react(), tailwindcss()], server: { proxy: { '/backend': { target: env.SAMAY_BACKEND_URL || 'http://127.0.0.1:8010', changeOrigin: true, rewrite: path => path.replace(/^\/backend/, '') } } }, test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', restoreMocks: true, exclude: ['**/node_modules/**', '**/e2e/**'] } };
});
