#!/usr/bin/env python3
"""Copies the developer guides the site renders from a MaiCord checkout at a
commit and records the commit in guides/source.json:

    python3 sync_guides.py <MaiCord checkout> [commit]    # commit defaults to HEAD

The site builds from these copies (guides/), so a build never depends on the
network or on a moving branch, and the commit is the one the pages name.
Review the diff, then commit guides/ with the message "Update the developer guides to <short commit>".
"""
import json
import os
import subprocess
import sys

GUIDES = {
    "plugin-sdk.md": "include/maicord/sdk/README.md",
    "effects.md": "samples/effects/README.md",
}
ROOT = os.path.dirname(os.path.abspath(__file__))


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True).stdout


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    repo, ref = sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "HEAD"
    commit = git(repo, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    date = git(repo, "show", "-s", "--format=%cs", commit).decode().strip()
    os.makedirs(os.path.join(ROOT, "guides"), exist_ok=True)
    for name, path in GUIDES.items():
        text = git(repo, "show", f"{commit}:{path}").decode("utf-8").replace("\r\n", "\n")
        with open(os.path.join(ROOT, "guides", name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    with open(os.path.join(ROOT, "guides", "source.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"repository": "maj113/MaiCord", "commit": commit, "date": date, "files": GUIDES}, f, indent=2)
        f.write("\n")
    print(f"Copied {len(GUIDES)} guides from {commit[:10]} ({date})")


if __name__ == "__main__":
    main()
