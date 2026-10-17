# MaiCord website

The website for [MaiCord](https://github.com/maj113/MaiCord), a lightweight,
native Discord client for Windows: https://maicord.com/

One static page in `site/`: HTML and inline CSS, no scripts, no web fonts, no
build step. `.github/workflows/pages.yml` publishes `site/` as is on every
push to `master` (Settings > Pages > Source: GitHub Actions). The custom domain
is set in Settings > Pages.

The update channels the client polls are served separately, from the MaiCord
repository's own Pages site at `maj113.github.io/MaiCord/`, and are not part
of this repository. Keep custom domains off the MaiCord repository and off any
`maj113.github.io` user site: the client fetches updates only from that
address, and a redirect there would stop updates for every installed client.
