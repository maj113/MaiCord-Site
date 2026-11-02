"""Renders the plugin, theme and effect pages from a loaded catalog
(catalog.py): a listing per kind with search, category filters and sort, and a
detail page per item. The pages are plain HTML that lists everything; the one
inline script (catalog-assets/) only adds the theme picker, the backdrop, the
filters and the copy button. CATALOG.md describes the data the pages read."""
import datetime
import html
import os

from markup import inline, markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "catalog-assets")
SITE = "https://maicord.com/"

KINDS = {
    "plugin": {
        "path": "plugins", "title": "Plugins", "noun": "plugin",
        "lead": "Native plugins that add features to MaiCord. Every plugin here is reviewed, built from its public "
                "source and signed, and you approve what it may do before it runs.",
        "sorts": (("name", "Name"), ("new", "Newest"), ("access", "Least access")),
    },
    "theme": {
        "path": "themes", "title": "Themes", "noun": "theme",
        "lead": "Colours, type and motion for MaiCord's interface. A theme is plain data and runs no code.",
        "sorts": (("name", "Name"), ("new", "Newest")),
    },
    "effect": {
        "path": "effects", "title": "Effects", "noun": "effect",
        "lead": "Animated backgrounds drawn by your GPU. An effect is a small shader with a few knobs, and it runs "
                "no code on your CPU.",
        "sorts": (("name", "Name"), ("new", "Newest"), ("cost", "Lightest")),
    },
}

# Permission names are the MC_PERM_* names in lower case (include/maicord/sdk/plugin_abi.h). The catalog lists the
# full effective set, including what hooks and buttons imply. The label is the consent text's gist and the level is
# how much the permission exposes: 0 stays on your PC, 1 reads or changes parts of your Discord data, 2 reads your
# messages, acts for you or reaches the network.
PERMISSIONS = {
    "message_send": ("Changes your messages before they are sent", 1),
    "read_messages": ("Reads the messages you receive", 2),
    "message_history": ("Keeps deleted and edited messages visible", 2),
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


def title_case(slug):
    return slug.replace("-", " ").capitalize()


def access(item):
    """The highest level among the latest version's permissions."""
    return max((PERMISSIONS.get(p, ("", 1))[1] for p in item["versions"][0]["permissions"]), default=0)


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


def write_files(out, item):
    """Writes the item's previews and loop into its directory and records their names:
    item["shots"] = [(name, image)], item["loop_name"]."""
    directory = os.path.join(out, KINDS[item["kind"]]["path"], item["slug"])
    os.makedirs(directory, exist_ok=True)
    item["shots"], item["loop_name"] = [], None
    for n, image in enumerate(item["previews"], 1):
        name = f"preview-{n}.png"
        with open(os.path.join(directory, name), "wb") as f:
            f.write(image["data"])
        item["shots"].append((name, image))
    if item.get("loop"):
        item["loop_name"] = "loop.png"
        with open(os.path.join(directory, "loop.png"), "wb") as f:
            f.write(item["loop"]["data"])


# ---- page shell --------------------------------------------------------------------------------

class Site:
    def __init__(self, catalog, theme_css):
        self.catalog, self.live = catalog, catalog["live"]
        self.css = asset("page.css").replace("/*THEME*/", theme_css)
        self.site_js = asset("site.js")
        self.items = {kind: sorted((i for i in catalog["items"] if i["kind"] == kind), key=lambda i: i["name"].casefold())
                      for kind in KINDS}

    def shell(self, *, title, description, path, depth, body, script, image=None, current=None):
        up = "../" * depth
        links = "".join(
            f'<a href="{up}{info["path"]}/"{" aria-current=\"page\"" if kind == current else ""}>{info["title"]}</a>'
            for kind, info in KINDS.items())
        picker = "".join(f'<button type="button" role="menuitemradio" tabindex="-1" data-theme="{key}">{name}</button>'
                         for key, name in THEMES)
        banner = ('' if self.live else '<p class="sample" role="note">Sample data: a test catalog signed with a throwaway key, '
                  'not published yet.</p>')
        robots = "" if self.live else '<meta name="robots" content="noindex">\n'
        image = image or SITE + "og.png"
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · MaiCord</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE}{path}">
{robots}<meta name="color-scheme" content="dark light">
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
<meta property="og:image" content="{esc(image)}">
<meta name="twitter:card" content="summary_large_image">
<style>
{self.css}</style>
</head>
<body>
<div class="sky" aria-hidden="true"></div>
<div class="wrap">
<nav class="top">
  <a class="brand" href="{up}">{LOGO}<span>MaiCord</span></a>
  {links}
  <a class="hide" href="https://github.com/maj113/MaiCord">GitHub</a>
  <div class="picker" hidden>
    <button type="button" id="theme-button" aria-haspopup="menu" aria-expanded="false" aria-controls="theme-menu" aria-label="Theme"></button>
    <div id="theme-menu" role="menu" aria-label="Theme" hidden>{picker}</div>
  </div>
</nav>
<main>
{banner}{body}
</main>
</div>
<footer>
  <div class="wrap">
    <div class="links">
      <a href="https://github.com/maj113/MaiCord">Source</a>
      <a href="https://github.com/maj113/MaiCord-plugins">Catalog on GitHub</a>
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


def card(item):
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
        name, image = item["shots"][0]
        thumb = (f'<div class="thumb"><img src="{slug}/{name}" width="{image["width"]}" height="{image["height"]}" '
                 f'alt="" loading="lazy" decoding="async"></div>')
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
    attrs = " ".join(f'data-{k}="{esc(str(v))}"' for k, v in data.items())
    return (f'<li class="item" {attrs}>{thumb}<div class="body"><h2><a href="{slug}/">{esc(item["name"])}</a></h2>'
            f'<p class="by">{authors_html(item, links=False)} · v{esc(item["version"])}</p><p class="sum">{esc(item["summary"])}</p>'
            f'<ul class="meta">{"".join(tags)}</ul></div></li>')


def listing(site, kind):
    info, items = KINDS[kind], site.items[kind]
    sorts = "".join(f'<option value="{k}">{v}</option>' for k, v in info["sorts"])
    rows = ""
    for key, label, values in facets(kind, items):
        chips = "".join(f'<button type="button" class="chip" data-facet="{key}" data-value="{esc(v)}" aria-pressed="false">'
                        f'{esc(name)}<small aria-hidden="true">{count}</small></button>' for v, name, count in values)
        rows += f'<div class="row" role="group" aria-labelledby="f-{key}"><span class="label" id="f-{key}">{label}</span>{chips}</div>'
    cards = "".join(card(i) for i in items)
    if site.live:
        stamp = (f'Catalog issued {date_text(site.catalog["issued"])}. Items are listed from MaiCord\'s signed catalog; '
                 'MaiCord checks the signature again before it installs anything.')
    else:
        stamp = "Sample build: this catalog is signed with a throwaway key and is not published yet."
    body = f"""<header>
<h1>{info["title"]}</h1>
<p class="lead">{info["lead"]}</p>
</header>
<form id="filters" class="filters" role="search" hidden>
  <div class="row">
    <label class="sr" for="q">Search {info["title"].lower()}</label>
    <input id="q" name="q" type="search" placeholder="Search {info["title"].lower()}" autocomplete="off">
    <span class="sortbox"><label class="label" for="sort">Sort by</label>
    <select id="sort" name="sort">{sorts}</select></span>
  </div>
  {rows}
</form>
<p id="count" role="status" hidden></p>
<ul id="items" class="grid" data-noun="{info["noun"]}">{cards}</ul>
<p id="empty" hidden>No {info["title"].lower()} match. <button type="button" class="button secondary">Clear filters</button></p>
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

    previews = ""
    if item["shots"]:
        figures = []
        for n, (name, image) in enumerate(item["shots"]):
            tag = (f'<img src="{name}" width="{image["width"]}" height="{image["height"]}" alt="{esc(image["alt"])}" '
                   f'decoding="async"{" fetchpriority=\"high\"" if n == 0 else " loading=\"lazy\""}>')
            caption = ""
            if n == 0 and item["loop_name"]:
                loop = item["loop"]
                tag = (f'<picture><source media="(prefers-reduced-motion: reduce)" srcset="{name}"><img src="{item["loop_name"]}" '
                       f'width="{loop["width"]}" height="{loop["height"]}" alt="{esc(image["alt"])}" decoding="async" '
                       f'fetchpriority="high"></picture>')
                caption = f'<figcaption>A {loop["seconds"]:g}-second loop at {loop["fps"]} frames per second.</figcaption>'
            figures.append(f"<figure>{tag}{caption}</figure>")
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
        table = ('<div style="overflow-x:auto"><table class="sheet"><thead><tr><th>Knob</th><th>Type</th><th>Range</th><th>Default</th></tr></thead>'
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
    <a class="button primary" href="{link}">Install in MaiCord</a>
    <p class="fine">Opens MaiCord, which shows what you are installing and asks before it changes anything.</p>
    <p class="linkrow"><code id="link">{link}</code><button type="button" class="button secondary" id="copy" hidden>Copy link</button><span id="copied" role="status"></span></p>
    <p class="fine">Nothing happens? MaiCord asks the first time whether it may open <code>maicord://</code> links, so until you agree, copy the link or find this {info["noun"]} in MaiCord's Browse tab. <a href="../../#install">Get MaiCord</a></p>
  </div>
  <div class="panel"><dl class="facts">{facts_html}</dl></div>
  <a class="button secondary" href="{esc(item["source"])}">View source</a>
</aside>
<div class="main">
{previews}<section id="about"><h2>About</h2>{markdown(item["description"], 3)}</section>
{extra}{news}<section id="credit"><h2>Credit</h2>{credit}</section>
</div>
</div>"""
    image = None
    if item["shots"]:
        image = f'{SITE}{info["path"]}/{slug}/{item["shots"][0][0]}'
    return site.shell(title=f'{item["name"]} · {info["title"]}', description=item["summary"], path=f'{info["path"]}/{slug}/',
                      depth=2, body=body, script=asset("detail.js"), image=image, current=kind)


def build(out, catalog, theme_css):
    """Writes /plugins/, /themes/, /effects/ and one directory per item into `out`."""
    site = Site(catalog, theme_css)
    for kind, info in KINDS.items():
        for item in site.items[kind]:
            write_files(out, item)
        with open(os.path.join(out, info["path"], "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(listing(site, kind))
        for item in site.items[kind]:
            with open(os.path.join(out, info["path"], item["slug"], "index.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(detail(site, item))
