// YOLOX-nano (Megvii, release 0.1.1rc0, COCO) inference in the browser with onnxruntime-web.
//
// The release 0.1.1rc0 ONNX models expect this preprocessing:
//   - letterbox anchored top-left, padded with 114
//   - BGR channels, raw 0..255 values (NO mean/std normalization)
//   - output [1, N, 85] not decoded: (dx, dy, log w, log h, obj, 80 classes) per grid cell
// Checked against the YOLOv5 sample bus.jpg with onnxruntime (Python) before porting it here.
import * as ort from 'onnxruntime-web/wasm';

import { COCO_CLASSES } from './coco.js';

const STRIDES = [8, 16, 32];

export class YoloxDetector {
  constructor({ modelUrl, inputSize = 416, classes = COCO_CLASSES } = {}) {
    this.modelUrl = modelUrl;
    this.inputSize = inputSize;
    this.classes = classes;
    this.session = null;
    this.grid = null;
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.canvas.height = inputSize;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
    this.input = new Float32Array(3 * inputSize * inputSize);
  }

  async load(onProgress) {
    ort.env.wasm.wasmPaths = '/ort/';
    ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1;
    const bytes = await fetchWithProgress(this.modelUrl, onProgress);
    this.session = await ort.InferenceSession.create(bytes, { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
    this.inputName = this.session.inputNames[0];
    const dims = this.session.inputMetadata?.[0]?.shape;
    if (Array.isArray(dims) && typeof dims[2] === 'number') this.inputSize = dims[2];
    this.grid = buildGrid(this.inputSize);
  }

  /** @param {CanvasImageSource} source  @returns {Promise<{boxes: Array, ms: number}>} */
  async detect(source, srcW, srcH, { scoreThr = 0.35, nmsThr = 0.45 } = {}) {
    const S = this.inputSize;
    const r = Math.min(S / srcW, S / srcH);
    const w = Math.round(srcW * r);
    const h = Math.round(srcH * r);

    const ctx = this.ctx;
    ctx.fillStyle = 'rgb(114,114,114)';
    ctx.fillRect(0, 0, S, S);
    ctx.drawImage(source, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, S, S);

    const plane = S * S;
    const input = this.input;
    for (let i = 0, p = 0; i < plane; i++, p += 4) {
      input[i] = data[p + 2]; // B
      input[i + plane] = data[p + 1]; // G
      input[i + 2 * plane] = data[p]; // R
    }

    const t0 = performance.now();
    const feeds = { [this.inputName]: new ort.Tensor('float32', input, [1, 3, S, S]) };
    const results = await this.session.run(feeds);
    const ms = performance.now() - t0;
    const out = results[this.session.outputNames[0]];
    const boxes = this.decode(out.data, out.dims, r, srcW, srcH, scoreThr, nmsThr);
    return { boxes, ms };
  }

  decode(raw, dims, ratio, srcW, srcH, scoreThr, nmsThr) {
    const [, n, stride] = dims;
    const numClasses = stride - 5;
    const { gx, gy, gs } = this.grid;
    const candidates = [];
    for (let i = 0; i < n; i++) {
      const o = i * stride;
      const obj = raw[o + 4];
      if (obj < scoreThr) continue;
      let best = 0;
      let cls = 0;
      for (let c = 0; c < numClasses; c++) {
        const v = raw[o + 5 + c];
        if (v > best) {
          best = v;
          cls = c;
        }
      }
      const score = obj * best;
      if (score < scoreThr) continue;
      const cx = (raw[o] + gx[i]) * gs[i];
      const cy = (raw[o + 1] + gy[i]) * gs[i];
      const bw = Math.exp(raw[o + 2]) * gs[i];
      const bh = Math.exp(raw[o + 3]) * gs[i];
      candidates.push({
        x1: clamp((cx - bw / 2) / ratio, 0, srcW),
        y1: clamp((cy - bh / 2) / ratio, 0, srcH),
        x2: clamp((cx + bw / 2) / ratio, 0, srcW),
        y2: clamp((cy + bh / 2) / ratio, 0, srcH),
        score,
        cls,
        label: this.classes[cls] ?? `class ${cls}`,
      });
    }
    return nms(candidates, nmsThr);
  }
}

function buildGrid(size) {
  const gx = [];
  const gy = [];
  const gs = [];
  for (const s of STRIDES) {
    const g = Math.floor(size / s);
    for (let y = 0; y < g; y++) {
      for (let x = 0; x < g; x++) {
        gx.push(x);
        gy.push(y);
        gs.push(s);
      }
    }
  }
  return { gx: Float32Array.from(gx), gy: Float32Array.from(gy), gs: Float32Array.from(gs) };
}

// Per-class NMS (equivalent to YOLOX's class-aware multiclass_nms).
function nms(boxes, thr) {
  boxes.sort((a, b) => b.score - a.score);
  const keep = [];
  for (const b of boxes) {
    if (keep.every((k) => k.cls !== b.cls || iou(k, b) <= thr)) keep.push(b);
  }
  return keep;
}

function iou(a, b) {
  const iw = Math.max(0, Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1));
  const ih = Math.max(0, Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1));
  const inter = iw * ih;
  const union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter;
  return union > 0 ? inter / union : 0;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

async function fetchWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not download the model (${res.status})`);
  const total = Number(res.headers.get('content-length')) || 0;
  if (!res.body || !total) return new Uint8Array(await res.arrayBuffer());
  const reader = res.body.getReader();
  const buf = new Uint8Array(total);
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf.set(value, loaded);
    loaded += value.length;
    onProgress?.(loaded / total);
  }
  return loaded === total ? buf : buf.slice(0, loaded);
}
