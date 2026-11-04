"""Renders the plugin, theme and effect pages from a loaded catalog
(catalog.py): a listing per kind with search, category filters and sort, a
detail page per item with its own link preview card, the developer guides, the
404 page and the catalog's part of the home page. The pages are plain HTML that
lists everything; the one inline script (catalog-assets/) only adds the theme
picker, the backdrop, the filters, the copy button and the install hint.
CATALOG.md describes the data the pages read."""
import datetime
import html
import json
import os

import card as social
import catalog
import guide
import images
from markup import inline, markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "catalog-assets")
SITE = "https://maicord.com/"
# Directories under /plugins/, /themes/ and /effects/ that belong to the site, so no item may use them as a slug.
RESERVED_SLUGS = ("develop",)
KINDS = {
    "plugin": {
        "path": "plugins", "title": "Plugins", "noun": "plugin",
        "lead": "Native plugins that add features to MaiCord. Every plugin here is reviewed, built from its public "
                "source and signed, and you approve what it may do before it runs.",
        "sorts": (("name", "Name"), ("new", "Newest"), ("access", "Least access")),
        "build": ("Write a plugin", "The SDK guide takes you from an empty folder to a plugin running in MaiCord: "
                  "the maicord-plugin tool, permissions, Developer Mode and sending it to this catalog.",
                  "Read the plugin guide", "develop/"),
    },
    "theme": {
        "path": "themes", "title": "Themes", "noun": "theme",
        "lead": "Colours, type and motion for MaiCord's interface. A theme is plain data and runs no code.",
        "sorts": (("name", "Name"), ("new", "Newest")),
        "build": ("Make a theme", "A theme is one small document. Send yours to the catalog on GitHub and it shows up here "
                  "and in MaiCord's Themes page.", "Open the catalog repository", "https://github.com/maj113/MaiCord-plugins"),
    },
    "effect": {
        "path": "effects", "title": "Effects", "noun": "effect",
        "lead": "Animated backgrounds drawn by your GPU. An effect is a small shader with a few knobs, and it runs "
                "no code on your CPU.",
        "sorts": (("name", "Name"), ("new", "Newest"), ("cost", "Lightest")),
        "build": ("Write an effect", "An effect is one HLSL function. The guide covers the quick start, the shader "
                  "interface, knobs and sending it to this catalog.", "Read the effect guide", "develop/"),
    },
}

# The developer guides: /plugins/develop/ and /effects/develop/, rendered from guides/ (sync_guides.py). `jump`
# links the guide's sections that answer the first questions; `links` points the guides' mentions of each other
# at these pages.
GUIDES = {
    "plugin": {
        "file": "plugin-sdk.md", "title": "Plugin developer guide",
        "lead": "Write a native plugin for MaiCord in C++, test it live with Developer Mode, and publish it to the "
                "official catalog.",
        "jump": (("quick-start", "Quick start"), ("a-plugin-in-c", "Writing a plugin"), ("permissions", "Permissions"),
                 ("developing", "Testing with Developer Mode"), ("publishing-to-the-catalog", "Submit to the catalog")),
        "links": {"samples/effects/README.md": "../../effects/develop/"},
    },
    "effect": {
        "file": "effects.md", "title": "Effect developer guide",
        "lead": "Write an animated background for MaiCord as one HLSL function, preview it live, and publish it to the "
                "official catalog.",
        "jump": (("quick-start", "Quick start"), ("how-an-effect-draws", "How an effect draws"), ("the-shader", "The shader"),
                 ("building", "Building"), ("publishing-to-the-catalog", "Submit to the catalog")),
        "links": {"include/maicord/sdk/README.md": "../../plugins/develop/"},
    },
}

# Permission names are the MC_PERM_* names in lower case (include/maicord/sdk/plugin_abi.h). The catalog lists the
# full effective set, including what hooks and buttons imply. The label is the consent text's gist and the level is
# how much the permission exposes: 0 stays on your PC, 1 reads or changes parts of your Discord data, 2 acts for you,
# reaches the network or restores logged messages. A plugin's overall level is in access().
PERMISSIONS = {
    "message_send": ("Changes your messages before they are sent", 1),
    "read_messages": ("Reads the messages you receive", 1),
    "message_history": ("Keeps deleted and edited messages visible", 1),
    "read_activity": ("Sees presence, voice, servers, members and friends", 1),
    "network": ("Connects to the hosts listed below", 2),
    "composer": ("Reads and changes the message box, starts replies and edits", 1),
    "act_messages": ("Sends, edits and deletes your messages, reacts and marks read", 2),
    "act_presence": ("Sets your custom status and activity", 1),
    "clipboard": ("Copies text to the clipboard", 0),
    "automated_actions": ("Acts without you clicking (not allowed in this catalog)", 2),
    "persistent_log": ("Restores kept messages from its own log (not allowed in this catalog)", 2),
}
LEVELS = ("Low", "Medium", "High")
COSTS = {"light": "Light", "medium": "Medium", "heavy": "Heavy"}
COST_NOTES = {"light": "easy on any GPU", "medium": "fine on most GPUs", "heavy": "best on a dedicated GPU"}
BLENDS = {"normal": "Normal", "screen": "Screen", "add": "Add"}
BASES = {"dark": "Dark", "light": "Light", "amoled": "AMOLED"}
KNOB_TYPES = {"float": "Slider", "int": "Whole-number slider", "toggle": "Switch", "color": "Colour", "choice": "Choice"}
USES = {"noise": "noise texture", "glyphs": "glyph grid", "blue_noise": "blue-noise texture",
        "pointer": "pointer position (optional)", "texture0": "bundled texture", "texture1": "second bundled texture"}
THEMES = (("dark", "Dark"), ("light", "Light"), ("amoled", "AMOLED"), ("aurora", "Aurora"), ("sunset", "Sunset"),
          ("ocean", "Ocean"), ("aurora-light", "Aurora light"))
LOGO = ('<svg class="logo" viewBox="0 0 176 176" aria-hidden="true"><rect width="176" height="176" rx="53" fill="#5865f2"/>'
        '<path d="M49.3 125V54.6L88 96.8l38.7-42.2V125" fill="none" stroke="#fff" stroke-width="25" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>')

esc = html.escape


def asset(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as f:
        return f.read()


def date_text(stamp):
    day = datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc)
    return f"{day:%b} {day.day}, {day.year}"


def bytes_text(size):
    return f"{size} B" if size < 1024 else f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"


# Category slugs that are acronyms or proper names, shown in their usual form (the catalog data keeps its slugs).
ACRONYMS = {"oled": "OLED", "amoled": "AMOLED", "ui": "UI", "ux": "UX", "rpc": "RPC", "url": "URL", "urls": "URLs",
            "dm": "DM", "dms": "DMs", "api": "API", "gpu": "GPU", "cpu": "CPU", "nsfw": "NSFW", "ascii": "ASCII",
            "css": "CSS", "hdr": "HDR", "tts": "TTS", "ai": "AI", "gif": "GIF", "gifs": "GIFs", "vc": "VC",
            "wcag": "WCAG", "fps": "FPS", "crt": "CRT", "vhs": "VHS", "rgb": "RGB", "id": "ID", "ids": "IDs"}


def title_case(slug):
    """A category slug as a label: `chat-bar` is "Chat bar", `oled` is "OLED"."""
    text = " ".join(ACRONYMS.get(w, w) for w in slug.split("-"))
    return text[:1].upper() + text[1:]


def access(item):
    """The plugin's overall level: its highest permission level, and High whenever the network is combined with
    any other permission, since what it reads could then leave the PC."""
    perms = item["versions"][0]["permissions"]
    level = max((PERMISSIONS[p][1] for p in perms), default=0)
    if "network" in perms and len(perms) > 1:
        level = 2
    return level


def authors_html(item, links=True):
    out = []
    for author in item["authors"]:
        name = esc(author["name"])
        out.append(f'<a href="https://github.com/{esc(author["github"])}">{name}</a>' if links and author["github"] else name)
    return ", ".join(out)


def license_html(identifier):
    if identifier.startswith("LicenseRef-"):
        return esc(identifier)
    return f'<a href="https://spdx.org/licenses/{esc(identifier)}.html">{esc(identifier)}</a>'


def card_details(item):
    """The line under the summary on an item's link preview card."""
    kind = item["kind"]
    extra = (f"{LEVELS[access(item)]} access" if kind == "plugin" else f"{BASES[item['base']]} theme" if kind == "theme"
             else f"{COSTS[item['cost']]} cost")
    return f"By {', '.join(a['name'] for a in item['authors'])} · v{item['version']} · {extra}"


def write_files(out, item):
    """Writes the item's pages' pictures into its directory: each preview as the original PNG and as AVIF at
    1x and 2x, the loop the same way, and the link preview card. Records them as
    item["shots"] = [{"png", "width", "height", "alt", "avif": [(name, width)]}] and
    item["loop_files"] = {"png", "avif" (a name or None), "width", "height", "seconds", "fps"} or None."""
    directory = os.path.join(out, KINDS[item["kind"]]["path"], item["slug"])
    where = f'{item["kind"]} {item["slug"]}'
    os.makedirs(directory, exist_ok=True)

    def write(name, data):
        with open(os.path.join(directory, name), "wb") as f:
            f.write(data)

    item["shots"], item["loop_files"] = [], None
    for n, image in enumerate(item["previews"], 1):
        png = f"preview-{n}.png"
        write(png, image["data"])
        avif = []
        for width, data in images.stills(image, f"{where}.previews[{n - 1}]"):
            avif.append((f"preview-{n}-{width}.avif", width))
            write(avif[-1][0], data)
        item["shots"].append({"png": png, "width": image["width"], "height": image["height"], "alt": image["alt"], "avif": avif})
    loop = item.get("loop")
    if loop:
        write("loop.png", loop["data"])
        loop_avif = images.loop(loop, f"{where}.loop")
        if loop_avif:
            write("loop.avif", loop_avif)
        item["loop_files"] = {"png": "loop.png", "avif": "loop.avif" if loop_avif else None,
                              **{k: loop[k] for k in ("width", "height", "seconds", "fps")}}
    preview = item["previews"][0]["data"] if item["previews"] else None
    social.render_item(os.path.join(directory, "og.png"), item["kind"].capitalize(), item["name"], item["summary"],
                       card_details(item), preview)


# ---- page shell --------------------------------------------------------------------------------

def nav_html(up, current=None, anchors=()):
    """The top navigation every page shares: the brand, the page's own anchors (home), the three catalog
    listings, GitHub and the theme picker. `up` leads from the page to the site root ("" on the home page)."""
    picker = "".join(f'<button type="button" role="menuitemradio" tabindex="-1" data-theme="{key}">{name}</button>'
                     for key, name in THEMES)
    pages = "".join(f'<a class="page" href="#{target}">{label}</a>' for target, label in anchors)
    kinds = "".join(
        f'<a href="{up}{info["path"]}/"{" aria-current=\"page\"" if kind == current else ""}>{info["title"]}</a>'
        for kind, info in KINDS.items())
    return (f'<nav class="top" aria-label="Main">\n  <a class="brand" href="{up or "./"}">{LOGO}<span>MaiCord</span></a>\n'
            f'  {pages}{kinds}\n  <a class="hide" href="https://github.com/maj113/MaiCord">GitHub</a>\n'
            '  <div class="picker" hidden>\n'
            '    <button type="button" id="theme-button" aria-haspopup="menu" aria-expanded="false" aria-controls="theme-menu" aria-label="Theme"></button>\n'
            f'    <div id="theme-menu" role="menu" aria-label="Theme" hidden>{picker}</div>\n  </div>\n</nav>')


class Site:
    def __init__(self, catalog, theme_css):
        self.catalog, self.live = catalog, catalog["live"]
        self.chrome_css, self.cards_css = asset("chrome.css"), asset("cards.css")
        self.css = (asset("page.css").replace("/*THEME*/", theme_css).replace("/*CHROME*/", self.chrome_css)
                    .replace("/*CARDS*/", self.cards_css))
        self.site_js = asset("site.js")
        self.items = {kind: sorted((i for i in catalog["items"] if i["kind"] == kind), key=lambda i: i["name"].casefold())
                      for kind in KINDS}

    def sample_note(self):
        return "" if self.live else ('<p class="sample" role="note">Sample data: a test catalog signed with a throwaway key, '
                                     'not published yet.</p>')

    def shell(self, *, title, description, path, depth, body, script="", image=None, current=None, catalog_page=True,
              absolute=False, indexed=True):
        """A whole page. `depth` is the page's directory depth below the site root, or `absolute` gives root-relative
        links (the 404 page, which is served from any depth). `image` is (url, width, height, alt) for the link
        preview. A `catalog_page` shows the sample-data note and stays noindex until the live catalog is
        published; `indexed` False marks any page noindex."""
        up = "/" if absolute else "../" * depth
        notice = self.sample_note() if catalog_page else ""
        robots = "" if (self.live or not catalog_page) and indexed else '<meta name="robots" content="noindex">\n'
        canonical = f'<link rel="canonical" href="{SITE}{path}">\n' if indexed else ""
        url, width, height, alt = image or (SITE + "og.png", 1200, 630, None)
        alt = f'<meta property="og:image:alt" content="{esc(alt)}">\n' if alt else ""
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · MaiCord</title>
<meta name="description" content="{esc(description)}">
{canonical}{robots}<meta name="color-scheme" content="dark light">
<script>try{{var t=localStorage.getItem("theme");if(/^(dark|light|amoled|aurora|sunset|ocean|aurora-light)$/.test(t))document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<meta name="theme-color" content="#1a1a1e" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f9fafc" media="(prefers-color-scheme: light)">
<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{up}apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MaiCord">
<meta property="og:title" content="{esc(title)} · MaiCord">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{esc(url)}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="{width}">
<meta property="og:image:height" content="{height}">
{alt}<meta name="twitter:card" content="summary_large_image">
<style>
{self.css}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="sky" aria-hidden="true"></div>
<div class="wrap">
{nav_html(up, current)}
<main id="main">
{notice}{body}
</main>
</div>
<footer>
  <div class="wrap">
    <div class="links">
      <a href="https://github.com/maj113/MaiCord">Source</a>
      <a href="https://github.com/maj113/MaiCord-plugins">Catalog on GitHub</a>
      <a href="{up}plugins/develop/">Plugin guide</a>
      <a href="{up}effects/develop/">Effect guide</a>
      <a href="https://github.com/maj113/MaiCord/releases">Releases</a>
      <a href="https://github.com/maj113/MaiCord/issues">Issues</a>
    </div>
    <p>MaiCord is not affiliated with Discord Inc. Discord is a trademark of Discord Inc.</p>
  </div>
</footer>
<script>
{self.site_js}{script}</script>
</body>
</html>
"""


# ---- listing -----------------------------------------------------------------------------------

def facets(kind, items):
    """[(facet key, label, [(value, label, count)])] for the chips; each facet's values are those present."""
    def counted(key, values):
        return [(v, label, sum(v in values(i) for i in items)) for v, label in key]

    categories = sorted({c for i in items for c in i["categories"]})
    out = [("cat", "Category", counted([(c, title_case(c)) for c in categories], lambda i: i["categories"]))]
    if kind == "theme":
        out.append(("base", "Base", counted(BASES.items(), lambda i: [i["base"]])))
    if kind == "effect":
        out.append(("cost", "Cost", counted(COSTS.items(), lambda i: [i["cost"]])))
    return [(key, label, [v for v in values if v[2]]) for key, label, values in out]


def srcset(shot, base, limit=None):
    return ", ".join(f"{base}{name} {width}w" for name, width in shot["avif"] if limit is None or width <= limit)


def picture(shot, *, sizes, base="", limit=None, alt="", loop=None, priority=False):
    """The <picture> of a preview: AVIF at the widths the page can use, the PNG as the fallback. With `loop`
    (an effect's loop files) the AVIF loop plays instead, and the still shows for reduced motion."""
    still = f'type="image/avif" srcset="{srcset(shot, base, limit)}" sizes="{sizes}"'
    load = 'fetchpriority="high"' if priority else 'loading="lazy"'
    if loop:
        return (f'<picture><source media="(prefers-reduced-motion: reduce)" {still}>'
                f'<source media="(prefers-reduced-motion: reduce)" srcset="{base}{shot["png"]}">'
                + (f'<source type="image/avif" srcset="{base}{loop["avif"]}">' if loop["avif"] else "") +
                f'<img src="{base}{loop["png"]}" width="{loop["width"]}" height="{loop["height"]}" alt="{esc(alt)}" '
                f'decoding="async" {load}></picture>')
    return (f'<picture><source {still}><img src="{base}{shot["png"]}" width="{shot["width"]}" height="{shot["height"]}" '
            f'alt="{esc(alt)}" decoding="async" {load}></picture>')


# The width a card's picture is shown at: one column below 656 pixels, two below 972, else three at most 349.
CARD_SIZES = "(max-width: 655px) calc(100vw - 40px), (max-width: 971px) calc((100vw - 56px) / 2), 349px"
# The home page's tiles: three in a row of 920 pixels, two on a phone. A detail page's first preview fills its
# column (708 pixels beside the panel, the page's width below 861); the others take half of it.
TILE_SIZES = "(max-width: 560px) calc((100vw - 56px) / 2), (max-width: 960px) calc((100vw - 72px) / 3), 296px"
DETAIL_SIZES = "(max-width: 860px) calc(100vw - 40px), 708px"
HALF_SIZES = "(max-width: 560px) calc(100vw - 40px), (max-width: 860px) calc((100vw - 52px) / 2), 348px"


def card(item, base="", heading="h2", animated=False, compact=False):
    """One catalog card. `base` leads from the page to the item's directory; `animated` shows an effect's loop."""
    kind, slug = item["kind"], item["slug"]
    version = item["versions"][0]
    tags = []
    if kind == "plugin":
        level = access(item)
        tags.append(f'<li class="tag"><span class="dot {LEVELS[level].lower()}"></span>{LEVELS[level]} access</li>')
    elif kind == "theme":
        if item.get("swatches"):
            dots = "".join(f'<i style="background:{item["swatches"][k]}"></i>' for k in ("background", "surface", "accent", "text"))
            tags.append(f'<li class="tag"><span class="swatches" aria-hidden="true">{dots}</span>{BASES[item["base"]]}</li>')
        else:
            tags.append(f'<li class="tag">{BASES[item["base"]]}</li>')
    else:
        tags.append(f'<li class="tag"><span class="dot {item["cost"]}"></span>{COSTS[item["cost"]]} cost</li>')
    tags += [f'<li class="tag">{esc(title_case(c))}</li>' for c in item["categories"]]
    thumb = ""
    if item["shots"]:
        sizes = TILE_SIZES if compact else CARD_SIZES
        thumb = (f'<div class="thumb">{picture(item["shots"][0], sizes=sizes, base=f"{base}{slug}/", limit=720, loop=item["loop_files"] if animated else None)}</div>')
    words = [item["name"], item["summary"], item["slug"], item["license"], *item["categories"],
             *(a["name"] for a in item["authors"]), *version.get("permissions", []), *version.get("network", [])]
    data = {"text": " ".join(words).lower(), "cat": " ".join(item["categories"]), "sort-name": item["name"].casefold(),
            "sort-new": -item["released"]}
    if kind == "plugin":
        data["sort-access"] = access(item) * 100 + len(version["permissions"])
    elif kind == "theme":
        data["base"] = item["base"]
    else:
        data["cost"] = item["cost"]
        data["sort-cost"] = list(COSTS).index(item["cost"])
    attrs = "" if base else " " + " ".join(f'data-{k}="{esc(str(v))}"' for k, v in data.items())
    if compact:
        return (f'<li class="item">{thumb}<div class="body"><{heading}><a href="{base}{slug}/">{esc(item["name"])}</a></{heading}>'
                f'<ul class="meta">{tags[0]}</ul></div></li>')
    return (f'<li class="item"{attrs}>{thumb}<div class="body"><{heading}><a href="{base}{slug}/">{esc(item["name"])}</a></{heading}>'
            f'<p class="by">{authors_html(item, links=False)} · v{esc(item["version"])}</p><p class="sum">{esc(item["summary"])}</p>'
            f'<ul class="meta">{"".join(tags)}</ul></div></li>')


def listing(site, kind):
    info, items = KINDS[kind], site.items[kind]
    sorts = "".join(f'<option value="{k}">{v}</option>' for k, v in info["sorts"])
    rows = ""
    for key, label, values in facets(kind, items):
        chips = "".join(f'<button type="button" class="chip" data-facet="{key}" data-value="{esc(v)}" aria-pressed="false">'
                        f'{esc(name)}<small aria-hidden="true">{count}</small></button>' for v, name, count in values)
        rows += (f'<div class="row" role="toolbar" aria-labelledby="f-{key}"><span class="label" id="f-{key}">{label}</span>'
                 f'<div class="chips">{chips}</div></div>')
    cards = "".join(card(i) for i in items)
    if site.live:
        stamp = (f'Catalog issued {date_text(site.catalog["issued"])}. Items are listed from MaiCord\'s signed catalog; '
                 'MaiCord checks the signature again before it installs anything.')
    else:
        stamp = "Sample build: this catalog is signed with a throwaway key and is not published yet."
    heading, text, label, target = info["build"]
    body = f"""<header class="listhead">
<h1>{info["title"]}</h1>
<p class="lead">{info["lead"]}</p>
<p class="actions"><a class="button secondary" href="{target}">{heading}</a></p>
</header>
<form id="filters" class="filters" role="search" hidden>
  <div class="row searchrow">
    <label class="sr" for="q">Search {info["title"].lower()}</label>
    <input id="q" name="q" type="search" placeholder="Search {info["title"].lower()}" autocomplete="off">
    <span class="sortbox"><label class="label" for="sort">Sort by</label>
    <select id="sort" name="sort">{sorts}</select></span>
  </div>
  {rows}
</form>
<p id="count" role="status" hidden></p>
<ul id="items" class="cards" data-noun="{info["noun"]}">{cards}</ul>
<div id="empty" hidden><strong>Nothing matches</strong><p id="why"></p>
  <div class="actions"><button type="button" class="button secondary">Clear filters</button><a class="button secondary" href="{target}">{heading}</a></div></div>
<div class="build"><div><h2>{heading}</h2><p>{text}</p></div><a class="button secondary" href="{target}">{label}</a></div>
<p class="fine">{stamp}</p>
<!-- catalog sequence {site.catalog["sequence"]} -->"""
    return site.shell(title=info["title"], description=f'{info["lead"]} Browse and install from MaiCord.',
                      path=f'{info["path"]}/', depth=1, body=body, script=asset("listing.js"), current=kind)


# ---- detail pages ------------------------------------------------------------------------------

def permissions_html(version):
    rows = []
    for name in sorted(version["permissions"], key=lambda p: (-PERMISSIONS.get(p, ("", 1))[1], PERMISSIONS.get(p, (p, 1))[0])):
        label, level = PERMISSIONS.get(name, (name.replace("_", " ").capitalize(), 1))
        rows.append(f'<li><span>{esc(label)}</span><code>{esc(name)}</code>'
                    f'<span class="tag"><span class="dot {LEVELS[level].lower()}"></span>{LEVELS[level]}</span></li>')
    out = ""
    if rows:
        out = f'<ul class="perms">{"".join(rows)}</ul>'
    else:
        out = "<p>This plugin asks for no permissions.</p>"
    if version["network"]:
        hosts = "".join(f"<li><code>{esc(h)}</code></li>" for h in version["network"])
        out += f"<h3>Network hosts</h3><p>It may connect to these hosts, and to no others.</p><ul>{hosts}</ul>"
    return out


def knob_row(knob):
    kind = knob["type"]
    if kind in ("float", "int"):
        rng, default = f'{knob["min"]:g} to {knob["max"]:g}', f'{knob["default"]:g}'
    elif kind == "toggle":
        rng, default = "On or off", "On" if knob["default"] else "Off"
    elif kind == "color":
        rng = "Any colour"
        default = f'<span class="swatches"><i style="background:{knob["default"]}"></i></span> <code>{esc(knob["default"])}</code>'
    else:
        rng, default = esc(", ".join(knob["choices"])), esc(knob["choices"][knob["default"]])
    return f'<tr><td>{esc(knob["label"])}</td><td>{KNOB_TYPES[kind]}</td><td>{rng}</td><td>{default}</td></tr>'


def detail(site, item):
    kind, slug = item["kind"], item["slug"]
    info, version = KINDS[kind], item["versions"][0]
    link = f"maicord://install/{kind}/{slug}"
    # An item that needs an interface older MaiCord releases don't have (only the newer indexes list it).
    needs = None
    if item["interface"] > 1:
        release = catalog.INTERFACE_RELEASES.get(kind, {}).get(item["interface"])
        needs = f"MaiCord {release} or later" if release else "a newer MaiCord"

    previews = ""
    if item["shots"]:
        figures = []
        for n, shot in enumerate(item["shots"]):
            loop = item["loop_files"] if n == 0 else None
            caption = (f'<figcaption>A {loop["seconds"]:g}-second loop at {loop["fps"]} frames per second.</figcaption>'
                       if loop else "")
            sizes = DETAIL_SIZES if n == 0 else HALF_SIZES
            figures.append(f'<figure>{picture(shot, sizes=sizes, alt=shot["alt"], loop=loop, priority=n == 0)}{caption}</figure>')
        previews = f'<div class="preview">{"".join(figures)}</div>'

    extra = ""
    if kind == "plugin":
        extra = f'<section id="permissions"><h2>Permissions</h2>{permissions_html(version)}</section>'
    elif kind == "theme":
        swatches = item.get("swatches")
        if swatches:
            names = (("background", "Background"), ("surface", "Surface"), ("text", "Text"), ("accent", "Accent"))
            chips = "".join(f'<li><i style="background:{swatches[k]}"></i><span>{label}<br><code>{swatches[k]}</code></span></li>'
                            for k, label in names)
            extra += f'<section id="colours"><h2>Colours</h2><ul class="colors">{chips}</ul></section>'
        if item.get("effect"):
            effect = next((e for e in site.items["effect"] if e["slug"] == item["effect"]), None)
            target = (f'<a href="../../effects/{esc(effect["slug"])}/">{esc(effect["name"])}</a>' if effect
                      else f'<code>{esc(item["effect"])}</code>')
            extra += (f'<section id="effect"><h2>Background effect</h2><p>This theme turns on the {target} effect. '
                      f'Installing the theme offers to install the effect too.</p></section>')
    else:
        rows = "".join(knob_row(k) for k in item["knobs"])
        table = ('<div class="scroll" role="region" aria-label="Knobs" tabindex="0"><table class="sheet"><thead><tr><th>Knob</th><th>Type</th><th>Range</th><th>Default</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>') if rows else "<p>This effect has no knobs of its own.</p>"
        extra += (f'<section id="knobs"><h2>Knobs</h2>{table}<p class="fine">Every effect also gets MaiCord\'s own controls: '
                  f'speed, resolution, frame rate, opacity, blend, what happens when MaiCord is not focused, and a GPU budget.</p></section>')
        users = [t for t in site.items["theme"] if t.get("effect") == slug]
        if users:
            names = "".join(f'<li><a href="../../themes/{esc(t["slug"])}/">{esc(t["name"])}</a></li>' for t in users)
            extra += f'<section id="themes"><h2>Used by these themes</h2><ul>{names}</ul></section>'

    news = ""
    notes = [v for v in item["versions"] if v["changelog"]]
    if notes:
        entries = "".join(f'<li><strong>{esc(v["version"])}</strong><time datetime="{datetime.datetime.fromtimestamp(v["released"], datetime.timezone.utc):%Y-%m-%d}">'
                          f'{date_text(v["released"])}</time><p>{esc(v["changelog"])}</p></li>' for v in notes)
        news = f'<section id="changes"><h2>What\'s new</h2><ul class="versions">{entries}</ul></section>'

    credit = f'<p>Made by {authors_html(item)}.</p>'
    derived = item["derived_from"]
    if derived:
        credit += (f'<p>Based on the work of {esc(derived["author"])} (<a href="{esc(derived["url"])}">'
                   f'{esc(derived["url"].split("/")[2])}</a>), used under the {license_html(derived["license"])} license.</p>')

    facts = [("Version", esc(item["version"])), ("Released", date_text(item["released"])), ("License", license_html(item["license"])),
             ("Size", bytes_text(item["file"]["bytes"]))]
    if kind == "plugin":
        facts.append(("Plugin API", f'level {version["api_level"]}'))
    elif kind == "theme":
        facts.append(("Base", BASES[item["base"]]))
    else:
        facts += [("Cost", f'{COSTS[item["cost"]]}, {COST_NOTES[item["cost"]]}'), ("Blend", BLENDS[item["blend"]])]
        if item["uses"]:
            facts.append(("Uses", esc(", ".join(USES[u] for u in item["uses"]))))
        if needs:
            facts.append(("Needs", needs))
    if item["homepage"]:
        facts.append(("Website", f'<a href="{esc(item["homepage"])}">{esc(item["homepage"].split("/")[2])}</a>'))
    facts.append(("SHA-256", f'<code>{item["file"]["sha256"]}</code>'))
    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)

    body = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="../">{info["title"]}</a> › <span aria-current="page">{esc(item["name"])}</span></nav>
<header class="head">
<h1>{esc(item["name"])}</h1>
<p class="lead">{esc(item["summary"])}</p>
<p class="byline"><span>By {authors_html(item)}</span><span>Updated {date_text(item["released"])}</span></p>
</header>
<div class="detail">
<aside>
  <div class="panel install">
    <a class="button primary" id="install" href="{link}">Install in MaiCord</a>
    <p class="fine">Opens MaiCord, which shows what you are installing and asks before it changes anything.{f" This effect needs {needs}." if needs else ""}</p>
    <p class="linkrow"><code id="link">{link}</code><button type="button" class="button secondary" id="copy" hidden>Copy link</button><span id="copied" role="status"></span></p>
    <div role="status"><div class="hint" id="hint" hidden><strong>Nothing opened?</strong><p>MaiCord may not be installed, or your browser blocked the prompt that asks to open it. <a href="../../#install">Get MaiCord</a>, allow the prompt and try again, or find this {info["noun"]} in MaiCord's Browse tab.</p></div></div>
    <p class="fine" id="help">Nothing happens? MaiCord asks the first time whether it may open <code>maicord://</code> links, so until you agree, copy the link or find this {info["noun"]} in MaiCord's Browse tab. <a href="../../#install">Get MaiCord</a></p>
  </div>
  <div class="panel"><dl class="facts">{facts_html}</dl></div>
  <a class="button secondary" href="{esc(item["source"])}">View source</a>
</aside>
<div class="main">
{previews}<section id="about"><h2>About</h2>{markdown(item["description"], 3)}</section>
{extra}{news}<section id="credit"><h2>Credit</h2>{credit}</section>
</div>
</div>"""
    card_image = (f'{SITE}{info["path"]}/{slug}/og.png', 1200, 630, f'{item["name"]}: a MaiCord {info["noun"]}. {item["summary"]}')
    return site.shell(title=f'{item["name"]} · {info["title"]}', description=item["summary"], path=f'{info["path"]}/{slug}/',
                      depth=2, body=body, script=asset("detail.js"), image=card_image, current=kind)


# ---- developer guides, 404, home --------------------------------------------------------------

def develop(site, kind):
    """/plugins/develop/ or /effects/develop/: the guide from guides/, in the site's look."""
    info, g = KINDS[kind], GUIDES[kind]
    with open(os.path.join(ROOT, "guides", "source.json"), encoding="utf-8") as f:
        source = json.load(f)
    with open(os.path.join(ROOT, "guides", g["file"]), encoding="utf-8") as f:
        heading, sections, content = guide.render(f.read(), g["links"])
    known = dict(sections)
    missing = [a for a, _ in g["jump"] if a not in known]
    if missing:
        raise SystemExit(f'guides/{g["file"]} has no section with the id(s) {", ".join(missing)}; update GUIDES in catalog_pages.py')
    jump = "".join(f'<li><a class="chip" href="#{a}">{esc(label)}</a></li>' for a, label in g["jump"])
    toc = "".join(f'<li><a href="#{a}">{esc(text)}</a></li>' for a, text in sections)
    path = source["files"][g["file"]]
    body = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="../">{info["title"]}</a> › <span aria-current="page">Develop</span></nav>
<header class="head">
<h1>{g["title"]}</h1>
<p class="lead">{g["lead"]}</p>
<p class="byline"><span>{esc(heading)}</span><span>From MaiCord <code>{source["commit"][:10]}</code>, {date_text(guides_stamp(source))}</span></p>
<ul class="jump" aria-label="Jump to a section">{jump}</ul>
</header>
<div class="guide-layout">
<nav class="toc" aria-label="On this page"><h2>On this page</h2><ol>{toc}</ol></nav>
<article class="guide">{content}</article>
</div>
<p class="fine source">This guide is <a href="https://github.com/{source["repository"]}/blob/master/{path}"><code>{path}</code></a> in MaiCord's
repository, rendered here as of commit <code>{source["commit"][:10]}</code>. The file on GitHub is always the latest.</p>"""
    return site.shell(title=g["title"], description=g["lead"], path=f'{info["path"]}/develop/', depth=2, body=body,
                      current=kind, catalog_page=False)


def guides_stamp(source):
    return int(datetime.datetime.strptime(source["date"], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


NOT_FOUND_SCRIPT = """// A mistyped catalog address: offer the search for it.
(() => {
  const m = location.pathname.match(/^\\/(plugins|themes|effects)\\/([a-z0-9-]+)/), note = document.getElementById("guess");
  if (!m || m[2] === "develop") return;
  const link = document.createElement("a");
  link.href = `/${m[1]}/?q=${encodeURIComponent(m[2].replace(/-/g, " "))}`;
  link.textContent = `Search ${m[1]} for “${m[2].replace(/-/g, " ")}”`;
  note.replaceChildren("Looking for something in particular? ", link, ".");
  note.hidden = false;
})();
"""


def not_found(site):
    """404.html: GitHub Pages serves it for any missing address, at any depth, so every link is root-relative."""
    notes = {"plugin": "Features, buttons and commands", "theme": "Colours, type and motion", "effect": "Animated backgrounds"}
    choices = "".join(
        f'<li><a href="/{info["path"]}/"><b>{info["title"]}</b><span>{len(site.items[kind])} in the catalog · {notes[kind]}</span></a></li>'
        for kind, info in KINDS.items())
    body = f"""<div class="lost">
<h1>Page not found</h1>
<p class="lead">That address doesn't lead anywhere. The catalog has what you may have been looking for.</p>
<ul class="choices">{choices}</ul>
<p class="fine" id="guess" hidden></p>
<p class="actions"><a class="button secondary" href="/">Back to the home page</a></p>
</div>"""
    return site.shell(title="Page not found", description="This page doesn't exist. Browse the plugins, themes and effects.",
                      path="404.html", depth=0, body=body, script=NOT_FOUND_SCRIPT, catalog_page=False, absolute=True,
                      indexed=False)


# The home page shows these plugins and effects (by slug) and the first six themes. One that the catalog no
# longer lists (revoked, renamed) is left out with a warning, so a revocation never stops the site's deploy.
HOME_PLUGINS = ("translate", "message-logger", "clear-urls")
HOME_EFFECTS = ("ascii-rain", "aurora")
HOME_THEMES = 6
HOME_ANCHORS = (("screenshots", "Screenshots"), ("features", "Features"), ("install", "Install"),
                ("changelog", "Changelog"), ("faq", "FAQ"))


def home_section(site):
    """The home page's section on plugins, themes and effects: a few real cards and the links to the listings."""
    def pick(kind, slugs):
        by_slug = {i["slug"]: i for i in site.items[kind]}
        for slug in slugs:
            if slug not in by_slug:
                catalog.warnings.append(f"home page: {kind} {slug} is not in the catalog and is left out")
        return [by_slug[s] for s in slugs if s in by_slug]

    groups = []
    for kind, items, classes, extra in (
            ("plugin", pick("plugin", HOME_PLUGINS), "cards three", {}),
            ("theme", site.items["theme"][:HOME_THEMES], "cards tiles", {"compact": True}),
            ("effect", pick("effect", HOME_EFFECTS), "cards two", {"animated": True})):
        if not items:
            continue
        info, base = KINDS[kind], KINDS[kind]["path"] + "/"
        cards = "".join(card(i, base=base, heading="h4", **extra) for i in items)
        count = len(site.items[kind])
        groups.append(f'<div class="group"><h3>{info["title"]}</h3><a href="{base}">Browse all {count} {info["noun"]}{"" if count == 1 else "s"}</a></div>\n'
                      f'<ul class="{classes}">{cards}</ul>')
    return f"""<section id="catalog">
  <h2>Plugins, themes and effects</h2>
  <p>Extend MaiCord from one official catalog. Plugins add features, themes restyle the interface, and effects draw a live shader behind it. Every item is reviewed, built from public source and signed, MaiCord checks the signature before it installs anything, and a plugin shows what it may do before it runs.</p>
  {site.sample_note()}
  {chr(10).join(groups)}
  <p class="fine">Write your own: the <a href="plugins/develop/">plugin guide</a> and the <a href="effects/develop/">effect guide</a>.</p>
</section>"""


def stamp_iso(stamp):
    return f"{datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc):%Y-%m-%d}"


def sitemap(site):
    """<url> lines for sitemap.xml. The developer guides always; the listings and every item once the live
    catalog is published, since the pages of a fixture build are noindex."""
    with open(os.path.join(ROOT, "guides", "source.json"), encoding="utf-8") as f:
        guides = json.load(f)["date"]
    rows = []
    for kind, info in KINDS.items():
        if site.live:
            rows.append((f'{info["path"]}/', stamp_iso(site.catalog["issued"])))
            rows += [(f'{info["path"]}/{i["slug"]}/', stamp_iso(i["released"])) for i in site.items[kind]]
        if kind in GUIDES:
            rows.append((f'{info["path"]}/develop/', guides))
    return "\n".join(f"  <url><loc>{SITE}{path}</loc><lastmod>{day}</lastmod></url>" for path, day in rows)


def write_page(out, path, text):
    target = os.path.join(out, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build(out, catalog_data, theme_css):
    """Writes /plugins/, /themes/, /effects/ (listings, one directory per item, the developer guide) and 404.html
    into `out`; returns the pieces the home page and the sitemap take from them."""
    images.require()
    site = Site(catalog_data, theme_css)
    for kind, info in KINDS.items():
        for item in site.items[kind]:
            if item["slug"] in RESERVED_SLUGS:
                raise SystemExit(f'{kind} {item["slug"]}: "{item["slug"]}" is reserved for the site ({info["path"]}/{item["slug"]}/)')
            write_files(out, item)
        write_page(out, f'{info["path"]}/index.html', listing(site, kind))
        for item in site.items[kind]:
            write_page(out, f'{info["path"]}/{item["slug"]}/index.html', detail(site, item))
    for kind in ("plugin", "effect"):
        write_page(out, f'{KINDS[kind]["path"]}/develop/index.html', develop(site, kind))
    write_page(out, "404.html", not_found(site))
    return {"nav": nav_html("", anchors=HOME_ANCHORS), "catalog_home": home_section(site), "sitemap_pages": sitemap(site),
            "chrome_css": site.chrome_css, "cards_css": site.cards_css, "site_js": site.site_js}
