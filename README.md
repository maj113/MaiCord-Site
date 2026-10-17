# MaiCord website

The website for [MaiCord](https://github.com/maj113/MaiCord), a lightweight,
native Discord client for Windows: https://maicord.com/

One static page: HTML and inline CSS, no scripts and no web fonts.
`site/index.html` is a template: `build.py` fills its `{{placeholders}}` with
the latest release, its download, CI status and recent changelogs from the
GitHub API, and `card.py` draws the link preview card (`og.png`) with the same
release details as a ~13 KB palette PNG, using the bundled Inter fonts in
`fonts/` (SIL Open Font License, `fonts/OFL.txt`). The finished site goes to
`_site/`. Preview it locally:

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python build.py   # then open _site/index.html

`.github/workflows/pages.yml` builds and deploys on every push to `master` and
checks hourly for new releases or CI results, deploying only when the page
changed (Settings > Pages > Source: GitHub Actions). The custom domain is set
in Settings > Pages.

The update channels the client polls are served separately, from the MaiCord
repository's own Pages site at `maj113.github.io/MaiCord/`, and are not part
of this repository. Keep custom domains off the MaiCord repository and off any
`maj113.github.io` user site: the client fetches updates only from that
address, and a redirect there would stop updates for every installed client.
