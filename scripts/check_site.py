#!/usr/bin/env python3
"""Dependency-free static checks for BuyTools.si SEO and sitemap integrity."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://buytools.si"
errors = []

class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.title_text = []
        self.in_title = False
        self.description = False
        self.canonical = []
        self.lang = None
        self.viewport = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            if attrs.get("name") == "description" and attrs.get("content", "").strip():
                self.description = True
            if attrs.get("name") == "viewport":
                self.viewport = True
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href", ""))
    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            self.title = bool("".join(self.title_text).strip())
    def handle_data(self, data):
        if self.in_title:
            self.title_text.append(data)

def fail(message):
    errors.append(message)

sitemap = ROOT / "sitemap.xml"
try:
    tree = ET.parse(sitemap)
    urls = [node.text.strip() for node in tree.findall(".//{*}loc") if node.text]
except (ET.ParseError, OSError) as exc:
    fail(f"sitemap.xml cannot be parsed: {exc}")
    urls = []

seen = set()
for url in urls:
    if url in seen:
        fail(f"Duplicate sitemap URL: {url}")
    seen.add(url)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "buytools.si":
        fail(f"Unexpected sitemap host/protocol: {url}")
        continue
    path = parsed.path
    local = ROOT / ("index.html" if path in ("", "/") else path.lstrip("/") + ("index.html" if path.endswith("/") else ""))
    if not local.is_file():
        fail(f"Sitemap URL has no matching static file: {url} -> {local.relative_to(ROOT)}")

html_files = sorted(ROOT.rglob("*.html"))
canonical_map = {}
for file in html_files:
    if any(part.startswith(".") for part in file.relative_to(ROOT).parts):
        continue
    parser = MetadataParser()
    try:
        parser.feed(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        fail(f"Cannot read {file.relative_to(ROOT)}: {exc}")
        continue
    rel = file.relative_to(ROOT).as_posix()
    if not parser.title:
        fail(f"Missing/empty title: {rel}")
    if not parser.description:
        fail(f"Missing meta description: {rel}")
    if not parser.lang:
        fail(f"Missing html lang attribute: {rel}")
    if not parser.viewport:
        fail(f"Missing viewport meta: {rel}")
    if len(parser.canonical) != 1 or not parser.canonical[0].startswith(DOMAIN):
        fail(f"Expected exactly one absolute canonical URL: {rel}")
    elif parser.canonical[0] in canonical_map:
        fail(f"Duplicate canonical URL {parser.canonical[0]} in {rel} and {canonical_map[parser.canonical[0]]}")
    else:
        canonical_map[parser.canonical[0]] = rel

if not urls:
    fail("sitemap.xml contains no URLs")

if errors:
    print("Site checks FAILED:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print(f"Site checks passed: {len(html_files)} HTML files, {len(urls)} unique sitemap URLs, valid titles/descriptions/canonicals.")
