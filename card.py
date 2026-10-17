"""Draws the 1200x630 link preview card (og.png) with the current release
details, as a small palette PNG.

Drawn directly with Pillow and the bundled Inter fonts rather than screenshot
from a browser, so the output depends only on the inputs, not on whichever
fonts or browser a machine has.
"""
import io
import math
import os

import oxipng
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

WIDTH, HEIGHT = 1200, 630
SCALE = 4  # drawn large, then downsampled for smooth edges
BACKGROUND = (26, 26, 30)
TEXT = (242, 244, 247)
MUTED = (181, 186, 193)
ACCENT = (88, 101, 242)
TAGLINE = "A lightweight, native Discord client for Windows"
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# The card uses five colours; everything else is antialiased edges. The
# palette is the smallest that stays within this PSNR of the full-colour
# drawing, the usual threshold below which differences aren't visible.
MINIMUM_PSNR = 40.0
MAXIMUM_COLOURS = 64


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONTS, f"inter-latin-{weight}-normal.woff2"), size * SCALE)


def wrap(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=face) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + [line]


def logo(draw, x, y, size):
    """The app tile: a rounded square with the M stroke, from favicon.svg."""
    unit = size / 176
    draw.rounded_rectangle((x, y, x + size, y + size), radius=53 * unit, fill=ACCENT)
    points = [(x + px * unit, y + py * unit)
              for px, py in ((49.3, 125), (49.3, 54.6), (88, 96.8), (126.7, 54.6), (126.7, 125))]
    stroke = 25 * unit
    draw.line(points, fill=(255, 255, 255), width=round(stroke), joint="curve")
    for px, py in (points[0], points[-1]):  # round caps
        draw.ellipse((px - stroke / 2, py - stroke / 2, px + stroke / 2, py + stroke / 2), fill=(255, 255, 255))


def psnr(a, b):
    mse = sum(rms * rms for rms in ImageStat.Stat(ImageChops.difference(a, b)).rms) / 3
    return math.inf if mse == 0 else 10 * math.log10(255 * 255 / mse)


def palette(card):
    """The smallest undithered palette that keeps the card visually intact."""
    for colours in range(4, MAXIMUM_COLOURS + 1):
        reduced = card.quantize(colors=colours, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
        if colours == MAXIMUM_COLOURS or psnr(reduced.convert("RGB"), card) >= MINIMUM_PSNR:
            return reduced


def render(details, path):
    """details: the muted line under the tagline, e.g. "v0.3.1 · 5.6 MB"."""
    s = SCALE
    image = Image.new("RGB", (WIDTH * s, HEIGHT * s), BACKGROUND)
    draw = ImageDraw.Draw(image)
    name, tagline, small = font(700, 84), font(600, 44), font(400, 28)

    tile, left = 112 * s, 96 * s
    lines = wrap(draw, TAGLINE, tagline, 900 * s)
    line_height = round(44 * 1.2) * s
    block = tile + 40 * s + line_height * len(lines) + 28 * s + 34 * s
    top = (HEIGHT * s - block) // 2

    logo(draw, left, top, tile)
    draw.text((left + tile + 28 * s, top + tile // 2), "MaiCord", font=name, fill=TEXT, anchor="lm")
    y = top + tile + 40 * s
    for line in lines:
        draw.text((left, y + line_height // 2), line, font=tagline, fill=TEXT, anchor="lm")
        y += line_height
    draw.text((left, y + 28 * s + 17 * s), details, font=small, fill=MUTED, anchor="lm")
    draw.rectangle((0, (HEIGHT - 10) * s, WIDTH * s, HEIGHT * s), fill=ACCENT)

    # Area averaging gives clean antialiasing; Lanczos rings, which costs bytes.
    card = image.resize((WIDTH, HEIGHT), Image.Resampling.BOX)
    # About a dozen colours suffice; with oxipng the card is about 9 KB (44 KB
    # as an RGB PNG).
    card = palette(card)
    data = io.BytesIO()
    card.save(data, "PNG", optimize=True)
    with open(path, "wb") as f:
        f.write(oxipng.optimize_from_memory(data.getvalue(), level=6))
