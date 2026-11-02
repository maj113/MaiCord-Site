#!/usr/bin/env python3
"""Builds the site: copies site/ to the output directory, generates the
plugin, theme and effect pages (/plugins, /themes, /effects, their detail
pages and the two developer guides) and the 404 page from the catalog, then
fills the {{placeholders}} in index.html and sitemap.xml with that output and
with live data from the MaiCord repository (latest release, its download and
size on disk, CI status and recent changelogs) and the theme colours
(theme_tokens.py). It draws the link preview card (og.png), the
apple-touch-icon and one card per catalog page, makes AVIF variants of the
catalog's previews, and fails when a link, image or sitemap entry of the
result leads nowhere (check_site.py).

The pages are deterministic for the same data, so the deploy workflow can
skip a deploy when nothing changed (the animated AVIF loops are not
byte-identical between runs, and the comparison looks at pages only).

    pip install -r requirements.txt
    python3 build.py [--out _site] [--catalog fixture|live]

The catalog is catalog-fixture.json by default (sample items, see CATALOG.md).
--catalog live reads and verifies the signed index of maj113/MaiCord-plugins:
the public key comes from --catalog-key or MAICORD_CATALOG_KEY, the optional
key it is rotating to from --catalog-next-key or MAICORD_CATALOG_NEXT_KEY (a
signature under either is accepted, as in the client), and
--catalog-url points elsewhere (a mirror, a test server).

GITHUB_TOKEN, when set, raises the API rate limit; public data needs none.
"""
import argparse
import datetime
import html
import io
import json
import os
import re
import shutil
import sys
import urllib.request
import zipfile

import card
import catalog
import catalog_pages
import check_site
import theme_tokens
from markup import inline

REPO = "maj113/MaiCord"
API = "https://api.github.com/repos/" + REPO
CHANGELOG_RELEASES = 3
# Sections of generated release notes that the site leaves to GitHub: the
# long commit list and the per-release download boilerplate.
SKIPPED_SECTIONS = {"other", "download"}
ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = ("index.html", "sitemap.xml")


def get(path):
    request = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "maicord-site-build",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


class RemoteFile(io.RawIOBase):
    """A release asset read through HTTP range requests, so listing the
    archive fetches its central directory (a few KB), not the whole zip."""

    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        self.position = (offset, self.position + offset, self.size + offset)[whence]
        return self.position

    def readinto(self, buffer):
        end = min(self.position + len(buffer), self.size)
        if end <= self.position:
            return 0
        request = urllib.request.Request(self.url, headers={
            "User-Agent": "maicord-site-build", "Range": f"bytes={self.position}-{end - 1}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 206:
                raise OSError("the asset host ignored the range request")
            data = response.read()
        buffer[:len(data)] = data
        self.position += len(data)
        return len(data)


def disk_size(archive):
    """Bytes the extracted client takes: the archive's EXE and DLLs, or every
    file when it holds neither. The API gives only the zip's own size, so the
    sizes come from the zip's directory."""
    with zipfile.ZipFile(RemoteFile(archive["browser_download_url"], archive["size"])) as z:
        files = [i for i in z.infolist() if not i.is_dir()]
    binaries = [i.file_size for i in files if i.filename.lower().endswith((".exe", ".dll"))]
    return sum(binaries) if binaries else sum(i.file_size for i in files)


def date_text(stamp):
    day = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{day:%B} {day.day}, {day.year}", day.strftime("%Y-%m-%d")


def short_date(stamp):
    day = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{day:%b} {day.day}, {day.year}"


def size_text(size):
    # Binary megabytes, labelled MB as Windows Explorer shows them.
    return f"{size / 1048576:.1f} MB"


def notes_html(body, url):
    """Renders the release notes' curated sections; counts the rest."""
    out, items, skipped, section = [], [], 0, None

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for line in body.replace("\r", "").split("\n"):
        line = line.rstrip()
        if line.startswith("## "):
            continue  # the release title, shown by the caller
        if line.startswith("### "):
            flush()
            section = line[4:].strip()
            if section.lower() not in SKIPPED_SECTIONS:
                out.append(f"<h4>{inline(section)}</h4>")
            continue
        skip = section is not None and section.lower() in SKIPPED_SECTIONS
        if line.startswith("- "):
            if skip:
                skipped += section.lower() == "other"
                continue
            # Drop the commit reference generated notes end each entry with.
            items.append(inline(re.sub(r"\s*\(\[`[0-9a-f]{7,40}`\]\([^)]*\)\)$", "", line[2:])))
        elif line and not skip and not line.startswith("**Full changelog:**"):
            flush()
            out.append(f"<p>{inline(line)}</p>")
    flush()
    more = f"and {skipped} more change{'s' * (skipped != 1)}" if skipped else "Full release notes"
    out.append(f'<p class="more"><a href="{html.escape(url)}">{more} on GitHub</a></p>')
    return "".join(out)


def build(out, catalog_data):
    releases = [r for r in get("/releases?per_page=20") if not r["draft"]]
    stable = [r for r in releases if not r["prerelease"]]
    if not stable:
        sys.exit("No published stable release.")
    latest = stable[0]
    archive = next((a for a in latest["assets"] if re.fullmatch(r"MaiCord-.+-windows-x64\.zip", a["name"])), None)
    if not archive:
        sys.exit(f"{latest['tag_name']} has no Windows archive.")
    runs = get("/actions/workflows/ci.yml/runs?branch=master&status=completed&per_page=1")["workflow_runs"]
    passing = bool(runs) and runs[0]["conclusion"] == "success"

    entries = []
    for release in stable[:CHANGELOG_RELEASES]:
        shown, iso = date_text(release["published_at"])
        version = release["tag_name"].lstrip("v")
        opened = " open" if release is latest else ""
        entries.append(
            f'<details class="release"{opened}><summary><span class="version">{html.escape(version)}</span>'
            f'<time datetime="{iso}">{shown}</time></summary>'
            f'<div class="notes">{notes_html(release["body"] or "", release["html_url"])}</div></details>')

    shown, iso = date_text(latest["published_at"])
    values = {
        "version": html.escape(latest["tag_name"].lstrip("v")),
        "release_url": html.escape(latest["html_url"]),
        "release_date": shown,
        "release_date_iso": iso,
        "release_date_short": short_date(latest["published_at"]),
        "download_url": html.escape(archive["browser_download_url"]),
        "download_size": size_text(archive["size"]),
        "disk_size": size_text(disk_size(archive)),
        "ci_state": "passing" if passing else "failing",
        "ci_class": "ok" if passing else "bad",
        # The workflow page, not the run: the page then changes only when the
        # status does, so hourly builds don't redeploy for every CI run.
        "ci_url": f"https://github.com/{REPO}/actions/workflows/ci.yml?query=branch%3Amaster",
        "changelog": "\n".join(entries),
        "theme_css": theme_tokens.css(),
    }

    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(ROOT, "site"), out)
    card.render(f"v{latest['tag_name'].lstrip('v')} · {values['release_date_short']} · "
                f"{values['download_size']} download · No Electron", os.path.join(out, "og.png"))
    card.touch_icon(os.path.join(out, "apple-touch-icon.png"))
    # The catalog pages come first: the home page and the sitemap take their navigation, shared CSS and
    # script, catalog section and page list from them.
    values.update(catalog_pages.build(out, catalog_data, values["theme_css"]))
    for name in TEMPLATES:
        page = os.path.join(out, name)
        with open(page, encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], text)
        with open(page, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    for line in catalog.warnings:
        print("catalog:", line)
    problems = check_site.check(out)
    if problems:
        sys.exit("The built site is inconsistent:\n" + "\n".join(problems))
    print(f"Built {len(catalog_data['items'])} catalog items ({'live' if catalog_data['live'] else 'fixture'})")
    print(f"Built {out}: {values['version']} ({values['release_date']}), CI {values['ci_state']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(ROOT, "_site"))
    parser.add_argument("--catalog", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--catalog-url", default=catalog.LIVE_URL)
    parser.add_argument("--catalog-key", default=os.environ.get("MAICORD_CATALOG_KEY"))
    parser.add_argument("--catalog-next-key", default=os.environ.get("MAICORD_CATALOG_NEXT_KEY"))
    args = parser.parse_args()
    try:
        data = catalog.load(args.catalog == "live", args.catalog_url, args.catalog_key, next_key_hex=args.catalog_next_key)
    except catalog.CatalogError as error:
        sys.exit(f"Catalog: {error}")
    build(args.out, data)
