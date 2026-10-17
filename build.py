#!/usr/bin/env python3
"""Builds the site: copies site/ to the output directory and fills the
{{placeholders}} in index.html with live data from the MaiCord repository
(latest release, its download, CI status and recent changelogs).

The output is deterministic for the same data, so the deploy workflow can
skip a deploy when nothing changed.

    python3 build.py [--out _site]

GITHUB_TOKEN, when set, raises the API rate limit; public data needs none.
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import sys
import urllib.request

REPO = "maj113/MaiCord"
API = "https://api.github.com/repos/" + REPO
CHANGELOG_RELEASES = 3
# Sections of generated release notes that the site leaves to GitHub: the
# long commit list and the per-release download boilerplate.
SKIPPED_SECTIONS = {"other", "download"}
ROOT = os.path.dirname(os.path.abspath(__file__))


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


def date_text(stamp):
    day = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{day:%B} {day.day}, {day.year}", day.strftime("%Y-%m-%d")


def short_date(stamp):
    day = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{day:%b} {day.day}, {day.year}"


def size_text(size):
    # Binary megabytes, labelled MB as Windows Explorer shows them.
    return f"{size / 1048576:.1f} MB"


def inline(text):
    """Escapes text and renders `code`, **bold** and [links](https://...)."""
    out, i = [], 0
    while i < len(text):
        if text[i] == "`":
            run = len(text[i:]) - len(text[i:].lstrip("`"))
            end = text.find("`" * run, i + run)
            if end > 0:
                out.append("<code>" + html.escape(text[i + run:end].strip()) + "</code>")
                i = end + run
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end > 0:
                out.append("<strong>" + inline(text[i + 2:end]) + "</strong>")
                i = end + 2
                continue
        link = re.match(r"\[([^\]]+)\]\((https://[^)\s]+)\)", text[i:])
        if link:
            out.append(f'<a href="{html.escape(link[2])}">{inline(link[1])}</a>')
            i += link.end()
            continue
        out.append(html.escape(text[i]))
        i += 1
    return "".join(out)


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


def build(out):
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
        "ci_state": "passing" if passing else "failing",
        "ci_class": "ok" if passing else "bad",
        # The workflow page, not the run: the page then changes only when the
        # status does, so hourly builds don't redeploy for every CI run.
        "ci_url": f"https://github.com/{REPO}/actions/workflows/ci.yml?query=branch%3Amaster",
        "changelog": "\n".join(entries),
    }

    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(ROOT, "site"), out)
    page = os.path.join(out, "index.html")
    with open(page, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], text)
    with open(page, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"Built {out}: {values['version']} ({values['release_date']}), CI {values['ci_state']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(ROOT, "_site"))
    build(parser.parse_args().out)
