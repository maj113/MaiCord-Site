#!/usr/bin/env python3
"""Self-check for the live catalog's key handling (catalog.load): a signature is
accepted under the current key or the next one, as the client accepts it, so a
key rotation never stops the deploy. Runs offline against the fixture's signed
index (signed by its throwaway key), with the public key stand-ins below:

    python3 test_catalog_keys.py
"""
import os
import sys

import catalog
import p256

with open(os.path.join(catalog.FIXTURE_DIR, "public-key.txt"), encoding="ascii") as f:
    SIGNER = f.read().strip()
# The generator point: a valid P-256 public key that did not sign the fixture.
OTHER = (b"\x04" + p256.G[0].to_bytes(32, "big") + p256.G[1].to_bytes(32, "big")).hex()


class FixtureSource(catalog.Source):
    """Serves the fixture's files as if they were live: only the key handling is under test."""

    def __init__(self, live, url=catalog.LIVE_URL):
        super().__init__(False)


catalog.Source = FixtureSource
catalog.parse = lambda document, source, now: {"items": [], "sequence": 1, "issued": 1, "expires": 2}


def loads(current, next_key=None):
    return catalog.load(True, "https://example.invalid/", current, next_key_hex=next_key)["live"]


def refuses(message, *args):
    try:
        loads(*args)
    except catalog.CatalogError as error:
        assert message in str(error), f"{error!r} does not mention {message!r}"
        return
    raise AssertionError(f"accepted, expected a refusal mentioning {message!r}")


def main():
    assert loads(SIGNER), "current key"
    assert loads(SIGNER, OTHER), "current key, another next key"
    assert loads(OTHER, SIGNER), "rotation: signed by the next key"
    assert loads(SIGNER, ""), "an unset next-key variable is ignored"
    assert loads(SIGNER, "  \n"), "a blank next-key variable is ignored"
    assert loads(f"  {SIGNER}\n", f"{OTHER}\r\n"), "whitespace around keys is ignored"
    refuses("under the catalog public key", OTHER)
    refuses("under the catalog public key", OTHER, "")
    refuses("the current or the next catalog public key", OTHER, OTHER)
    refuses("the next catalog public key is not hex", SIGNER, "not hex")
    refuses("the catalog public key is not hex", "zz", SIGNER)
    refuses("needs its public key", None, SIGNER)
    refuses("needs its public key", "", SIGNER)
    print("Catalog key handling: ok")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        sys.exit(f"Catalog key handling: FAILED: {error}")
