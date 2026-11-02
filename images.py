"""AVIF variants of the catalog's PNG previews and loops, made at build time.

The catalog ships PNG (a 1440x900 theme preview is about 220 KB, an effect loop
about 1 MB). The pages offer AVIF at the sizes they display, 1x and 2x, and keep
the PNG as the fallback for browsers without AVIF. The variants are derived from
the PNG after its SHA-256 and size were checked against the index (catalog.py),
and this module checks them again, so no variant can come from bytes the index
did not sign. The output is deterministic: libavif is run with fixed settings.
"""
import io

from PIL import Image, ImageSequence, features

import card
import catalog

# Widths of the stills: a card (350 CSS pixels) at 1x and 2x, then the detail page's
# column (about 700 CSS pixels) at 2x. Nothing is made wider than the original.
WIDTHS = (360, 720, 1440)
QUALITY = 55
# Full chroma resolution: previews are UI screenshots and thin coloured lines, where 4:2:0 smears the colour.
SUBSAMPLING = "4:4:4"
SPEED = 6
MAX_FRAMES = 600  # 10 seconds at 60 frames per second, the index's limit
# A loop is encoded at the first quality that stays within MIN_LOOP_PSNR dB of the PNG on three probe frames
# (a grain or noise effect needs a high one) and is kept only if it is under MAX_LOOP_SHARE of the PNG's size;
# otherwise the page keeps the PNG.
LOOP_QUALITIES = (50, 70, 90)
MIN_LOOP_PSNR = 38.0
MAX_LOOP_SHARE = 0.5


def require():
    if not features.check("avif"):
        raise SystemExit("This Pillow build cannot write AVIF (requirements.txt pins one that can).")


def _open(image, where):
    """The decoded PNG of `image` ({"data", "sha256", "bytes", "width", "height"}), after checking
    the bytes against the digest and the pixels against the size the index declares."""
    catalog.check(image["data"], image, where)
    picture = Image.open(io.BytesIO(image["data"]))
    if picture.format != "PNG" or picture.size != (image["width"], image["height"]):
        raise catalog.CatalogError(f"{where}: not a PNG of the size the index lists")
    return picture


def widths(width):
    """The variant widths for an original `width` pixels wide, ascending, ending at the largest that fits."""
    return [w for w in WIDTHS if w < width] + [min(width, WIDTHS[-1])]


def stills(image, where):
    """[(width, AVIF bytes)] for a PNG preview."""
    picture = _open(image, where)
    picture = picture.convert("RGBA" if "A" in picture.getbands() else "RGB")
    out = []
    for width in widths(image["width"]):
        height = max(1, round(image["height"] * width / image["width"]))
        scaled = picture if width == picture.width else picture.resize((width, height), Image.Resampling.LANCZOS)
        data = io.BytesIO()
        scaled.save(data, "AVIF", quality=QUALITY, speed=SPEED, subsampling=SUBSAMPLING)
        out.append((width, data.getvalue()))
    return out


def loop(image, where):
    """AVIF bytes of an APNG loop, at its own size and frame timing, or None when no quality is both faithful
    and small enough (see LOOP_QUALITIES)."""
    picture = _open(image, where)
    if getattr(picture, "n_frames", 1) > MAX_FRAMES:
        raise catalog.CatalogError(f"{where}: more than {MAX_FRAMES} frames")
    frames, durations = [], []
    for frame in ImageSequence.Iterator(picture):
        durations.append(max(1, round(frame.info.get("duration", 1000 / image["fps"]))))
        frames.append(frame.convert("RGBA" if "A" in frame.getbands() else "RGB"))
    probes = sorted({0, len(frames) // 2, len(frames) - 1})
    for quality in LOOP_QUALITIES:
        data = io.BytesIO()
        frames[0].save(data, "AVIF", save_all=True, append_images=frames[1:], duration=durations, quality=quality,
                       speed=SPEED, subsampling=SUBSAMPLING)
        if len(data.getvalue()) > MAX_LOOP_SHARE * image["bytes"]:
            return None  # a higher quality only grows
        decoded = Image.open(io.BytesIO(data.getvalue()))
        worst = min(card.psnr(_frame(decoded, i), frames[i].convert("RGB")) for i in probes)
        if worst >= MIN_LOOP_PSNR:
            return data.getvalue()
    return None


def _frame(picture, index):
    picture.seek(index)
    return picture.convert("RGB")
