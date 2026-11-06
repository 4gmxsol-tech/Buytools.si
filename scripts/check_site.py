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

from site_validation import fragment_target_exists, has_shared_favicon, missing_image_compressor_disclosures, missing_csv_export_safety_disclosures, missing_json_file_workflow_disclosures, missing_batch_image_resizer_disclosures

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

# Keep the JSON formatter and its practical guide mutually discoverable.
json_tool_parser = all_parsers.get(ROOT / "tools/json-formatter/index.html")
json_guide_parser = all_parsers.get(ROOT / "guides/format-json-online/index.html")
if json_tool_parser and "/guides/format-json-online/" not in json_tool_parser.hrefs:
    fail("JSON Formatter landing page must link to the practical JSON formatting guide.")
if json_guide_parser and "/tools/json-formatter/" not in json_guide_parser.hrefs:
    fail("JSON formatting guide must link to the JSON Formatter landing page.")

json_guide_html = (ROOT / "guides/format-json-online/index.html").read_text(encoding="utf-8")
missing_json_workflow = missing_json_file_workflow_disclosures(json_guide_html)
if missing_json_workflow:
    fail("JSON guide is missing practical local-file workflow details: " + ", ".join(missing_json_workflow))

# Keep the image guide aligned with the actual compressor output contract.
image_guide = (ROOT / "guides/reduce-image-size/index.html").read_text(encoding="utf-8")
missing_image_disclosures = missing_image_compressor_disclosures(image_guide)
if missing_image_disclosures:
    fail("Image guide is missing accurate compressor disclosures: " + ", ".join(missing_image_disclosures))

# Keep the batch image resizer metadata and output explanation aligned with its PNG implementation.
batch_image_resizer_page = (ROOT / "tools/batch-image-resizer/index.html").read_text(encoding="utf-8")
missing_batch_resizer_disclosures = missing_batch_image_resizer_disclosures(batch_image_resizer_page)
if missing_batch_resizer_disclosures:
    fail("Batch image resizer page is inaccurate or incomplete: " + ", ".join(missing_batch_resizer_disclosures))

# Check that each homepage catalogue ID has a corresponding tool renderer branch.
home = (ROOT / "index.html").read_text(encoding="utf-8")
csv_viewer_page = (ROOT / "tools/csv-viewer/index.html").read_text(encoding="utf-8")
csv_converter_page = (ROOT / "tools/csv-json-converter/index.html").read_text(encoding="utf-8")
for page_path, page_html in (
    ("tools/csv-viewer/index.html", csv_viewer_page),
    ("tools/csv-json-converter/index.html", csv_converter_page),
):
    missing_csv_disclosures = missing_csv_export_safety_disclosures(page_html)
    if missing_csv_disclosures:
        fail(f"CSV export safety disclosure missing from {page_path}: " + ", ".join(missing_csv_disclosures))
if (
    "function spreadsheetSafeCsvCell(value)" not in home
    or "spreadsheetSafeCsvCell(v)" not in home
    or "spreadsheetSafeCsvCell(str)" not in home
):
    fail("Both CSV export paths must use the shared spreadsheet formula-injection safeguard.")
if 'id="csvFile"' not in home or "maxCsvFileBytes=5*1024*1024" not in home or "readCsvFileText(file)" not in home:
    fail("CSV Viewer must read selected local CSV files in-browser with a 5 MiB size guard.")
if (
    "async function readCsvFileText(file)" not in home
    or "new TextDecoder('utf-16le')" not in home
    or "new TextDecoder('utf-16be')" not in home
):
    fail("CSV Viewer must decode UTF-16LE and UTF-16BE files when a byte-order mark is present.")
if "UTF-16LE BOM" not in csv_viewer_page or "UTF-16BE BOM" not in csv_viewer_page:
    fail("CSV Viewer landing page must disclose its supported UTF-16 BOM encodings.")
if (
    'id="csvDelimiter"' not in home
    or "function parseCSV(input,delimiter=',')" not in home
    or "parseCSV(text.value,$('#csvDelimiter').value)" not in home
    or "Choose comma, semicolon or tab" not in home
):
    fail("CSV Viewer must expose and use an explicit comma, semicolon or tab field-separator control.")
if "comma-, semicolon- and tab-separated values" not in csv_viewer_page or "normalized to comma-separated CSV" not in csv_viewer_page:
    fail("CSV Viewer landing page must disclose supported import separators and comma-normalized exports.")
if "Choose a .csv file up to 5 MiB" not in csv_viewer_page or "not uploaded to a processing server" not in csv_viewer_page:
    fail("CSV Viewer landing page must accurately disclose local file selection and its size limit.")
if "Open comma-, semicolon- or tab-delimited CSV files" not in csv_viewer_page or "Open local CSV files up to 5 MiB with the browser File API" not in csv_viewer_page:
    fail("CSV Viewer metadata must describe supported field separators and local file selection accurately.")

privacy_text = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
if "CSV Viewer" not in privacy_text or "5 MiB" not in privacy_text or "browser File API" not in privacy_text or "not uploaded to a BuyTools.si processing endpoint" not in privacy_text:
    fail("Privacy policy must describe local CSV file reading and the 5 MiB limit.")

# Keep privacy disclosures synchronized with third-party requests in the homepage tool code.
dynamic_import_urls = re.findall(r"""import\(['"](https?://[^'"]+)['"]\)""", home)
for dependency_url in dynamic_import_urls:
    if dependency_url not in privacy_text:
        fail(f"Third-party library import missing from privacy policy: {dependency_url}")
for host in ("api.qrserver.com", "staticimgly.com"):
    if host not in privacy_text:
        fail(f"Third-party processing or asset host missing from privacy policy: {host}")
qr_notice_requirements = (
    'for="text"',
    'aria-describedby="qrPrivacyNotice"',
    'id="qrPrivacyNotice"',
    'sent to QRServer',
    'Do not enter passwords',
    'href="/privacy/"',
)
if any(requirement.lower() not in home.lower() for requirement in qr_notice_requirements):
    fail("QR generator must show an accessible, tool-level disclosure before text is sent to the third-party QR service.")
if "buytools-theme" not in privacy_text:
    fail("Browser theme storage key is not disclosed in the privacy policy.")
if "at least 90.2 MiB" not in home or "at least 90.2 MiB" not in (ROOT / "tools/remove-background/index.html").read_text(encoding="utf-8"):
    fail("Background-removal first-run model-size warning is missing from the workspace or landing page.")
if "94,553,445 bytes" not in privacy_text or "90.2 MiB" not in privacy_text:
    fail("Measured background-removal model download size is missing from the privacy policy.")
consent_key = "buytools-background-removal-consent-v1"
consent_gate = home.find("const consentKey='" + consent_key + "'")
model_import = home.find("const mod=await import('https://esm.sh/@imgly/background-removal@1.5.5')")
if consent_gate < 0 or model_import < 0 or consent_gate > model_import or "window.confirm(" not in home:
    fail("Background-removal model assets must be gated by explicit first-use consent before the third-party import.")
if consent_key not in privacy_text:
    fail("Temporary background-removal consent storage must be disclosed in the privacy policy.")
if "confirmation is shown before the first model download" not in (ROOT / "tools/remove-background/index.html").read_text(encoding="utf-8").lower():
    fail("Background-removal landing page must explain the first-use download confirmation.")
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
