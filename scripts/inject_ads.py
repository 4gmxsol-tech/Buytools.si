#!/usr/bin/env python3
"""Add the shared BuyTools ad engine to eligible static HTML pages at build time."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"privacy", "terms", "licenses"}
TAG = '<script defer src="/assets/buytools-ads.js"></script>'


def inject_ads(root=ROOT):
    """Inject the consent-aware engine once per eligible page and validate placement."""
    root = Path(root)
    if not (root / "assets" / "buytools-ads.js").is_file():
        raise ValueError("Consent-aware ad engine is missing: assets/buytools-ads.js")

    injected = 0
    eligible = 0
    for page in sorted(root.rglob("*.html")):
        relative = page.relative_to(root)
        if relative.parts and relative.parts[0] in SKIP:
            continue

        eligible += 1
        source = page.read_text(encoding="utf-8")
        lower = source.lower()
        body_close = lower.rfind("</body>")
        if body_close < 0:
            raise ValueError(f"Cannot inject ad engine: missing </body> in {relative}")
        if source.count(TAG) > 1:
            raise ValueError(f"Duplicate ad-engine tags found in {relative}")

        if TAG not in source:
            source = source[:body_close] + TAG + chr(10) + source[body_close:]
            page.write_text(source, encoding="utf-8")
            injected += 1

        lower = source.lower()
        tag_position = lower.rfind(TAG.lower())
        body_position = lower.rfind("</body>")
        if source.count(TAG) != 1 or tag_position < 0 or tag_position > body_position:
            raise ValueError(f"Ad engine must appear exactly once before </body> in {relative}")

    return injected, eligible


def main():
    injected, eligible = inject_ads()
    print(
        f"Ad engine injection verified on {eligible} eligible HTML pages; "
        f"{injected} newly injected."
    )


if __name__ == "__main__":
    main()
