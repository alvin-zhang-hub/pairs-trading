"""Generate a static HTML version of the scanner page for GitHub Pages.

Reads `lighthouse/output/scanner_cache.json` and writes `docs/index.html` at
the repo root. GH Pages serves `docs/` from the main branch (one-time setting
in repo Settings → Pages).

Idempotent and stateless — safe to run after every scan.
"""
from __future__ import annotations

import argparse
import os
import sys

from lighthouse.dashboard_view import render_scanner_page

# Resolve relative to the lighthouse package so this works from any CWD.
_LIGHTHOUSE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_LIGHTHOUSE_DIR, "..", ".."))

DEFAULT_CACHE = os.path.join(_LIGHTHOUSE_DIR, "output", "scanner_cache.json")
DEFAULT_OUTPUT = os.path.join(_REPO_ROOT, "docs", "index.html")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build static scanner site")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="path to scanner_cache.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="path to write index.html")
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    html = render_scanner_page(args.cache, filters=None)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"wrote {len(html):,} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
