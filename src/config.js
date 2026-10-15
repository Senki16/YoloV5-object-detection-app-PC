import { COCO_CLASSES } from './coco.js';

// To use another YOLOX model exported to ONNX (e.g. one fine-tuned on your own classes),
// copy the .onnx into public/models/ and change the path, input size and class list here.
export const CONFIG = {
  model: {
    modelUrl: '/models/yolox_nano.onnx',
    inputSize: 416,
    classes: COCO_CLASSES,
  },
};
