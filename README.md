# Sheik Detector 🛡️

*The sharpest eye in all of Hyrule.*

Real-time object detection **in the browser**, styled after *The Legend of Zelda: The Minish Cap*.
It runs **YOLOX-nano** (trained on COCO, 80 classes) with
[onnxruntime-web](https://onnxruntime.ai/docs/tutorials/web/): images and camera frames never leave
the device, and the site is fully static, so it deploys to Vercel with no backend.

- **Camera** — live detection from the webcam / phone camera (front/back switch, pause, save snapshot).
- **Image** — upload or drag & drop a picture and get it annotated; save the result as PNG.
- **Options** — minimum confidence, NMS threshold and the Minish Woods light-ray effect.

## Deploy to Vercel

1. Import this repository in [vercel.com/new](https://vercel.com/new).
2. Vercel reads `vercel.json` (Vite framework, `npm run build`, output `dist/`). No settings to change.
3. Deploy. The camera needs HTTPS, which Vercel provides.

`vercel.json` also sends the `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` headers so
the WebAssembly runtime can use several threads, and caches the model for a year.

## Run locally

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # production build in dist/
npm run preview   # serve dist/
```

## Model

| | |
|---|---|
| Model | YOLOX-nano, `yolox_nano.onnx` from Megvii's [release 0.1.1rc0](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0) |
| License | Apache 2.0 (see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)) |
| Input | 416×416, BGR, 0–255, letterbox top-left padded with 114 (no normalization) |
| Output | 3549 × 85, decoded in `src/detector.js` (grid + stride, obj × class score, per-class NMS) |
| Size | 3.6 MB, in `public/models/` |

The COCO model knows 80 everyday classes (person, car, dog, …). It is **not** trained to detect
damage (cracks, dents, rust, …). To detect damage, fine-tune YOLOX-nano on a damage dataset,
export it to ONNX with YOLOX's `tools/export_onnx.py`, drop the `.onnx` into `public/models/` and
point `src/config.js` at it with your class list. If you export with a recent YOLOX (≥ 0.2.0, no
`--legacy` normalization), the preprocessing in `src/detector.js` stays the same.

## Project layout

```
index.html              three screens: title, quest select, detection
src/main.js             UI, camera/image flow, drawing, inventory and text box
src/detector.js         YOLOX preprocessing, ONNX inference and decoding/NMS
src/config.js           model path, input size and class names
src/style.css           pixel-art UI built from 9-slice sprites (border-image)
public/models/          yolox_nano.onnx
public/sprites/         sprites cut from the sheets in assets-src/sheets
tools/extract_assets.py regenerates public/sprites/ from the sheets (Python + Pillow)
scripts/copy-ort.js     copies the onnxruntime-web .wasm/.mjs into public/ort/ before dev/build
```

## Credits

- **YOLOX** © Megvii Inc., Apache License 2.0.
- *The Legend of Zelda: The Minish Cap* graphics © Nintendo / Capcom. This is a non-commercial fan
  project; it is not affiliated with or endorsed by Nintendo.
- Sprite sheets ripped by **EternalLight** (file select, pause menu), **Chaotic Death**
  (backgrounds and overlays), **Aquatics64** (font) and **Yue** (title screen), from
  The Spriters Resource.
- UI font: [Pixelify Sans](https://fonts.google.com/specimen/Pixelify+Sans) (SIL Open Font License).
