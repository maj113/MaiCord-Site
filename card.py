"""Draws the 1200x630 link preview cards as small palette PNGs: og.png with
the current release details, and one card per catalog page (name, kind,
summary and its preview picture).

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


def logo(draw, x, y, size, radius=53):
    """The app tile: a rounded square with the M stroke, from favicon.svg."""
    unit = size / 176
    draw.rounded_rectangle((x, y, x + size, y + size), radius=radius * unit, fill=ACCENT)
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


def touch_icon(path, size=180):
    """apple-touch-icon.png: the logo full-bleed, since iOS rounds the corners itself."""
    image = Image.new("RGB", (size * SCALE, size * SCALE), ACCENT)
    logo(ImageDraw.Draw(image), 0, 0, size * SCALE, radius=0)
    icon = palette(image.resize((size, size), Image.Resampling.BOX))
    data = io.BytesIO()
    icon.save(data, "PNG", optimize=True)
    with open(path, "wb") as f:
        f.write(oxipng.optimize_from_memory(data.getvalue(), level=6))


def fit(draw, text, face, width, lines):
    """`text` wrapped to `width`, at most `lines` lines; the last one ends in an ellipsis when text is cut."""
    wrapped = wrap(draw, text, face, width)
    if len(wrapped) <= lines:
        return wrapped
    last = wrapped[lines - 1]
    while last and draw.textlength(last + "…", font=face) > width:
        last = last[:-1].rstrip()
    return wrapped[:lines - 1] + [last + "…"]


def title_lines(draw, text, width):
    """The largest bold size, 76 down to 52 pixels, at which `text` fits two lines; the size and the lines."""
    for size in range(76, 52, -4):
        face = font(700, size)
        lines = wrap(draw, text, face, width)
        if len(lines) <= 2 and all(draw.textlength(line, font=face) <= width for line in lines):
            return face, size, lines
    face = font(700, 52)
    return face, 52, fit(draw, text, face, width, 2)


def render_item(path, kind, name, summary, details, preview=None):
    """The link preview card of one catalog page (1200x630, PNG): the kind, name, summary and a details
    line, with the item's preview picture at the right (`preview`: its PNG bytes) or, when it has none
    (plugins), a tile with its initial."""
    s = SCALE
    image = Image.new("RGB", (WIDTH * s, HEIGHT * s), BACKGROUND)
    draw = ImageDraw.Draw(image)
    left, top = 72 * s, 56 * s
    right = (WIDTH - 72) * s
    column = (528 if preview else 640) * s  # the text column's width
    logo(draw, left, top, 44 * s, radius=13)
    draw.text((left + 60 * s, top + 22 * s), "MaiCord", font=font(700, 28), fill=TEXT, anchor="lm")

    pill = font(600, 20)
    label = kind.upper()
    pill_width = round(draw.textlength(label, font=pill)) + 32 * s
    face, size, lines = title_lines(draw, name, column)
    step = round(size * 1.12) * s
    body = font(400, 28)
    rows = fit(draw, summary, body, column, 4 if len(lines) < 2 else 3)
    block = 38 * s + 26 * s + step * len(lines) + 12 * s + 40 * s * len(rows)
    # Centred between the header (ends at 100) and the details line (starts at 556).
    y = (100 + 556) * s // 2 - block // 2
    draw.rounded_rectangle((left, y, left + pill_width, y + 38 * s), radius=19 * s, fill=ACCENT)
    draw.text((left + pill_width // 2, y + 19 * s), label, font=pill, fill=(255, 255, 255), anchor="mm")
    y += 38 * s + 26 * s
    for line in lines:
        draw.text((left, y + step // 2), line, font=face, fill=TEXT, anchor="lm")
        y += step
    y += 12 * s
    for line in rows:
        draw.text((left, y + 20 * s), line, font=body, fill=MUTED, anchor="lm")
        y += 40 * s
    small = font(400, 24)
    draw.text((left, (HEIGHT - 52) * s), fit(draw, details, small, right - left, 1)[0], font=small, fill=MUTED, anchor="lm")
    draw.rectangle((0, (HEIGHT - 10) * s, WIDTH * s, HEIGHT * s), fill=ACCENT)

    if not preview:
        side = 240 * s
        x, y = right - side, (HEIGHT * s - side) // 2 - 16 * s
        draw.rounded_rectangle((x, y, x + side, y + side), radius=56 * s, fill=(38, 38, 43), outline=(64, 64, 72), width=2 * s)
        draw.text((x + side // 2, y + side // 2 + 6 * s), name[:1].upper(), font=font(700, 150),
                  fill=(150, 160, 255), anchor="mm")
    card = image.resize((WIDTH, HEIGHT), Image.Resampling.BOX)

    if preview:
        picture = Image.open(io.BytesIO(preview)).convert("RGB")
        width = 528
        height = round(picture.height * width / picture.width)
        picture = picture.resize((width, height), Image.Resampling.LANCZOS)
        x, y = WIDTH - 72 - width, (HEIGHT - 10 - height) // 2 + 8
        mask = Image.new("L", (width * s, height * s), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width * s - 1, height * s - 1), radius=14 * s, fill=255)
        mask = mask.resize((width, height), Image.Resampling.BOX)
        outline = Image.new("L", (width * s, height * s), 0)
        ImageDraw.Draw(outline).rounded_rectangle((0, 0, width * s - 1, height * s - 1), radius=14 * s, outline=255, width=s)
        outline = outline.resize((width, height), Image.Resampling.BOX)
        card.paste(picture, (x, y), mask)
        card.paste((70, 70, 78), (x, y), outline)
        # Pictures are photographic: 256 adaptive colours, no dithering, keep the card near 100 KB.
        card = card.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    else:
        card = palette(card)
    data = io.BytesIO()
    card.save(data, "PNG", optimize=True)
    with open(path, "wb") as f:
        f.write(oxipng.optimize_from_memory(data.getvalue(), level=6))
