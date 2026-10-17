# MaiCord website

The website for [MaiCord](https://github.com/maj113/MaiCord), a lightweight,
native Discord client for Windows: https://maicord.com/

One static page: HTML and inline CSS, no scripts and no web fonts.
`site/index.html` is a template: `build.py` (Python standard library only)
fills its `{{placeholders}}` with the latest release, its download, CI status
and recent changelogs from the GitHub API, writing the finished site to
`_site/`. Preview it locally with `python3 build.py` and open
`_site/index.html`.

`.github/workflows/pages.yml` builds and deploys on every push to `master` and
checks hourly for new releases or CI results, deploying only when the page
changed (Settings > Pages > Source: GitHub Actions). The custom domain is set
in Settings > Pages.

The update channels the client polls are served separately, from the MaiCord
repository's own Pages site at `maj113.github.io/MaiCord/`, and are not part
of this repository. Keep custom domains off the MaiCord repository and off any
`maj113.github.io` user site: the client fetches updates only from that
address, and a redirect there would stop updates for every installed client.
