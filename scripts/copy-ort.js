// Copies the onnxruntime-web WebAssembly runtime into public/ort/ so it is served as-is.
// This way ORT's multithreading workers load ORT's own loader instead of the app bundle.
import { copyFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const dist = dirname(require.resolve('onnxruntime-web/wasm'));
const out = join(import.meta.dirname, '..', 'public', 'ort');
mkdirSync(out, { recursive: true });
for (const f of ['ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.wasm']) {
  copyFileSync(join(dist, f), join(out, f));
}
console.log(`onnxruntime-web → ${out}`);
