#!/usr/bin/env python3
"""Add the shared BuyTools ad engine to eligible static HTML pages at build time."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SKIP = {"privacy", "terms", "licenses"}
TAG = '<script defer src="/assets/buytools-ads.js"></script>'
count = 0
for page in ROOT.rglob("*.html"):
    rel = page.relative_to(ROOT)
    if rel.parts and rel.parts[0] in SKIP:
        continue
    source = page.read_text(encoding="utf-8")
    if TAG in source:
        continue
    if "</body>" not in source.lower():
        raise SystemExit(f"Cannot inject ad engine: missing </body> in {rel}")
    pos = source.lower().rfind("</body>")
    source = source[:pos] + TAG + "\n" + source[pos:]
    page.write_text(source, encoding="utf-8")
    count += 1
print(f"Ad engine injected into {count} eligible HTML pages.")
