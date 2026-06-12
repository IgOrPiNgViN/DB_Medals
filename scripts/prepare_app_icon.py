#!/usr/bin/env python3
"""i.webp / i.png -> client/resources/app_icon.ico + app_icon.png (без белого фона)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_CANDIDATES = [
    ROOT / "i.webp",
    ROOT / "i.png",
    ROOT / "i.jpg",
    ROOT / "app_icon.png",
    ROOT / "602067b9c2da5dbd679f777a47f45df8.jpg",
]
OUT_DIR = ROOT / "client" / "resources"
OUT_ICO = OUT_DIR / "app_icon.ico"
OUT_PNG = OUT_DIR / "app_icon.png"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _is_background_pixel(r: int, g: int, b: int, *, white_min: int, max_channel_diff: int) -> bool:
    """Почти белый нейтральный пиксель (не золотой/красный блик)."""
    if r < white_min or g < white_min or b < white_min:
        return False
    return max(r, g, b) - min(r, g, b) <= max_channel_diff


def _remove_white_background(img, *, white_min: int = 245, max_channel_diff: int = 20, soft: int = 10):
    """Убирает только фон, связанный с краями изображения (flood fill)."""
    from collections import deque

    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    bg = [[False] * w for _ in range(h)]
    queue: deque[tuple[int, int]] = deque()

    def try_seed(x: int, y: int) -> None:
        if x < 0 or x >= w or y < 0 or y >= h or bg[y][x]:
            return
        r, g, b, a = px[x, y]
        if a == 0 or _is_background_pixel(r, g, b, white_min=white_min, max_channel_diff=max_channel_diff):
            bg[y][x] = True
            queue.append((x, y))

    for x in range(w):
        try_seed(x, 0)
        try_seed(x, h - 1)
    for y in range(h):
        try_seed(0, y)
        try_seed(w - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            try_seed(nx, ny)

    for y in range(h):
        for x in range(w):
            if not bg[y][x]:
                continue
            r, g, b, _a = px[x, y]
            px[x, y] = (r, g, b, 0)

    # мягкий край только у пикселей, соседних с удалённым фоном
    for y in range(h):
        for x in range(w):
            if bg[y][x]:
                continue
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            neighbors_bg = any(
                0 <= nx < w and 0 <= ny < h and bg[ny][nx]
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            )
            if not neighbors_bg:
                continue
            brightness = max(r, g, b)
            if brightness >= white_min - soft and max(r, g, b) - min(r, g, b) <= max_channel_diff + 8:
                fade = max(0, min(255, int((white_min - brightness + soft) * 255 / soft)))
                px[x, y] = (r, g, b, min(a, fade))
    return rgba


def main() -> int:
    src = next((p for p in SRC_CANDIDATES if p.is_file()), None)
    if src is None:
        print("Иконка не найдена. Положите i.webp или i.png в корень проекта.")
        return 1

    try:
        from PIL import Image
    except ImportError:
        print("Установите: pip install Pillow")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = Image.open(src)
    img = _remove_white_background(raw)
    master = img.resize((256, 256), Image.Resampling.LANCZOS)
    master.save(OUT_PNG, format="PNG")
    icons = [master.resize((s, s), Image.Resampling.LANCZOS) for s in SIZES]
    icons[0].save(OUT_ICO, format="ICO", sizes=[(s, s) for s in SIZES], append_images=icons[1:])
    print(f"OK: {OUT_ICO}")
    print(f"OK: {OUT_PNG}  (из {src.name}, белый фон убран)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
