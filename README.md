# MaiCord website

The website for [MaiCord](https://github.com/maj113/MaiCord), a lightweight,
native Discord client for Windows: https://maicord.com/

Static HTML and inline CSS, no web fonts, and one inline script per page for
the theme picker and the backdrop (plus the filters, the copy button and the
install hint on the catalog pages). Every page is readable without scripts.
The picker keeps the chosen theme in `localStorage` under `theme` and nothing
else. The backdrop's stars and comets are MaiCord's own effect shader ported to
WebGL 2; without scripts the page shows the default theme with static stars.
The theme colours come from `theme_tokens.py`, a port of the client's theme
maths: run it to print the CSS and a contrast table.

The pages:

- `/`: `site/index.html`, a template. `build.py` fills its `{{placeholders}}`
  with the latest release, its download, CI status and recent changelogs from
  the GitHub API, and with the catalog section and navigation below. The size
  on disk is summed from the release zip's directory, read with HTTP range
  requests.
- `/plugins`, `/themes`, `/effects` and a detail page per item, `/plugins/develop`
  and `/effects/develop` (the developer guides) and `404.html`: generated from
  MaiCord's signed catalog and the guides. `CATALOG.md` describes them.
- The backdrop and theme-picker script (`catalog-assets/site.js`) and the
  frame CSS (`catalog-assets/chrome.css`: focus rings, skip link, navigation,
  picker, backdrop) are shared by the home page and the catalog pages;
  `build.py` places them into both, so there is one copy of each.

`card.py` draws the link preview cards with the bundled Inter fonts (SIL Open
Font License, `fonts/OFL.txt`): `og.png` with the latest release details
(~9 KB), the `apple-touch-icon.png`, and one card per catalog page with its
name, kind, summary and preview. `images.py` makes AVIF variants of the
catalog's PNG previews and loops. The finished site goes to `_site/`. Preview
it locally:

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python build.py   # then open _site/index.html

A full build takes about 45 seconds, nearly all of it AVIF encoding. The build
fails when a link, image, `srcset` candidate, `#fragment` or sitemap entry of
the result leads nowhere (`check_site.py`, which also runs on its own:
`python3 check_site.py _site`).

`site/screenshots/` holds renderer captures from MaiCord's opt-in showcase
probe (`tests/integration/showcase_probe.cpp`) with invented data, as AVIF at
1x and 2x. The hero is an animated AVIF loop (`hero-live`) whose first frame is
the still shown for reduced motion. Shots are 1440x900 DIPs of a window with
8 DIP corners, so the page scales the corner radius with the picture.

`guides/` holds copies of MaiCord's SDK guide
(`include/maicord/sdk/README.md`) and effect guide
(`samples/effects/README.md`), and `guides/source.json` the MaiCord commit they
were copied at; `guide.py` renders them at build time. The pages name that
commit, so a change to the guides in the MaiCord repository reaches the site
only when you refresh them:

    python3 sync_guides.py ../MaiCord [commit]     # then commit guides/

The renderer reads the guides' Markdown subset (headings, lists, tables, fenced
code, `code`, bold, italic, https links) and nothing else. `GUIDES` in
`catalog_pages.py` names the section ids the "jump to" chips link to; the build
fails if a guide drops one of them.

`.github/workflows/pages.yml` builds and deploys on every push to `master` and
checks hourly for new releases or CI results, deploying only when the page
changed (Settings > Pages > Source: GitHub Actions). The custom domain is set
in Settings > Pages.

The update channels the client polls are served separately, from the MaiCord
repository's own Pages site at `maj113.github.io/MaiCord/`, and are not part
of this repository. Keep custom domains off the MaiCord repository and off any
`maj113.github.io` user site: the client fetches updates only from that
address, and a redirect there would stop updates for every installed client.

## Release checklist (0.6.0)

Until the release the catalog pages are built from the sample catalog
(`catalog-fixture.json`, signed with a throwaway key): they say so, they are
`noindex`, and the sitemap leaves them out. To publish the real catalog:

1. The catalog repository (`maj113/MaiCord-plugins`) has published its signed
   index to `https://maj113.github.io/MaiCord-plugins/` (`index.json`,
   `index.json.sig`, `details/`, `previews/`).
2. In this repository's Settings > Secrets and variables > Actions > Variables,
   add both `MAICORD_PLUGIN_CATALOG_PUBLIC_KEY` and
   `MAICORD_PLUGIN_CATALOG_NEXT_PUBLIC_KEY`: the 130 hex digits of the catalog's
   current and next public keys, the same values MaiCord is built with. The build
   accepts a signature under either, as the client does, so a key rotation never
   stops the deploy. Variables are per repository: set them here as well as in
   the catalog repository. The build fails without the first and warns without
   the second. `python3 test_catalog_keys.py` checks the rule offline and runs in
   the workflow before every build.
3. Rehearse: Actions > Deploy > Run workflow with catalog `live` and Deploy off.
   The run builds against the live catalog, verifies its signature and checks
   every link, and publishes nothing. A bad signature, an expired index, a
   missing key or a broken link fails it.
4. Flip the switch: change `'fixture'` to `'live'` in the `CATALOG:` line of
   `.github/workflows/pages.yml` (or set the repository variable
   `MAICORD_SITE_CATALOG` to `live`, which needs no commit).
5. Merge to `master`. The push deploys, and the hourly runs keep the pages
   current from then on. Check `https://maicord.com/plugins/`: no sample-data
   note, and `https://maicord.com/sitemap.xml` lists the listings and every
   item.
6. Later, delete `catalog-fixture.json`, `catalog-fixture/` and the fixture
   notes in `catalog_pages.py` and `CATALOG.md`, once nothing needs them.
7. Refresh the developer guides if MaiCord's changed since
   `guides/source.json` (`sync_guides.py`, above), and check that the home page
   still shows its chosen items: `HOME_PLUGINS` and `HOME_EFFECTS` in
   `catalog_pages.py`. An item the catalog no longer lists is left out, with a
   warning in the build log.
8. Publish MaiCord 0.6.0 before the flip, or with it: the home page's download
   is the latest stable release, and an older client cannot install from the
   catalog pages.

The slug `develop` is reserved: `/plugins/develop` and `/effects/develop` are
the guides, so the build fails on a catalog item with that slug. The catalog
repository should refuse it too.
