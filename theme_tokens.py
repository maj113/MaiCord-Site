#!/usr/bin/env python3
"""Site colour tokens for each theme, computed with MaiCord's own theme maths.

Ports of the client sources (keep in sync when they change):
  include/maicord/ui/theme.hpp                  kDefaultTheme, kLightTheme, kAmoledTheme
  include/maicord/ui/background_theme.hpp       background_theme_defaults
  include/maicord/app/client_theme.hpp          client_theme_projection, preset palettes
  include/maicord/ui/background_color_math.hpp  linear/sRGB, HSL, OKLab, mix, anchors
  include/maicord/ui/background_presentation.hpp ui_background_tier_opacity (chat tier)
  src/ui/theme_styles.cpp                       ui_theme_contrast_ratio, ui_theme_gradient_emphasis
  src/ui/button.cpp                             gradient primary hover shade (.94)

build.py inserts css() into index.html; `python3 theme_tokens.py` prints the
CSS and a contrast table.
"""

# kDefaultTheme core palette (theme.hpp), RGB in 0..1.
DARK = {
    "base_lowest": (.0588, .0588, .0706), "base_lower": (.1020, .1020, .1176), "base_low": (.1333, .1333, .1451),
    "surface": (.1647, .1647, .1804), "surface_high": (.2078, .2078, .2275), "interactive": (.2667, .2667, .2941),
    "interactive_hover": (.3216, .3216, .3529), "accent": (.3451, .3961, .9490), "text_primary": (.9490, .9569, .9686),
    "avatar_placeholder": (.3804, .3882, .4196), "text_secondary": (.7098, .7294, .7569),
}
AMOLED = dict(DARK, base_lowest=(0, 0, 0), base_lower=(.02, .02, .025), base_low=(.035, .035, .045),
              surface=(.06, .06, .075), surface_high=(.105, .105, .125))
LIGHT = dict(DARK, base_lowest=(.91, .92, .95), base_lower=(.95, .96, .98), base_low=(.975, .98, .99),
             surface=(1, 1, 1), surface_high=(.93, .94, .97), interactive=(.85, .87, .91),
             interactive_hover=(.79, .81, .87), text_primary=(.11, .12, .15), text_secondary=(.36, .38, .43),
             avatar_placeholder=(.67, .69, .74))
# client_theme.hpp presets; background_theme_defaults: angle 120, intensity 40.
PALETTES = {"aurora": (0x6935b8, 0x164d80, 0x16836f), "sunset": (0x7a284b, 0xa65732, 0x362062),
            "ocean": (0x15335f, 0x167d89, 0x363269)}
INTENSITY = 40
ON_ACCENT = (1, 1, 1)
# Flat primary hover; the client has no flat counterpart for the site's button.
FLAT_ACCENT_HOVER = (0x47 / 255, 0x52 / 255, 0xc4 / 255)


def unit(v):
    return min(v, 1) if v >= 0 else 0


def root(value, degree):
    if value <= 0:
        return 0
    if value >= 1:
        return 1
    low, high = 0.0, 1.0
    for _ in range(32):
        middle = (low + high) * .5
        if middle ** degree < value:
            low = middle
        else:
            high = middle
    return (low + high) * .5


def linear(c):
    v = unit(c)
    if v <= .04045:
        return v / 12.92
    s = (v + .055) / 1.055
    return s * s * root(s * s, 5)


def srgb(c):
    if not c > 0:
        return 0
    if c >= 1:
        return 1
    if c <= .0031308:
        return 12.92 * c
    return 1.055 * root(c ** 5, 12) - .055


def luminance(c):
    return .2126 * linear(c[0]) + .7152 * linear(c[1]) + .0722 * linear(c[2])


def rgb24(v):
    return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255)


def hsl(c):
    r, g, b = (unit(x) for x in c)
    high, low = max(r, g, b), min(r, g, b)
    delta, lightness = high - low, (high + low) * .5
    if not delta:
        return [0, 0, lightness]
    saturation = delta / (high + low if lightness < .5 else 2 - high - low)
    hue = (g - b) / delta if r == high else 2 + (b - r) / delta if g == high else 4 + (r - g) / delta
    hue *= 60
    return [hue + 360 if hue < 0 else hue, saturation, lightness]


def from_hsl(h):
    hue, saturation, lightness = h[0], unit(h[1]), unit(h[2])
    if not saturation:
        return (lightness,) * 3
    hue = hue / 60 if 0 <= hue <= 360 else 0
    hue = 0 if hue == 6 else hue
    chroma = (1 - abs(lightness * 2 - 1)) * saturation
    sector = int(hue)
    fraction = hue - sector
    x = chroma * (1 - fraction if sector & 1 else fraction)
    m = lightness - chroma * .5
    r, g, b = [(chroma, x, 0), (x, chroma, 0), (0, chroma, x), (0, x, chroma), (x, 0, chroma)][sector] \
        if sector < 5 else (chroma, 0, x)
    return (r + m, g + m, b + m)


def oklab(c):
    r, g, b = linear(c[0]), linear(c[1]), linear(c[2])
    l = root(.4122214708 * r + .5363325363 * g + .0514459929 * b, 3)
    m = root(.2119034982 * r + .6806995451 * g + .1073969566 * b, 3)
    s = root(.0883024619 * r + .2817188376 * g + .6299787005 * b, 3)
    return (.2104542553 * l + .7936177850 * m - .0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + .4505937099 * s,
            .0259040371 * l + .7827717662 * m - .8086757660 * s)


def from_oklab(lab):
    L, a, b = lab
    l = (L + .3963377774 * a + .2158037573 * b) ** 3
    m = (L - .1055613458 * a - .0638541728 * b) ** 3
    s = (L - .0894841775 * a - 1.2914855480 * b) ** 3
    return (srgb(4.0767416621 * l - 3.3077115913 * m + .2309699292 * s),
            srgb(-1.2684380046 * l + 2.6097574011 * m - .3413193965 * s),
            srgb(-.0041960863 * l - .7034186147 * m + 1.7076147010 * s))


def mix(original, anchor, tint_percent):
    if not tint_percent > 0:
        return original
    share = min(tint_percent, 100) / (100 + min(tint_percent, 100))
    base = oklab(original)
    return from_oklab(tuple(x + (y - x) * share for x, y in zip(base, anchor)))


def anchors(stops, light):
    lum = [luminance(s) for s in stops]
    darkest, lightest = stops[lum.index(min(lum))], stops[lum.index(max(lum))]
    base = hsl(lightest if light else darkest)
    text = list(base)
    if base[1]:
        base[1] = 1
    base[2] = .9 if light else .05
    text_lightness = .05 - INTENSITY * .0005 if light else .9 + INTENSITY * .001
    text[2] = int(text_lightness * 100 + .500000001) / 100
    return from_hsl(base), from_hsl(text), (100 - .4 * INTENSITY if light else 30 - .2 * INTENSITY), \
        (30 if light else 40)


def composite(top, alpha, bottom):
    return tuple(t * alpha + b * (1 - alpha) for t, b in zip(top, bottom))


def contrast(fg, bg, alpha=1):
    x, y = luminance(composite(fg, alpha, bg)), luminance(bg)
    return (max(x, y) + .05) / (min(x, y) + .05)


def emphasis(stops, light, floating, primary):
    """ui_theme_gradient_emphasis: fill, text and outline."""
    best, hue = -1, None
    for stop in stops:
        lab = oklab(stop)
        squared = lab[1] ** 2 + lab[2] ** 2
        if squared > best:
            best, hue = squared, lab
    chroma = root(best, 2)
    target = min(max(chroma * 1.25, .09), .18)
    a, b = hue[1] / chroma * target, hue[2] / chroma * target
    text, fill = ON_ACCENT, None
    for step in range(21):
        fill = from_oklab((.74 - step * .02, a, b))
        if contrast(text, fill) >= 4.5:
            break
    else:
        fill = from_oklab((.5 if light else .62, a, b))
        white, black = (1, 1, 1), (0, 0, 0)
        text = white if contrast(white, fill) >= contrast(black, fill) else black
    for step in range(31):
        outline = from_oklab((.56 - step * .016 if light else .62 + step * .012, a, b))
        if contrast(outline, floating) >= 3 and contrast(outline, primary) >= 3:
            break
    return fill, text, outline


def chat_canvas_alpha(light):
    """ui_background_tier_opacity for the chat tier at INTENSITY."""
    multiplier = ((1000 - 7 * INTENSITY + 5) // 10) / 100
    return .95 * (.6 + .4 * multiplier) if light else .48 + .32 * multiplier


def readable_link(color, backgrounds):
    """The accent's hue, lightness stepped in OKLab until 4.5:1 on every backdrop.
    Site only: the client asks links for 3:1 (ui_theme_contrast_warnings)."""
    lab = oklab(color)
    dark = luminance(backgrounds[0]) < .18
    for step in range(60):
        candidate = from_oklab((lab[0] + (step if dark else -step) * .01, lab[1], lab[2]))
        if all(contrast(candidate, bg) >= 4.5 for bg in backgrounds):
            return candidate
    return candidate


def theme(name):
    """Resolved site tokens: (light, tokens, backdrop stops)."""
    light = name in ("light", "aurora-light")
    core = dict(LIGHT if light else AMOLED if name == "amoled" else DARK)
    palette = PALETTES.get(name.replace("-light", ""))
    stops = [rgb24(v) for v in palette] if palette else None
    if stops:
        base, text, base_percent, text_percent = anchors(stops, light)
        base, text = oklab(base), oklab(text)
        for key in ("base_lowest", "base_lower", "base_low", "surface", "surface_high", "interactive",
                    "interactive_hover", "avatar_placeholder"):
            core[key] = mix(core[key], base, base_percent)
        for key in ("text_primary", "text_secondary"):
            core[key] = mix(core[key], text, text_percent)
    # Site roles, as the flat site used them: page, cards, raised controls, borders.
    if light:
        tokens = {"bg": core["base_low"], "surface": core["surface"], "raised": core["base_lower"],
                  "line": core["interactive"]}
    else:
        tokens = {"bg": core["base_lowest"] if name == "amoled" else core["base_lower"],
                  "surface": core["base_low"], "raised": core["surface"], "line": core["surface_high"]}
    tokens.update(text=core["text_primary"], muted=core["text_secondary"])
    if stops:
        # Chat canvas: black (dark) or white (light) at the tier opacity over the gradient.
        canvas = chat_canvas_alpha(light)
        backdrop = [composite((1, 1, 1) if light else (0, 0, 0), canvas, s) for s in stops]
        fill, on_fill, outline = emphasis(stops, light, core["base_lower"], core["base_low"])
        tokens.update(accent=fill, on_accent=on_fill, accent_hover=tuple(c * .94 for c in fill), focus=outline)
    else:
        backdrop = [tokens["bg"]] * 3
        tokens.update(accent=core["accent"], on_accent=ON_ACCENT, accent_hover=FLAT_ACCENT_HOVER,
                      focus=core["accent"])
    tokens["link"] = readable_link(core["accent"], backdrop + [tokens["bg"], tokens["surface"]])
    return light, tokens, backdrop


THEMES = ("dark", "light", "amoled", "aurora", "sunset", "ocean", "aurora-light")
FLAT = ("dark", "light", "amoled")


def hexa(c):
    return "#" + "".join(f"{int(unit(x) * 255 + .5):02x}" for x in c)


def declarations(name):
    light, tokens, backdrop = theme(name)
    out = [f"color-scheme: {'light' if light else 'dark'};"]
    out += [f"--{k.replace('_', '-')}: {hexa(v)};" for k, v in tokens.items()]
    out += [f"--g{i + 1}: {hexa(c)};" for i, c in enumerate(backdrop)]
    out.append(f"--veil: {'100%' if name in FLAT else '74%'};")
    # Effect ink (background_fx.hlsl), as an RGB triplet for the CSS fallback stars.
    out.append(f"--ink: {'26 46 77' if light else '209 230 255'};")
    return " ".join(out)


def swatch(name):
    if name in PALETTES:
        return ", ".join(hexa(rgb24(v)) for v in PALETTES[name])
    if name == "aurora-light":
        return ", ".join(hexa(composite((1, 1, 1), .5, rgb24(v))) for v in PALETTES["aurora"])
    color = hexa(theme(name)[1]["bg"])
    return f"{color}, {color}"


def css():
    lines = ["/* Theme tokens: generated by theme_tokens.py from MaiCord's theme maths. Edit that file. */",
             f":root, :root[data-theme=aurora] {{ {declarations('aurora')} }}",
             f"@media (prefers-color-scheme: light) {{ :root:not([data-theme]) {{ {declarations('aurora-light')} }} }}"]
    lines += [f":root[data-theme={n}] {{ {declarations(n)} }}" for n in THEMES if n != "aurora"]
    lines += [f"[data-theme={n}] {{ --cur: {swatch(n)}; }}" for n in THEMES]
    return "\n".join(lines)


if __name__ == "__main__":
    print(css())
    print()
    for name in THEMES:
        light, t, backdrop = theme(name)
        grounds = backdrop + [composite(backdrop[i], .5, backdrop[i + 1]) for i in range(2)] + [t["bg"]]
        surfaces = [composite(t["surface"], .74 if name not in FLAT else 1, g) for g in grounds]
        row = {k: min(contrast(t[k], g) for g in grounds + surfaces) for k in ("text", "muted", "link")}
        row["on_accent"] = contrast(t["on_accent"], t["accent"])
        print(f"{name:13s}", "  ".join(f"{k} {v:.2f}" for k, v in row.items()))
