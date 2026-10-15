"""Cuts the sprites out of the Minish Cap sheets (assets-src/sheets) into public/sprites.

Usage:  python tools/extract_assets.py

Each sheet's background is made transparent with a flood fill from the crop's edges,
so same-colored pixels inside a sprite are not punched out.
"""

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "assets-src" / "sheets"
OUT = ROOT / "public" / "sprites"


def load(name):
    return Image.open(SHEETS / name).convert("RGBA")


def key_out(img, color, tol=0):
    """Makes the background color connected to the image edges transparent."""
    img = img.copy()
    px = img.load()
    w, h = img.size

    def is_bg(p):
        return p[3] and all(abs(p[i] - color[i]) <= tol for i in range(3))

    queue = deque()
    for x in range(w):
        queue.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        queue.extend([(0, y), (w - 1, y)])
    seen = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        if not is_bg(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return img


def key_all(img, color, tol=0):
    """Makes every pixel of the given color transparent (for light overlays)."""
    img = img.copy()
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if all(abs(p[i] - color[i]) <= tol for i in range(3)):
                px[x, y] = (0, 0, 0, 0)
    return img


def crop(sheet, x, y, w, h):
    return sheet.crop((x, y, x + w, y + h))


def three_slice(img, left, right, mid_x):
    """Rebuilds a text-free banner/button: left cap + repeated middle column + right cap."""
    w, h = img.size
    out = Image.new("RGBA", (w, h))
    out.paste(img.crop((0, 0, left, h)), (0, 0))
    out.paste(img.crop((w - right, 0, w, h)), (w - right, 0))
    col = img.crop((mid_x, 0, mid_x + 1, h))
    for x in range(left, w - right):
        out.paste(col, (x, 0))
    return out


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, optimize=True)
    print(f"  {name:28s} {img.size[0]}x{img.size[1]}")


def main():
    fs = load("file-select.png")  # lilac background (167,167,227)
    bg = load("backgrounds-overlays.png")
    pm = load("pause-menu.png")  # background (192,192,255)
    ts = load("title-screen.png")
    lila, lila2, white = (167, 167, 227), (192, 192, 255), (255, 255, 255)

    # --- Backgrounds ---
    save(crop(ts, 251, 24, 240, 160), "bg-title.png")
    for i in range(4):
        save(crop(fs, 2 + (i % 2) * 241, 668 + (i // 2) * 161, 240, 160), f"bg-fileselect-{i}.png")
    save(crop(bg, 577, 414, 240, 168), "bg-beanstalk.png")
    save(crop(bg, 297, 49, 256, 256), "bg-cloudtops.png")
    save(crop(pm, 316, 319, 240, 160), "bg-pattern.png")

    # --- Overlays (Minish Woods light rays, 4 frames) ---
    for i, y in enumerate((24, 187, 350, 513)):
        frame = crop(ts, 6, y, 240, 160)
        sky = frame.getpixel((2, 2))[:3]
        save(key_all(frame, sky, tol=6), f"rays-{i}.png")
    clouds = crop(bg, 567, 1241, 256, 256)
    save(key_all(clouds, clouds.getpixel((2, 2))[:3], tol=4), "overlay-clouds.png")
    fog = crop(bg, 22, 1240, 256, 256)
    save(key_all(fog, fog.getpixel((0, 0))[:3], tol=10), "overlay-fog.png")

    # --- Logos / titles ---
    zelda = crop(ts, 280, 439, 168, 81)
    save(key_out(zelda, zelda.getpixel((0, 0))[:3], tol=8), "logo-zelda.png")
    save(key_out(crop(bg, 371, 1006, 248, 128), white, tol=8), "logo-minishcap.png")
    press = crop(ts, 381, 189, 89, 18)
    save(key_out(press, press.getpixel((0, 0))[:3], tol=8), "press-start.png")

    # --- Panels and buttons (file-select screen) ---
    save(key_out(crop(fs, 81, 32, 108, 76), lila), "frame-dark.png")
    save(key_out(crop(fs, 255, 188, 228, 124), lila), "frame-dark-big.png")
    save(key_out(crop(fs, 2, 32, 69, 26), lila), "btn-green-active.png")
    save(key_out(crop(fs, 2, 62, 69, 26), lila), "btn-green.png")
    save(key_out(crop(fs, 255, 122, 69, 26), lila), "btn-orange.png")
    banner_blue = key_out(crop(fs, 255, 92, 220, 22), lila)
    save(three_slice(banner_blue, 24, 24, 30), "banner-blue.png")
    banner_red = key_out(crop(fs, 255, 2, 220, 22), lila)
    save(three_slice(banner_red, 24, 24, 30), "banner-red.png")
    save(key_out(crop(fs, 51, 302, 24, 14), lila), "toggle.png")
    for i in range(7):
        save(key_out(crop(fs, 2 + i * 17, 116, 16, 16), lila), f"gem-{i}.png")
    for i in range(5):
        save(key_out(crop(fs, 2 + i * 11, 156, 9, 8), lila), f"heart-{i}.png")
    links = [2, 23, 44, 65, 86, 107, 128, 149, 170, 191]
    for i, x in enumerate(links):
        save(key_out(crop(fs, x, 170, 18, 30), lila), f"link-walk-{i}.png")
        save(key_out(crop(fs, x, 201, 18, 30), lila), f"link-green-{i}.png")

    # --- Pause menu: stone frame, text bar, icons ---
    save(key_out(crop(pm, 6, 57, 208, 133), lila2), "frame-stone.png")
    save(key_out(crop(pm, 6, 375, 224, 154), lila2), "frame-map.png")
    save(key_out(crop(pm, 2, 278, 216, 22), lila2), "textbar.png")
    save(key_out(crop(pm, 7, 29, 21, 21), lila2), "tab-l.png")
    save(key_out(crop(pm, 30, 29, 21, 21), lila2), "tab-r.png")
    save(key_out(crop(pm, 219, 87, 26, 19), lila2), "glow.png")
    for i, x in enumerate((418, 446, 474, 502)):
        save(key_out(crop(pm, x, 201, 26, 24), lila2), f"heart-container-{i}.png")
    items = [
        (6, 196, 14, 14), (22, 195, 15, 15), (39, 195, 15, 15), (56, 195, 15, 15),
        (73, 194, 16, 16), (93, 195, 16, 15), (113, 196, 13, 14), (6, 216, 12, 14),
        (21, 216, 14, 14), (39, 215, 12, 15), (55, 214, 14, 16), (73, 214, 12, 16),
        (88, 215, 12, 15), (6, 238, 14, 13), (24, 237, 14, 14), (42, 239, 16, 12),
        (62, 237, 14, 14), (79, 234, 17, 17), (320, 200, 14, 24), (336, 200, 24, 25),
        (396, 194, 18, 31), (320, 234, 16, 16), (338, 234, 16, 16), (356, 234, 16, 16),
        (374, 234, 16, 16), (320, 254, 16, 16), (340, 256, 14, 14), (358, 255, 14, 15),
        (376, 255, 14, 15), (394, 255, 12, 15), (410, 255, 14, 15), (396, 229, 17, 21),
    ]
    for i, (x, y, w, h) in enumerate(items):
        save(key_out(crop(pm, x, y, w, h), lila2), f"item-{i}.png")
    for i in range(13):
        save(key_out(crop(pm, 6 + i * 14, 257, 12, 15), lila2), f"bottle-{i}.png")


if __name__ == "__main__":
    main()
