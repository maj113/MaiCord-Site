#!/usr/bin/env python3
"""Checks a built site (build.py runs it, or run it on a directory): every internal link, image, srcset
candidate, canonical and link-preview URL leads to a file the build wrote, every #fragment names an id on its
page, every page address is a clean directory URL (no .html, no index), and every sitemap entry exists.

    python3 check_site.py _site
"""
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

SITE = "https://maicord.com/"
LINKS = {"a": "href", "link": "href", "img": "src", "source": "srcset", "script": "src"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.refs = set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "meta" and attrs.get("property") in ("og:image", "og:url"):
            self.refs.append(attrs["content"])
        key = LINKS.get(tag)
        if key and key in attrs and not (tag == "link" and attrs.get("rel") in ("preconnect", "dns-prefetch")):
            if key == "srcset":
                self.refs += [c.split()[0] for c in attrs["srcset"].split(",") if c.strip()]
            else:
                self.refs.append(attrs[key])
        if tag == "img" and "srcset" in attrs:
            self.refs += [c.split()[0] for c in attrs["srcset"].split(",") if c.strip()]


def parse(path, cache):
    if path not in cache:
        page = Page()
        with open(path, encoding="utf-8") as f:
            page.feed(f.read())
        cache[path] = page
    return cache[path]


def check(out):
    errors, cache = [], {}
    pages = [os.path.join(d, n) for d, _, names in os.walk(out) for n in names if n.endswith(".html")]
    for page in sorted(pages):
        here = "/" + os.path.relpath(page, out).replace(os.sep, "/")
        directory = here.rsplit("/", 1)[0] + "/"
        # 404.html is served for any address, so its links must not depend on where it was reached.
        for ref in parse(page, cache).refs:
            if re.match(r"(mailto:|maicord:|data:|javascript:)", ref) or (re.match(r"https?://", ref) and not ref.startswith(SITE)):
                continue
            url = urllib.parse.urlsplit(ref.replace(SITE, "/", 1) if ref.startswith(SITE) else ref)
            if here == "/404.html" and url.path and not url.path.startswith("/"):
                errors.append(f"{here}: relative link {ref} breaks below the root")
                continue
            target = urllib.parse.unquote(url.path) if url.path.startswith("/") else urllib.parse.unquote(
                os.path.normpath(os.path.join(directory, url.path)).replace(os.sep, "/")) if url.path else here
            if url.path and url.path.endswith("/") and not target.endswith("/"):
                target += "/"
            if url.path and target.endswith(".html") and not target.endswith("404.html"):
                errors.append(f"{here}: {ref} is not a clean address")
            file = os.path.join(out, target.lstrip("/"))
            if target.endswith("/"):
                file = os.path.join(file, "index.html")
            if not os.path.isfile(file):
                errors.append(f"{here}: {ref} leads nowhere")
            elif url.fragment and file.endswith(".html") and url.fragment not in parse(file, cache).ids:
                errors.append(f"{here}: {ref} names no id on the page")
    sitemap = os.path.join(out, "sitemap.xml")
    if os.path.isfile(sitemap):
        for loc in ET.parse(sitemap).getroot().iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if not loc.text.startswith(SITE) or not os.path.isfile(os.path.join(out, loc.text[len(SITE):], "index.html")):
                errors.append(f"sitemap.xml: {loc.text} is not a page of this build")
    return errors


if __name__ == "__main__":
    problems = check(sys.argv[1])
    print("\n".join(problems) if problems else "Links, images and sitemap are consistent.")
    sys.exit(1 if problems else 0)
