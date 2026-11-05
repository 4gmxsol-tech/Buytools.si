#!/usr/bin/env python3
"""Dependency-light structural, SEO, internal-link and inline-JavaScript checks."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from site_validation import fragment_target_exists, has_shared_favicon

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://buytools.si"
ERRORS = []
WARNINGS = []


def fail(message):
    ERRORS.append(message)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.in_title = False
        self.lang = None
        self.description = None
        self.viewport = False
        self.canonicals = []
        self.icons = []
        self.og_urls = []
        self.hrefs = []
        self.ids = []
        self.inline_scripts = []
        self._script_parts = None
        self._script_type = None
        self._script_src = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            if attrs.get("name", "").lower() == "description":
                self.description = attrs.get("content", "").strip() or self.description
            if attrs.get("name", "").lower() == "viewport":
                self.viewport = True
            if attrs.get("property", "").lower() == "og:url":
                self.og_urls.append(attrs.get("content", "").strip())
        elif tag == "link":
            rel_tokens = attrs.get("rel", "").lower().split()
            if "canonical" in rel_tokens:
                self.canonicals.append(attrs.get("href", "").strip())
            if "icon" in rel_tokens:
                self.icons.append(attrs.get("href", "").strip())
        elif tag == "a" and attrs.get("href") is not None:
            self.hrefs.append(attrs["href"].strip())
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "script":
            self._script_parts = []
            self._script_type = attrs.get("type", "").lower()
            self._script_src = attrs.get("src")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self._script_parts is not None:
            if not self._script_src and self._script_type not in ("application/ld+json", "application/json", "importmap"):
                self.inline_scripts.append("".join(self._script_parts))
            self._script_parts = None
            self._script_type = None
            self._script_src = None

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self._script_parts is not None:
            self._script_parts.append(data)


def expected_url(file):
    rel = file.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return DOMAIN + "/"
    if rel.endswith("/index.html"):
        return DOMAIN + "/" + rel[:-len("index.html")]
    return DOMAIN + "/" + rel


def local_file_for_url(url):
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path == "/":
        candidate = ROOT / "index.html"
    elif path.endswith("/"):
        candidate = ROOT / path.lstrip("/") / "index.html"
    else:
        candidate = ROOT / path.lstrip("/")
        if not candidate.is_file() and not Path(path).suffix:
            candidate = ROOT / path.lstrip("/") / "index.html"
    return candidate


# Require the shared favicon asset used by every public page.
if not (ROOT / "assets" / "favicon.svg").is_file():
    fail("Shared SVG favicon asset is missing: assets/favicon.svg")

# Parse sitemap and require exact coverage of all indexable HTML pages.
sitemap_path = ROOT / "sitemap.xml"
try:
    sitemap_root = ET.parse(sitemap_path).getroot()
    sitemap_urls = [node.text.strip() for node in sitemap_root.findall(".//{*}loc") if node.text]
except (ET.ParseError, OSError) as exc:
    fail(f"sitemap.xml cannot be parsed: {exc}")
    sitemap_urls = []

seen_urls = set()
for url in sitemap_urls:
    if url in seen_urls:
        fail(f"Duplicate sitemap URL: {url}")
    seen_urls.add(url)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "buytools.si" or parsed.query or parsed.fragment:
        fail(f"Unexpected sitemap URL format: {url}")
        continue
    target = local_file_for_url(url)
    if not target.is_file():
        fail(f"Sitemap URL has no matching static file: {url}")

html_files = sorted(
    file for file in ROOT.rglob("*.html")
    if file.name != "404.html" and not any(part.startswith(".") for part in file.relative_to(ROOT).parts)
)
expected_sitemap = {expected_url(file) for file in html_files}
for missing in sorted(expected_sitemap - seen_urls):
    fail(f"Public HTML page missing from sitemap: {missing}")
for extra in sorted(seen_urls - expected_sitemap):
    fail(f"Sitemap URL has no matching public HTML page: {extra}")

all_parsers = {}
for file in html_files:
    rel = file.relative_to(ROOT).as_posix()
    parser = PageParser()
    try:
        parser.feed(file.read_text(encoding="utf-8"))
        parser.close()
    except (OSError, UnicodeError, Exception) as exc:
        fail(f"Cannot parse {rel}: {exc}")
        continue
    all_parsers[file] = parser
    title = "".join(parser.title_parts).strip()
    if not title:
        fail(f"Missing/empty title: {rel}")
    elif len(title) > 75:
        WARNINGS.append(f"Long title ({len(title)} chars): {rel}")
    if not parser.description:
        fail(f"Missing meta description: {rel}")
    elif len(parser.description) > 180:
        WARNINGS.append(f"Long meta description ({len(parser.description)} chars): {rel}")
    if not parser.lang:
        fail(f"Missing html lang attribute: {rel}")
    if not parser.viewport:
        fail(f"Missing viewport meta: {rel}")

    canonical = expected_url(file)
    if parser.canonicals != [canonical]:
        fail(f"Canonical must exactly match {canonical}; found {parser.canonicals}: {rel}")
    if not has_shared_favicon(parser.icons):
        fail(f"Missing shared SVG favicon /assets/favicon.svg: {rel}")
    if parser.og_urls and parser.og_urls != [canonical]:
        fail(f"og:url must match canonical {canonical}; found {parser.og_urls}: {rel}")

    if len(parser.ids) != len(set(parser.ids)):
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        fail(f"Duplicate HTML id(s) {duplicates}: {rel}")

# Validate static internal links and fragment targets.
fragment_links_checked = 0
for file, parser in all_parsers.items():
    page_url = expected_url(file)
    for href in parser.hrefs:
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        resolved = urljoin(page_url, href)
        parsed = urlparse(resolved)
        if parsed.scheme not in ("http", "https") or parsed.netloc != "buytools.si":
            continue
        target = local_file_for_url(resolved)
        if not target.is_file():
            fail(f"Broken internal link in {file.relative_to(ROOT)}: {href}")
            continue
        target_parser = all_parsers.get(target)
        if parsed.fragment and target_parser:
            fragment_links_checked += 1
            if not fragment_target_exists(parsed.fragment, target_parser.ids):
                fail(
                    f"Broken internal anchor in {file.relative_to(ROOT)}: {href} "
                    f"(target {target.relative_to(ROOT)})"
                )

# Every indexable tool and guide landing page must be reachable from a crawlable homepage link.
homepage_parser = all_parsers.get(ROOT / "index.html")
homepage_discovery_links = set()
if homepage_parser:
    for href in homepage_parser.hrefs:
        resolved = urljoin(DOMAIN + "/", href)
        parsed = urlparse(resolved)
        if parsed.scheme == "https" and parsed.netloc == "buytools.si" and not parsed.query and not parsed.fragment:
            homepage_discovery_links.add(resolved)
for url in sitemap_urls:
    if urlparse(url).path.startswith(("/tools/", "/guides/")) and url not in homepage_discovery_links:
        fail(f"Public tool/guide page is not linked from homepage: {url}")

# Check that each homepage catalogue ID has a corresponding tool renderer branch.
home = (ROOT / "index.html").read_text(encoding="utf-8")
privacy_text = (ROOT / "privacy/index.html").read_text(encoding="utf-8")

# Keep privacy disclosures synchronized with third-party requests in the homepage tool code.
dynamic_import_urls = re.findall(r"""import\(['"](https?://[^'"]+)['"]\)""", home)
for dependency_url in dynamic_import_urls:
    if dependency_url not in privacy_text:
        fail(f"Third-party library import missing from privacy policy: {dependency_url}")
for host in ("api.qrserver.com", "staticimgly.com"):
    if host not in privacy_text:
        fail(f"Third-party processing or asset host missing from privacy policy: {host}")
if "buytools-theme" not in privacy_text:
    fail("Browser theme storage key is not disclosed in the privacy policy.")
catalogue_start = home.find("const tools=[")
catalogue_end = home.find("\n];", catalogue_start)
renderer_start = home.find("function toolMarkup(id)")
renderer_end = home.find("function wireTool(id)", renderer_start)
if min(catalogue_start, catalogue_end, renderer_start, renderer_end) < 0:
    fail("Could not locate the homepage tool catalogue or renderer.")
else:
    catalogue = home[catalogue_start:catalogue_end]
    renderer = home[renderer_start:renderer_end]
    tool_ids = re.findall(r"\{id:'([^']+)'", catalogue)
    for tool_id in tool_ids:
        if tool_id not in renderer:
            fail(f"Homepage tool has no renderer mapping: {tool_id}")
    if len(tool_ids) != len(set(tool_ids)):
        fail("Homepage tool catalogue contains duplicate IDs.")

# Syntax-check inline JavaScript with Node.js when available.
node = shutil.which("node")
if node:
    for file, parser in all_parsers.items():
        for index, script in enumerate(parser.inline_scripts, start=1):
            if not script.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as temp:
                temp.write(script)
                temp.flush()
                result = subprocess.run([node, "--check", temp.name], capture_output=True, text=True)
            if result.returncode:
                detail = (result.stderr or result.stdout).strip().splitlines()
                fail(f"Inline JavaScript syntax error in {file.relative_to(ROOT)} (script {index}): {detail[-1] if detail else 'unknown error'}")
else:
    WARNINGS.append("Node.js unavailable; inline JavaScript syntax checks skipped.")

# robots.txt must point to the sitemap that is actually shipped.
robots = ROOT / "robots.txt"
if not robots.is_file() or "Sitemap: " + DOMAIN + "/sitemap.xml" not in robots.read_text(encoding="utf-8"):
    fail("robots.txt must reference https://buytools.si/sitemap.xml")

if ERRORS:
    print("Site checks FAILED:")
    for error in ERRORS:
        print(" - " + error)
    if WARNINGS:
        print("Warnings:")
        for warning in WARNINGS:
            print(" - " + warning)
    sys.exit(1)

print(
    f"Site checks passed: {len(html_files)} public HTML pages, "
    f"{len(sitemap_urls)} sitemap URLs, exact canonicals, internal links, "
    f"{len(homepage_discovery_links)} homepage tool/guide discovery links, "
    f"{fragment_links_checked} internal fragment links, "
    "tool renderer mappings and inline JavaScript syntax."
)
if WARNINGS:
    print("Warnings:")
    for warning in WARNINGS:
        print(" - " + warning)
