import './style.css';

import { CONFIG } from './config.js';
import { YoloxDetector } from './detector.js';

const $ = (sel) => document.querySelector(sel);

const state = {
  mode: 'camera',
  scoreThr: 0.35,
  nmsThr: 0.45,
  facing: 'environment',
  stream: null,
  running: false,
  paused: false,
  image: null,
  lastBoxes: [],
  modelReady: null,
};

const detector = new YoloxDetector(CONFIG.model);
const canvas = $('#canvas');
const ctx = canvas.getContext('2d');
const video = $('#video');

// ---------------------------------------------------------------- preload
// Backgrounds and animation frames are set from CSS, so the browser would only fetch each one the
// first time it is shown, leaving the screen blank for a moment. Fetch and decode them up front.
const BACKGROUNDS = [
  'bg-title', 'bg-pattern',
  ...[0, 1, 2, 3].map((i) => `bg-fileselect-${i}`),
  ...[0, 1, 2, 3].map((i) => `rays-${i}`),
];
const preloaded = BACKGROUNDS.map((name) => {
  const img = new Image();
  img.src = `/sprites/${name}.png`;
  return img.decode().catch(() => {});
});
const fileSelectReady = Promise.all(preloaded.slice(2, 6));

// ---------------------------------------------------------------- screens
function show(id) {
  document.querySelectorAll('.screen').forEach((s) => s.classList.toggle('is-active', s.id === id));
}

// ---------------------------------------------------------------- title
async function startGame() {
  await fileSelectReady;
  show('screen-menu');
  selectMenuItem(0);
  document.querySelectorAll('.menu-item')[0].focus();
  loadModel();
}
$('#btn-press-start').addEventListener('click', startGame);
document.addEventListener('keydown', (e) => {
  if ($('#screen-title').classList.contains('is-active') && (e.key === 'Enter' || e.key === ' ')) {
    e.preventDefault();
    startGame();
  }
});

// ---------------------------------------------------------------- model loading
const HEARTS = 10;
function renderHearts(progress) {
  const full = Math.round(progress * HEARTS * 2) / 2;
  const box = $('#loader-hearts');
  box.innerHTML = '';
  for (let i = 0; i < HEARTS; i++) {
    const img = document.createElement('img');
    // heart-0 full, heart-2 half, heart-4 empty (heart row from the file-select sheet)
    img.src = i + 1 <= full ? '/sprites/heart-0.png' : i + 0.5 === full ? '/sprites/heart-2.png' : '/sprites/heart-4.png';
    img.alt = '';
    box.append(img);
  }
}

function loadModel() {
  if (state.modelReady) return state.modelReady;
  renderHearts(0);
  const loader = $('#model-loader');
  state.modelReady = detector
    .load((p) => {
      renderHearts(p);
      $('#loader-text').textContent = `Awakening the Eye of Sheik… ${Math.round(p * 100)}%`;
    })
    .then(() => {
      renderHearts(1);
      loader.classList.add('is-ready');
      $('#loader-text').textContent = 'The Eye of Sheik is ready!';
    })
    .catch((err) => {
      console.error(err);
      loader.classList.add('is-error');
      $('#loader-text').textContent = `The model failed to awaken: ${err.message}`;
      state.modelReady = null;
      throw err;
    });
  return state.modelReady;
}

// ---------------------------------------------------------------- menu
const DESCRIPTIONS = {
  camera: 'Use your device camera to detect objects in real time.',
  image: 'Upload an image and the Eye of Sheik will reveal everything in it.',
  options: 'Tune the minimum confidence, NMS and visual effects.',
};
const menuItems = [...document.querySelectorAll('.menu-item')];
let menuIndex = 0;

function selectMenuItem(i) {
  menuIndex = (i + menuItems.length) % menuItems.length;
  menuItems.forEach((b, j) => b.classList.toggle('is-selected', j === menuIndex));
  $('#menu-description').textContent = DESCRIPTIONS[menuItems[menuIndex].dataset.mode];
}

menuItems.forEach((btn, i) => {
  btn.addEventListener('mouseenter', () => selectMenuItem(i));
  btn.addEventListener('focus', () => selectMenuItem(i));
  btn.addEventListener('click', () => chooseMode(btn.dataset.mode));
});

document.addEventListener('keydown', (e) => {
  if (!$('#screen-menu').classList.contains('is-active') || !$('#options-panel').hidden) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    selectMenuItem(menuIndex + (e.key === 'ArrowDown' ? 1 : -1));
    menuItems[menuIndex].focus();
  }
});

// Walking Link as the menu cursor
let walkFrame = 0;
setInterval(() => {
  walkFrame = (walkFrame + 1) % 10;
  document.querySelectorAll('.menu-item .cursor').forEach((img) => (img.src = `/sprites/link-walk-${walkFrame}.png`));
}, 120);

function chooseMode(mode) {
  if (mode === 'options') {
    $('#options-panel').hidden = false;
    $('#opt-score').focus();
    return;
  }
  enterDetect(mode);
}

// ---------------------------------------------------------------- options
function bindRange(id, key) {
  const input = $(`#${id}`);
  const out = $(`#${id}-out`);
  input.addEventListener('input', () => {
    state[key] = Number(input.value);
    out.textContent = state[key].toFixed(2);
    if (state.mode === 'image' && state.image) runOnImage();
  });
}
bindRange('opt-score', 'scoreThr');
bindRange('opt-nms', 'nmsThr');
$('#opt-rays').addEventListener('change', (e) => document.body.classList.toggle('no-rays', !e.target.checked));
$('#btn-options-close').addEventListener('click', () => {
  $('#options-panel').hidden = true;
  menuItems[menuIndex].focus();
});

// ---------------------------------------------------------------- detection
async function enterDetect(mode) {
  state.mode = mode;
  state.paused = false;
  state.lastBoxes = [];
  $('#btn-pause').textContent = 'Pause';
  $('#btn-pause').hidden = mode !== 'camera';
  $('#btn-flip').style.visibility = mode === 'camera' ? 'visible' : 'hidden';
  $('#detect-title').textContent = mode === 'camera' ? 'CAMERA' : 'IMAGE';
  $('#dropzone').hidden = mode !== 'image' || !!state.image;
  show('screen-detect');
  updateInventory([]);
  clearCanvas();

  say('The Eye of Sheik is getting ready…');
  try {
    await loadModel();
  } catch {
    say('Could not load the model. Check your connection and go back to the menu.', 'hl-red');
    return;
  }
  if (mode === 'camera') startCamera();
  else if (state.image) runOnImage();
  else say('Choose an image for the Eye of Sheik to examine.');
}

function clearCanvas() {
  canvas.width = 640;
  canvas.height = 480;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

$('#btn-back').addEventListener('click', () => {
  stopCamera();
  show('screen-menu');
  menuItems[menuIndex].focus();
});

// ---- camera
async function startCamera() {
  stopCamera();
  if (!navigator.mediaDevices?.getUserMedia) {
    say('This browser cannot use the camera (HTTPS is required).', 'hl-red');
    return;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: state.facing, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
  } catch (err) {
    say(`No camera access: ${err.name === 'NotAllowedError' ? 'permission denied' : err.message}`, 'hl-red');
    return;
  }
  video.srcObject = state.stream;
  await video.play();
  state.running = true;
  say('Look around! The Eye of Sheik is now watching.');
  loop();
}

function stopCamera() {
  state.running = false;
  state.stream?.getTracks().forEach((t) => t.stop());
  state.stream = null;
  video.srcObject = null;
}

let lastFrameAt = 0;
let fps = 0;
async function loop() {
  if (!state.running) return;
  if (!state.paused && video.readyState >= 2) {
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    ctx.drawImage(video, 0, 0, w, h);
    const { boxes, ms } = await detector.detect(canvas, w, h, { scoreThr: state.scoreThr, nmsThr: state.nmsThr });
    if (!state.running) return;
    state.lastBoxes = boxes;
    drawBoxes(boxes);
    const now = performance.now();
    if (lastFrameAt) fps = fps * 0.85 + (1000 / (now - lastFrameAt)) * 0.15;
    lastFrameAt = now;
    updateStats(boxes.length, ms, fps);
    updateInventory(boxes);
    announce(boxes);
  }
  requestAnimationFrame(loop);
}

$('#btn-flip').addEventListener('click', () => {
  state.facing = state.facing === 'environment' ? 'user' : 'environment';
  if (state.mode === 'camera') startCamera();
});

$('#btn-pause').addEventListener('click', () => {
  state.paused = !state.paused;
  $('#btn-pause').textContent = state.paused ? 'Resume' : 'Pause';
  lastFrameAt = 0;
  say(state.paused ? 'Time has stopped…' : 'The Eye of Sheik is watching again.');
});

// ---- image
const dropzone = $('#dropzone');
$('#file-input').addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (file) openImage(file);
  e.target.value = '';
});
['dragenter', 'dragover'].forEach((t) =>
  $('#viewport').addEventListener(t, (e) => {
    if (state.mode !== 'image') return;
    e.preventDefault();
    dropzone.hidden = false;
    dropzone.classList.add('is-over');
  }),
);
['dragleave', 'drop'].forEach((t) => dropzone.addEventListener(t, () => dropzone.classList.remove('is-over')));
$('#viewport').addEventListener('drop', (e) => {
  if (state.mode !== 'image') return;
  e.preventDefault();
  const file = [...(e.dataTransfer?.files || [])].find((f) => f.type.startsWith('image/'));
  if (file) openImage(file);
});
canvas.addEventListener('click', () => {
  if (state.mode === 'image') $('#file-input').click();
});

async function openImage(file) {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.src = url;
  try {
    await img.decode();
  } catch {
    say('That image could not be read.', 'hl-red');
    return;
  } finally {
    URL.revokeObjectURL(url);
  }
  state.image = img;
  dropzone.hidden = true;
  await loadModel();
  runOnImage();
}

let imageRun = 0;
async function runOnImage() {
  const img = state.image;
  const run = ++imageRun;
  const w = img.naturalWidth;
  const h = img.naturalHeight;
  canvas.width = w;
  canvas.height = h;
  ctx.drawImage(img, 0, 0);
  const { boxes, ms } = await detector.detect(img, w, h, { scoreThr: state.scoreThr, nmsThr: state.nmsThr });
  if (run !== imageRun) return;
  ctx.drawImage(img, 0, 0);
  state.lastBoxes = boxes;
  drawBoxes(boxes);
  updateStats(boxes.length, ms, null);
  updateInventory(boxes);
  announce(boxes, true);
}

// ---- save snapshot
$('#btn-snapshot').addEventListener('click', () => {
  canvas.toBlob((blob) => {
    if (!blob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sheik-detector-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    say('You saved a memory to your album!', 'hl-green');
  }, 'image/png');
});

// ---------------------------------------------------------------- drawing
// Palette inspired by Minish Cap kinstones / rupees
const PALETTE = ['#48e030', '#f8d038', '#60c8ff', '#ff5040', '#c070ff', '#ff9020', '#f8f8f8', '#30d0b0'];
const colorFor = (cls) => PALETTE[cls % PALETTE.length];

const heartImg = new Image();
heartImg.src = '/sprites/heart-0.png';

function drawBoxes(boxes) {
  const s = Math.max(1, Math.round(Math.min(canvas.width, canvas.height) / 240)); // one "GBA pixel"
  ctx.save();
  ctx.imageSmoothingEnabled = false;
  ctx.textBaseline = 'middle';
  ctx.font = `700 ${s * 8}px "Pixelify Sans", sans-serif`;
  for (const b of boxes) {
    const color = colorFor(b.cls);
    const x = Math.round(b.x1);
    const y = Math.round(b.y1);
    const w = Math.round(b.x2 - b.x1);
    const h = Math.round(b.y2 - b.y1);

    // Double frame: dark outline + color, with menu-cursor style corners
    ctx.lineWidth = s * 3;
    ctx.strokeStyle = '#101030';
    ctx.strokeRect(x, y, w, h);
    ctx.lineWidth = s;
    ctx.strokeStyle = color;
    ctx.strokeRect(x, y, w, h);
    const c = Math.min(w, h, s * 10) | 0;
    ctx.fillStyle = color;
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
      ctx.fillRect(cx - (dx < 0 ? s * 2 : 0), cy - (dy < 0 ? c : 0), s * 2, c);
      ctx.fillRect(cx - (dx < 0 ? c : 0), cy - (dy < 0 ? s * 2 : 0), c, s * 2);
    }

    // Label styled like a Minish Cap text box
    const text = `${b.label} ${Math.round(b.score * 100)}%`;
    const tw = Math.ceil(ctx.measureText(text).width);
    const th = s * 12;
    const lx = Math.min(Math.max(0, x), canvas.width - tw - s * 16);
    const ly = y - th - s * 2 >= 0 ? y - th - s * 2 : y + s * 2;
    ctx.fillStyle = '#000030';
    ctx.fillRect(lx, ly, tw + s * 16, th);
    ctx.fillStyle = '#f8f8f8';
    ctx.fillRect(lx, ly, tw + s * 16, s);
    ctx.fillRect(lx, ly + th - s, tw + s * 16, s);
    ctx.fillRect(lx, ly, s, th);
    ctx.fillRect(lx + tw + s * 16 - s, ly, s, th);
    if (heartImg.complete) ctx.drawImage(heartImg, lx + s * 3, ly + (th - s * 8) / 2, s * 9, s * 8);
    ctx.fillStyle = color;
    ctx.fillText(text, lx + s * 13, ly + th / 2 + s * 0.5);
  }
  ctx.restore();
}

// ---------------------------------------------------------------- HUD
function updateStats(count, ms, fpsValue) {
  $('#stat-count').textContent = count;
  $('#stat-ms').textContent = ms.toFixed(0);
  $('#stat-fps').textContent = fpsValue ? fpsValue.toFixed(1) : '–';
}

let lastInventoryKey = '';
function updateInventory(boxes) {
  const counts = new Map();
  for (const b of boxes) {
    if (!counts.has(b.cls)) counts.set(b.cls, { label: b.label, n: 0 });
    counts.get(b.cls).n++;
  }
  const entries = [...counts.entries()].sort((a, b) => b[1].n - a[1].n);
  const key = entries.map(([c, v]) => `${c}:${v.n}`).join('|');
  if (key === lastInventoryKey) return;
  lastInventoryKey = key;
  const list = $('#inventory-list');
  list.innerHTML = '';
  for (const [cls, { label, n }] of entries) {
    const li = document.createElement('li');
    li.innerHTML = `<img src="/sprites/item-${cls % 32}.png" alt="" /><span class="name"></span><span class="qty">×${n}</span>`;
    li.querySelector('.name').textContent = label;
    li.querySelector('.name').style.color = colorFor(cls);
    list.append(li);
  }
  $('#inventory-empty').hidden = entries.length > 0;
}

// Text box with typewriter effect
let typing = null;
let currentMessage = '';
function say(text, cls = '') {
  if (text === currentMessage) return;
  currentMessage = text;
  const el = $('#message');
  el.className = cls;
  clearInterval(typing);
  let i = 0;
  el.textContent = '';
  typing = setInterval(() => {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) clearInterval(typing);
  }, 22);
}

let lastAnnounce = 0;
function announce(boxes, force = false) {
  const now = performance.now();
  if (!force && now - lastAnnounce < 2500) return;
  lastAnnounce = now;
  if (!boxes.length) {
    say(force ? 'Nothing in sight… not even a Minish.' : 'Nothing here… keep exploring.');
    return;
  }
  const top = boxes.reduce((a, b) => (b.score > a.score ? b : a));
  const n = boxes.length;
  say(`You found ${n} ${n === 1 ? 'item' : 'items'}! Clearest one: ${top.label}.`, 'hl-green');
}

// Quietly preload the model while the title screen is showing
if ('requestIdleCallback' in window) requestIdleCallback(() => loadModel().catch(() => {}));
