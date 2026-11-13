import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', include: ['e2e/**/*.test.tsx'], testTimeout: 20000, restoreMocks: true } });
