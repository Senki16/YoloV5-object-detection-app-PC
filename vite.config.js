import { defineConfig } from 'vite';

// Cross-origin isolation lets onnxruntime-web use multiple threads (SharedArrayBuffer).
const isolationHeaders = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

export default defineConfig({
  optimizeDeps: { exclude: ['onnxruntime-web'] },
  server: { headers: isolationHeaders },
  preview: { headers: isolationHeaders },
  build: { target: 'es2022', chunkSizeWarningLimit: 1024 },
});
