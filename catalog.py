"""Loads and checks the catalog the plugin, theme and effect pages are built
from: index format 2 of maj113/MaiCord-plugins. CATALOG.md describes it.

Two sources, one code path after the bytes arrive, and both signed:
  fixture  catalog-fixture.json (the index), catalog-fixture/ (its signature,
           throwaway public key, details and previews): a real format 2 build
  live     the published index and its signature, verified against the
           catalog public key, plus the details and preview files it names

The index is untrusted input. The structure is checked strictly (a wrong type,
a missing member or a bad value fails the build, so the site never publishes a
half-understood catalog) while unknown members are ignored with a warning, so
a format that grows does not stop deployments. Every details and preview file
is checked against the SHA-256 and size the index lists.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

import p256

ROOT = os.path.dirname(os.path.abspath(__file__))
FIXTURE_INDEX = os.path.join(ROOT, "catalog-fixture.json")
FIXTURE_DIR = os.path.join(ROOT, "catalog-fixture")
LIVE_URL = "https://maj113.github.io/MaiCord-plugins/"
# The index MaiCord 0.6.4 and later read: every item, with the interface each
# one needs (index-full.json, for 0.6.3, and index.json, for 0.6.0 to 0.6.2,
# leave out what those can't run), so the site reads this one.
INDEX = "index-3.json"
# The index signature covers SHA-256(DOMAIN + document), as format 1 does with
# its "v1" domain (catalog format 2, local://prog/catalog-format2.md).
DOMAIN = b"MaiCord plugin index v2\n"

KINDS = ("plugin", "theme", "effect")
MAX_INDEX_BYTES = 256 * 1024
MAX_ITEMS = 128
MAX_DETAILS_BYTES = 16 * 1024
MAX_PREVIEW_BYTES = 256 * 1024
MAX_LOOP_BYTES = 2 * 1024 * 1024
MAX_PREVIEWS = 4
# Package limits by kind: a DLL, a theme document, a .mcfx.
FILE_LIMITS = {"plugin": 8 * 1024 * 1024, "theme": 64 * 1024, "effect": 1536 * 1024}
MAX_VALIDITY_SECONDS = 35 * 86400
CLOCK_SKEW_SECONDS = 600

SLUG = r"[a-z0-9][a-z0-9-]*"
SHA256 = r"[0-9a-f]{64}"
COLOR = r"#[0-9a-fA-F]{6}"
COSTS = ("light", "medium", "heavy")
BLENDS = ("normal", "screen", "add")
BASES = ("dark", "light", "amoled")
USES = ("noise", "glyphs", "blue_noise", "pointer", "texture0", "texture1")
# The first MaiCord release that runs each interface above 1, per item kind.
INTERFACE_RELEASES = {"effect": {2: "0.6.3", 3: "0.6.3"}, "theme": {2: "0.6.4"}}
KNOB_TYPES = ("float", "int", "toggle", "color", "choice")
# The format 2 limits for knob scalars, colours and choices.
KNOB_LIMITS = {"scalar": 16, "color": 4, "choice": 8}
CHOICE_MAX = 16
VERSION = r"(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})"
HOST = r"(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+"
# MC_PERM_* names in bit order (include/maicord/sdk/plugin_abi.h).
PERMISSIONS = ("message_send", "read_messages", "message_history", "read_activity", "network", "composer",
               "act_messages", "act_presence", "clipboard", "automated_actions", "persistent_log")
SEVERITIES = ("malicious", "broken", "withdrawn")


def version_key(text):
    return tuple(int(part) for part in text.split("."))


# Unknown members and permission names the pages could not describe; the
# build prints them.
warnings = []


class CatalogError(Exception):
    pass


class Node:
    """An object being read member by member. Reading marks a member as known;
    finish() reports the rest."""

    def __init__(self, data, where):
        if type(data) is not dict:
            raise CatalogError(f"{where}: expected an object")
        self.data, self.where, self.known = data, where, set()

    def fail(self, key, what):
        raise CatalogError(f"{self.where}.{key}: {what}" if key else f"{self.where}: {what}")

    def get(self, key, required):
        self.known.add(key)
        if key in self.data:
            return self.data[key]
        if required:
            self.fail(key, "missing")
        return None

    def text(self, key, maximum, pattern=None, required=True):
        value = self.get(key, required)
        if value is None:
            return None
        if (type(value) is not str or not 0 < len(value) <= maximum
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
                or (pattern and not re.fullmatch(pattern, value))):
            self.fail(key, f"expected text of 1 to {maximum} characters" + (f" matching {pattern}" if pattern else ""))
        return value

    def url(self, key, required=True):
        return self.text(key, 256, r"https://[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:[0-9]+)?([/?#][^\s\"'<>\\]*)?", required)

    def integer(self, key, low, high, required=True):
        value = self.get(key, required)
        if value is None:
            return None
        if type(value) is not int or not low <= value <= high:
            self.fail(key, f"expected an integer from {low} to {high}")
        return value

    def real(self, key, required=True):
        value = self.get(key, required)
        if value is None:
            return None
        if type(value) not in (int, float) or abs(value) > 1e9 or value != value:
            self.fail(key, "expected a number")
        return value

    def decimal(self, key):
        """A number with at most 3 decimals."""
        value = self.real(key, True)
        if round(value, 3) != value:
            self.fail(key, "expected at most 3 decimals")
        return value

    def boolean(self, key, required=True):
        value = self.get(key, required)
        if value is not None and type(value) is not bool:
            self.fail(key, "expected true or false")
        return value

    def one_of(self, key, choices, required=True):
        value = self.get(key, required)
        if value is not None and value not in choices:
            self.fail(key, f"expected one of {', '.join(choices)}")
        return value

    def child(self, key, required=True):
        value = self.get(key, required)
        return None if value is None else Node(value, f"{self.where}.{key}")

    def array(self, key, maximum, minimum=0, required=True):
        value = self.get(key, required)
        if value is None:
            return None
        if type(value) is not list or not minimum <= len(value) <= maximum:
            self.fail(key, f"expected a list of {minimum} to {maximum} entries")
        return value

    def strings(self, key, maximum, pattern, minimum=0, required=True, maximum_text=253):
        values = self.array(key, maximum, minimum, required)
        if values is None:
            return None
        for n, value in enumerate(values):
            Node({"": value}, f"{self.where}.{key}[{n}]").text("", maximum_text, pattern)
        if len(set(values)) != len(values):
            self.fail(key, "duplicate entries")
        return values

    def hosts(self, key, maximum):
        """Network hosts: exact or `*.host`, lower-case LDH names, as the client accepts them."""
        values = self.strings(key, maximum, HOST)
        for value in values:
            base = value[2:] if value.startswith("*.") else value
            if len(base) > 64 or "." not in base or base.rsplit(".", 1)[1].isdigit():
                self.fail(key, f"{value!r} is not a host name")
        return values

    def finish(self):
        for key in sorted(set(self.data) - self.known):
            warnings.append(f"{self.where}: ignored unknown member {key!r}")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"duplicate member {key!r}")
        result[key] = value
    return result


class Source:
    """Reads the catalog's files by name: the index (INDEX) and its `.sig`,
    `details/<sha256>.md` and `previews/<sha256>.png`."""

    def __init__(self, live, url=LIVE_URL):
        self.live, self.url = live, url if url.endswith("/") else url + "/"

    def read(self, name, limit):
        if not self.live:
            path = os.path.join(FIXTURE_DIR, *name.split("/")) if name != INDEX else FIXTURE_INDEX
            if not os.path.exists(path):
                raise CatalogError(f"{name}: not found")
            with open(path, "rb") as f:
                data = f.read(limit + 1)
        else:
            request = urllib.request.Request(self.url + name, headers={"User-Agent": "maicord-site-build"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(limit + 1)
            except urllib.error.HTTPError as error:
                raise CatalogError(f"{name}: " + ("not found" if error.code == 404 else f"HTTP {error.code}")) from error
        if len(data) > limit:
            raise CatalogError(f"{name}: larger than {limit} bytes")
        return data


def _file(node, key, limit):
    """A {sha256, bytes} pair."""
    entry = node.child(key)
    sha, size = entry.text("sha256", 64, SHA256), entry.integer("bytes", 1, limit)
    entry.finish()
    return {"sha256": sha, "bytes": size}


def _image(raw, where, limit, loop):
    """A preview (with alt text) or, for effects, the looping APNG."""
    node = Node(raw, where)
    image = {"sha256": node.text("sha256", 64, SHA256), "bytes": node.integer("bytes", 1, limit),
             "width": node.integer("width", 1, 4096), "height": node.integer("height", 1, 4096)}
    if loop:
        image["fps"], image["seconds"] = node.integer("fps", 1, 60), node.integer("seconds", 1, 10)
    else:
        image["alt"] = node.text("alt", 255)
    node.finish()
    return image


def _author(raw, where):
    node = Node(raw, where)
    author = {"name": node.text("name", 64), "github": node.text("github", 39, r"[A-Za-z0-9][A-Za-z0-9-]*", required=False)}
    node.finish()
    return author


def _knob(raw, where):
    node = Node(raw, where)
    knob = {"id": node.text("id", 24, r"[a-z][a-z0-9_]*"), "type": node.one_of("type", KNOB_TYPES),
            "label": node.text("label", 48)}
    kind = knob["type"]
    if kind in ("float", "int"):
        read = node.decimal if kind == "float" else (lambda key: node.integer(key, -10 ** 9, 10 ** 9))
        knob["min"], knob["max"], knob["default"] = read("min"), read("max"), read("default")
        if not knob["min"] < knob["max"] or not knob["min"] <= knob["default"] <= knob["max"]:
            node.fail("default", "expected min < max and min <= default <= max")
    elif kind == "toggle":
        knob["default"] = node.boolean("default")
    elif kind == "color":
        knob["default"] = node.text("default", 7, COLOR)
    else:
        knob["choices"] = node.strings("choices", CHOICE_MAX, r"[^\x00-\x1f]+", minimum=2, maximum_text=24)
        knob["default"] = node.integer("default", 0, len(knob["choices"]) - 1)
    node.finish()
    return knob


def _knobs(raw, where):
    knobs = [_knob(entry, f"{where}[{n}]") for n, entry in enumerate(raw)]
    if len({k["id"] for k in knobs}) != len(knobs):
        raise CatalogError(f"{where}: duplicate knob id")
    counts = {"scalar": 0, "color": 0, "choice": 0}
    for knob in knobs:
        counts["scalar" if knob["type"] in ("float", "int", "toggle") else knob["type"]] += 1
    for name, limit in KNOB_LIMITS.items():
        if counts[name] > limit:
            raise CatalogError(f"{where}: more than {limit} {name} knobs")
    return knobs


def _version(raw, where, kind):
    """A plugin's version record, or the data item's own members (`raw` is the
    item's node then)."""
    node = raw if isinstance(raw, Node) else Node(raw, where)
    version = {"version": node.text("version", 11, VERSION), "released": node.integer("released", 1, 2 ** 40),
               "changelog": node.text("changelog", 512, required=False),
               "file": _file(node, "file", FILE_LIMITS[kind])}
    if kind == "plugin":
        version["commit"] = node.text("commit", 40, r"[0-9a-f]{40}", required=False)
        version["api_level"] = node.integer("api_level", 1, 0xFFFF)
        version["permissions"] = node.strings("permissions", len(PERMISSIONS), "|".join(PERMISSIONS))
        if version["permissions"] != [p for p in PERMISSIONS if p in version["permissions"]]:
            node.fail("permissions", "expected the permissions in their fixed order")
        version["network"] = node.hosts("network", 8)
        if ("network" in version["permissions"]) != bool(version["network"]):
            node.fail("network", "expected hosts exactly when the network permission is listed")
        node.finish()
    return version


def _item(raw, where, source):
    node = Node(raw, where)
    kind = node.one_of("kind", KINDS)
    item = {"kind": kind, "slug": node.text("slug", 40, SLUG), "name": node.text("name", 95),
            "summary": node.text("summary", 255), "license": node.text("license", 32, r"[A-Za-z0-9.+-]+"),
            "source": node.url("source"), "homepage": node.url("homepage", required=False)}
    item["authors"] = [_author(a, f"{where}.authors[{n}]") for n, a in enumerate(node.array("authors", 4, 1))]
    item["categories"] = node.strings("categories", 3, SLUG, maximum_text=24)
    derived = node.child("derived_from", required=False)
    item["derived_from"] = derived and {"url": derived.url("url"), "author": derived.text("author", 64),
                                        "license": derived.text("license", 32, r"[A-Za-z0-9.+-]+")}
    if derived:
        derived.finish()
    item["details"] = _file(node, "details", MAX_DETAILS_BYTES)
    item["previews"] = [_image(p, f"{where}.previews[{n}]", MAX_PREVIEW_BYTES, False) for n, p in enumerate(
        node.array("previews", MAX_PREVIEWS, 0 if kind == "plugin" else 1))]

    if kind == "plugin":
        versions = node.array("versions", 4, 1)
        item["versions"] = [_version(v, f"{where}.versions[{n}]", kind) for n, v in enumerate(versions)]
        for newer, older in zip(item["versions"], item["versions"][1:]):
            if version_key(newer["version"]) <= version_key(older["version"]) or newer["released"] < older["released"]:
                raise CatalogError(f"{where}.versions: expected newest first, versions strictly decreasing")
        latest = item["versions"][0]
    else:
        latest = _version(node, where, kind)
        item["versions"] = [latest]
        if kind == "theme":
            item["base"] = node.one_of("base", BASES)
            item["effect"] = node.text("effect", 40, SLUG, required=False)
            swatches = node.child("swatches", required=False)
            item["swatches"] = swatches and {k: swatches.text(k, 7, COLOR)
                                             for k in ("background", "surface", "text", "accent")}
            if swatches:
                swatches.finish()
        else:
            item["cost"] = node.one_of("cost", COSTS)
            item["blend"] = node.one_of("blend", BLENDS)
            item["uses"] = node.strings("uses", len(USES), "|".join(USES))
            item["knobs"] = _knobs(node.array("knobs", sum(KNOB_LIMITS.values())), f"{where}.knobs")
            loop = node.get("loop", False)
            item["loop"] = loop and _image(loop, f"{where}.loop", MAX_LOOP_BYTES, True)
    item["interface"] = node.integer("interface", 1, 0xFFFF, required=False) or 1
    if item["interface"] > 1 and item["interface"] not in INTERFACE_RELEASES.get(kind, {}):
        warnings.append(f"{where}: interface {item['interface']} has no release in INTERFACE_RELEASES")
    for key in ("version", "released", "changelog", "file"):
        item[key] = latest[key]
    node.finish()
    item["description"] = source.read(f"details/{item['details']['sha256']}.md", MAX_DETAILS_BYTES)
    check(item["description"], item["details"], f"{where}.details")
    item["description"] = item["description"].decode("utf-8")
    for image in item["previews"] + ([item["loop"]] if item.get("loop") else []):
        image["data"] = source.read(f"previews/{image['sha256']}.png",
                                    MAX_LOOP_BYTES if image is item.get("loop") else MAX_PREVIEW_BYTES)
        check(image["data"], image, f"{where}.previews")
    return item


def check(data, expected, where):
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise CatalogError(f"{where}: the file does not match the size and SHA-256 the index lists")


def parse(document, source, now):
    """Checks the index document; returns {"items", "sequence", "issued",
    "expires"} with each item's files loaded and verified."""
    try:
        raw = json.loads(document.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, ValueError) as error:
        raise CatalogError(f"index: not JSON ({error})") from error
    root = Node(raw, "index")
    if root.integer("format", 1, 1000) != 2:
        raise CatalogError("index: format 2 expected")
    sequence = root.integer("sequence", 1, 2 ** 63)
    issued, expires = root.integer("issued", 1, 2 ** 40), root.integer("expires", 1, 2 ** 40)
    if not issued < expires <= issued + MAX_VALIDITY_SECONDS or issued > now + CLOCK_SKEW_SECONDS:
        raise CatalogError("index: the validity window is wrong")
    if source.live and expires <= now:
        raise CatalogError("index: expired")
    # Revoked and blocked files are never shown; the client enforces the lists.
    withdrawn = set()
    for key in ("revoked", "blocklist"):
        seen_digests = set()
        for n, entry in enumerate(root.array(key, 64, required=False) or []):
            member = Node(entry, f"index.{key}[{n}]")
            digest = member.text("sha256", 64, SHA256)
            if digest in seen_digests:
                member.fail("sha256", "duplicate")
            seen_digests.add(digest)
            if key == "revoked":
                member.one_of("severity", SEVERITIES)
            reason = member.get("reason", True)
            if type(reason) is not str or len(reason) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in reason):
                member.fail("reason", "expected text of at most 128 characters")
            member.integer("since", 1, 2 ** 40)
            member.finish()
            withdrawn.add(digest)
    items, seen = [], set()
    for n, entry in enumerate(root.array("items", MAX_ITEMS)):
        item = _item(entry, f"items[{n}]", source)
        if (item["kind"], item["slug"]) in seen:
            raise CatalogError(f"items[{n}]: duplicate {item['kind']} {item['slug']}")
        seen.add((item["kind"], item["slug"]))
        if item["file"]["sha256"] in withdrawn:
            warnings.append(f"{item['kind']} {item['slug']} is revoked and not listed")
            continue
        items.append(item)
    root.finish()
    return {"items": items, "sequence": sequence, "issued": issued, "expires": expires}


def load(live, url=LIVE_URL, key_hex=None, now=None, next_key_hex=None):
    """The catalog from the fixture, or from `url`. Both are verified: the
    live one under `key_hex`, the catalog public key, or `next_key_hex`, the
    key it is rotating to (each 130 hex digits; MaiCord compiles in both and
    accepts either, so a rotation never stops the deploy), the fixture under
    the throwaway key stored beside it (catalog-fixture/public-key.txt)."""
    now = int(time.time()) if now is None else now
    source = Source(live, url)
    document = source.read(INDEX, MAX_INDEX_BYTES)
    if not live:
        with open(os.path.join(FIXTURE_DIR, "public-key.txt"), encoding="ascii") as f:
            keys = [("the fixture key", f.read().strip())]
    elif not key_hex:
        raise CatalogError("the live catalog needs its public key (--catalog-key or MAICORD_CATALOG_KEY)")
    else:
        keys = [("the catalog public key", key_hex)]
        if next_key_hex and next_key_hex.strip():
            keys.append(("the next catalog public key", next_key_hex))
    decoded = []
    for name, text in keys:
        try:
            decoded.append(bytes.fromhex(text.strip()))
        except ValueError as error:
            raise CatalogError(f"{name} is not hex") from error
    signature = source.read(f"{INDEX}.sig", 64)
    digest = hashlib.sha256(DOMAIN + document).digest()
    if not any(p256.verify(key, digest, signature) for key in decoded):
        raise CatalogError("index: the signature does not verify under " + (
            "the catalog public key" if len(decoded) == 1 else "the current or the next catalog public key"))
    catalog = parse(document, source, now)
    catalog["live"] = live
    return catalog
