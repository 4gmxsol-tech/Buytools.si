#!/usr/bin/env python3
"""Dependency-light structural, SEO, internal-link and inline-JavaScript checks."""
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from site_validation import fragment_target_exists, has_shared_favicon, known_analytics_or_ad_markers, missing_advertising_consent_disclosure, missing_image_compressor_disclosures, missing_csv_export_safety_disclosures, missing_json_file_workflow_disclosures, missing_batch_image_resizer_disclosures, homepage_tool_count_mismatch, missing_image_lossless_workflow_disclosures, missing_image_reduction_workflow_steps, missing_json_schema_scope_disclosures, missing_json_scope_metadata_disclosures, missing_homepage_json_syntax_disclosure, missing_license_footer_link, missing_direct_browser_package_notices, missing_runtime_dependency_notices, missing_upstream_lock_evidence, missing_confirmed_bundled_license_notices, has_head_license_declaration, missing_sitemap_lastmod_sync, missing_article_date_modified_sync, noncanonical_internal_index_links, missing_pages_workflow_least_privilege, missing_immutable_action_pins, missing_csv_troubleshooting_guidance, faq_schema_mismatches

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
sitemap_root = None
try:
    sitemap_root = ET.parse(sitemap_path).getroot()
    sitemap_urls = [node.text.strip() for node in sitemap_root.findall(".//{*}loc") if node.text]
except (ET.ParseError, OSError) as exc:
    fail(f"sitemap.xml cannot be parsed: {exc}")
    sitemap_urls = []

# Validate optional lastmod values and require them for the recently updated homepage and resizer.
sitemap_entries = {}
if sitemap_root is not None:
    for entry in sitemap_root.findall(".//{*}url"):
        loc = entry.findtext("{*}loc")
        if not loc:
            continue
        loc = loc.strip()
        sitemap_entries[loc] = entry
        lastmod = entry.findtext("{*}lastmod")
        if lastmod:
            try:
                lastmod_date = date.fromisoformat(lastmod.strip())
            except ValueError:
                fail(f"Invalid sitemap lastmod date for {loc}: {lastmod!r}")
            else:
                if lastmod_date > date.today():
                    fail(f"Sitemap lastmod must not be in the future: {loc}")

for required_lastmod_url in (DOMAIN + "/", DOMAIN + "/tools/batch-image-compressor/", DOMAIN + "/tools/batch-image-resizer/", DOMAIN + "/tools/json-formatter/", DOMAIN + "/tools/word-counter/", DOMAIN + "/tools/images-to-pdf/", DOMAIN + "/guides/convert-images-to-pdf/", DOMAIN + "/guides/reduce-image-size/", DOMAIN + "/guides/format-json-online/", DOMAIN + "/privacy/", DOMAIN + "/tools/csv-viewer/"):
    entry = sitemap_entries.get(required_lastmod_url)
    if entry is None or not entry.findtext("{*}lastmod"):
        fail(f"Recently updated page is missing sitemap lastmod: {required_lastmod_url}")

word_counter_page = (ROOT / "tools/word-counter/index.html").read_text(encoding="utf-8")
homepage_word_counter_code = (ROOT / "index.html").read_text(encoding="utf-8")
if (
    "new Intl.Segmenter(undefined,{granularity:'grapheme'})" not in homepage_word_counter_code
    or "Array.from(value).length" not in homepage_word_counter_code
):
    fail("Homepage Word Counter must count grapheme clusters with a documented code-point fallback.")
for required_word_counter_disclosure in ("characters excluding whitespace", "spaces and line breaks", "Unicode grapheme clusters", "Older browsers fall back to Unicode code points"):
    if required_word_counter_disclosure not in word_counter_page:
        fail("Word Counter page is missing accurate character-count disclosure: " + required_word_counter_disclosure)

licenses_page_path = ROOT / "licenses" / "index.html"
if not licenses_page_path.is_file():
    fail("Third-party license notice page is missing: licenses/index.html")
else:
    licenses_page = licenses_page_path.read_text(encoding="utf-8")
    sitemap_content = sitemap_path.read_text(encoding="utf-8")
    lastmod_errors = missing_sitemap_lastmod_sync(
        sitemap_content,
        DOMAIN + "/licenses/",
        licenses_page,
    )
    for message in lastmod_errors:
        fail("Licenses sitemap lastmod is out of sync: " + message)
    if has_head_license_declaration(licenses_page):
        fail("Aggregate third-party license inventory must not declare one document-level license in the HTML head.")
    for required_notice in ("@imgly/background-removal", "1.5.5", "AGPL-3.0", "https://github.com/imgly/background-removal-js", "https://www.gnu.org/licenses/agpl-3.0.html", "pdf-lib", "1.17.1", "https://esm.sh/pdf-lib@1.17.1", "https://github.com/Hopding/pdf-lib/blob/v1.17.1/LICENSE.md", "JSZip", "3.10.2", "MIT or GPL-3.0", "https://esm.sh/jszip@3.10.2", "https://github.com/Stuk/jszip/blob/v3.10.2/LICENSE.markdown", "jsPDF", "4.2.1", "https://esm.sh/jspdf@4.2.1", "https://github.com/parallax/jsPDF/blob/v4.2.1/LICENSE"):
        if required_notice not in licenses_page:
            fail("Third-party license notice is missing required attribution: " + required_notice)
    runtime_manifest_path = ROOT / "audits" / "background-removal-runtime-baseline.json"
    if not runtime_manifest_path.is_file():
        fail("Background-removal runtime dependency baseline is missing: audits/background-removal-runtime-baseline.json")
    else:
        try:
            runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            fail("Background-removal runtime dependency baseline is not valid JSON: " + str(error))
        else:
            missing_runtime_notices = missing_runtime_dependency_notices(runtime_manifest, licenses_page)
            if missing_runtime_notices:
                fail("Background-removal runtime license inventory is incomplete: " + "; ".join(missing_runtime_notices))
            missing_upstream_evidence = missing_upstream_lock_evidence(runtime_manifest)
            if missing_upstream_evidence:
                fail("Background-removal upstream dependency evidence is incomplete: " + "; ".join(missing_upstream_evidence))
            missing_transitive_notices = missing_confirmed_bundled_license_notices(runtime_manifest, licenses_page)
            if missing_transitive_notices:
                fail("Background-removal transitive license notices are incomplete: " + "; ".join(missing_transitive_notices))
for linked_page in (ROOT / "privacy" / "index.html", ROOT / "tools" / "remove-background" / "index.html"):
    if 'href="/licenses/"' not in linked_page.read_text(encoding="utf-8"):
        fail("Relevant page must link to the third-party license notice: " + str(linked_page.relative_to(ROOT)))
homepage_html = (ROOT / "index.html").read_text(encoding="utf-8")
if '<nav class="footerlinks" aria-label="Legal">' not in homepage_html or '<a href="/licenses/">Licenses</a>' not in homepage_html:
    fail("Homepage legal footer must expose a crawlable link to the third-party license notice.")


csv_viewer_page_path = ROOT / "tools" / "csv-viewer" / "index.html"
if not csv_viewer_page_path.is_file():
    fail("CSV Viewer landing page is missing: tools/csv-viewer/index.html")
else:
    csv_viewer_html = csv_viewer_page_path.read_text(encoding="utf-8")
    for message in missing_csv_troubleshooting_guidance(csv_viewer_html):
        fail("CSV Viewer troubleshooting content is incomplete: " + message)
    for message in faq_schema_mismatches(csv_viewer_html):
        fail("CSV Viewer FAQ structured data is out of sync: " + message)
    for message in missing_sitemap_lastmod_sync(
        sitemap_path.read_text(encoding="utf-8"),
        DOMAIN + "/tools/csv-viewer/",
        csv_viewer_html,
    ):
        fail("CSV Viewer sitemap lastmod is out of sync: " + message)

# Keep the homepage search form aligned with its WebSite SearchAction URL template.
if '<form class="searchbox" id="toolSearch" role="search" action="/" method="get">' not in homepage_html:
    fail("Homepage tool search must use a semantic GET search form with the SearchAction endpoint.")
if '<input id="search" type="search" name="q" aria-label="Search tools"' not in homepage_html:
    fail("Homepage search input must expose the q parameter declared by SearchAction.")
for required_search_contract in (
    '"target":"https://buytools.si/?q={search_term_string}"',
    '"query-input":"required name=search_term_string"',
    "$('#toolSearch').addEventListener('submit'",
    "history.replaceState(null,'',url)",
):
    if required_search_contract not in homepage_html:
        fail("Homepage search form and SearchAction contract are out of sync: " + required_search_contract)

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
CORE_LICENSE_LINK_PAGES = (
    "guides/format-json-online/index.html",
    "guides/reduce-image-size/index.html",
    "tools/json-formatter/index.html",
    "tools/csv-viewer/index.html",
)
for relative_path in CORE_LICENSE_LINK_PAGES:
    page_path = ROOT / relative_path
    if not page_path.is_file():
        fail(f"Core landing page required for license discovery is missing: {relative_path}")
        continue
    message = missing_license_footer_link(page_path.read_text(encoding="utf-8"))
    if message:
        fail(f"{relative_path}: {message}")

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
    for alias in noncanonical_internal_index_links(parser.hrefs, expected_url(file)):
        fail(
            f"Internal link must use the canonical trailing-slash URL instead of an index.html alias: "
            f"{rel}: {alias}"
        )
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

# Keep every direct, version-pinned browser package import represented in the license inventory.
if licenses_page_path.is_file():
    site_html = "\n".join(file.read_text(encoding="utf-8") for file in html_files)
    missing_package_notices = missing_direct_browser_package_notices(site_html, licenses_page)
    if missing_package_notices:
        fail("Direct browser package license inventory is incomplete: " + "; ".join(missing_package_notices))

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
if json_guide_parser and "/tools/csv-viewer/" not in json_guide_parser.hrefs:
    fail("JSON formatting guide must contextually link to the CSV Viewer for spreadsheet-data discovery.")

# Extend the JSON guide's topical cluster from adjacent JSON utilities.
for related_json_page in (
    ROOT / "tools/csv-json-converter/index.html",
    ROOT / "tools/json-to-typescript/index.html",
):
    parser = all_parsers.get(related_json_page)
    if parser and "/guides/format-json-online/" not in parser.hrefs:
        fail(f"Related JSON utility must link to the practical JSON formatting guide: {related_json_page.relative_to(ROOT)}")

json_guide_html = (ROOT / "guides/format-json-online/index.html").read_text(encoding="utf-8")
missing_json_workflow = missing_json_file_workflow_disclosures(json_guide_html)
if missing_json_workflow:
    fail("JSON guide is missing practical local-file workflow details: " + ", ".join(missing_json_workflow))
json_tool_page = (ROOT / "tools/json-formatter/index.html").read_text(encoding="utf-8")
missing_json_tool_workflow = missing_json_file_workflow_disclosures(json_tool_page)
if missing_json_tool_workflow:
    fail("JSON Formatter page is missing local-file workflow details: " + ", ".join(missing_json_tool_workflow))
json_scope_pages = (
    ("JSON guide", json_guide_html),
    ("JSON Formatter", json_tool_page),
)
for page_name, page_text in json_scope_pages:
    missing_json_scope = missing_json_schema_scope_disclosures(page_text)
    if missing_json_scope:
        fail(f"{page_name} must distinguish JSON syntax validation from JSON Schema validation: " + ", ".join(missing_json_scope))
    missing_json_metadata = missing_json_scope_metadata_disclosures(page_text)
    if missing_json_metadata:
        fail(f"{page_name} search/social descriptions must state the JSON syntax and schema scope: " + ", ".join(missing_json_metadata))
if (
    'id="jsonFile"' not in json_tool_page
    or "MAX_JSON_FILE_BYTES=5*1024*1024" not in json_tool_page
    or "file.size>MAX_JSON_FILE_BYTES" not in json_tool_page
):
    fail("Dedicated JSON Formatter must provide a local file picker and enforce the 5 MiB limit before reading.")
homepage_json_page = (ROOT / "index.html").read_text(encoding="utf-8")
if "jsonFile" not in homepage_json_page or "maxJsonFileBytes=5*1024*1024" not in homepage_json_page or "file.size>maxJsonFileBytes" not in homepage_json_page:
    fail("Homepage JSON tool must provide a local file picker and enforce the 5 MiB limit before reading.")
strict_utf8_decoder = 'new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer())'
if strict_utf8_decoder not in json_tool_page or "new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer())" not in homepage_json_page:
    fail("Both JSON file importers must reject malformed UTF-8 instead of silently replacing invalid bytes.")

# Keep the image guide aligned with the actual compressor output contract.
image_guide = (ROOT / "guides/reduce-image-size/index.html").read_text(encoding="utf-8")
image_guide_parser = PageParser()
image_guide_parser.feed(image_guide)
image_guide_title = "".join(image_guide_parser.title_parts).strip()
if image_guide_title != "How to Reduce Image File Size Without Losing Quality | BuyTools.si":
    fail("Image guide title must match the verified no-quality-loss search intent.")
image_compressor_runtime = (ROOT / "index.html").read_text(encoding="utf-8")
quality_control_markup = 'id="quality" type="range" min=".2" max=".95" step=".05" value=".75"'
if quality_control_markup not in image_compressor_runtime:
    fail("Image compressor quality control must retain its documented 20%-95% range and 75% default.")
for required_quality_detail in (
    "starts at 75% quality and ranges from 20% to 95%",
    "browser's JPEG encoder",
    "not a percentage of pixels or image detail retained",
):
    if required_quality_detail not in image_guide:
        fail("Image guide is missing an accurate quality-control detail: " + required_quality_detail)
image_guide_article_date_errors = missing_article_date_modified_sync(image_guide)
for message in image_guide_article_date_errors:
    fail("Image guide Article dateModified is out of sync: " + message)
for required_image_guide_detail in (
    'id="quick-answer"',
    "Lossless optimization can reduce file size without changing decoded pixels",
    "Resizing:</strong> changes pixel dimensions",
    "Lossy compression:</strong> discards image information",
    'href="/tools/image-compressor/"',
    'href="/tools/image-resizer/"',
):
    if required_image_guide_detail not in image_guide:
        fail("Image guide is missing a search-intent or accuracy detail: " + required_image_guide_detail)
missing_image_disclosures = missing_image_compressor_disclosures(image_guide)
if missing_image_disclosures:
    fail("Image guide is missing accurate compressor disclosures: " + ", ".join(missing_image_disclosures))
missing_lossless_workflow = missing_image_lossless_workflow_disclosures(image_guide)
if missing_lossless_workflow:
    fail("Image guide is missing accurate lossless-workflow guidance: " + ", ".join(missing_lossless_workflow))
missing_reduction_steps = missing_image_reduction_workflow_steps(image_guide)
if missing_reduction_steps:
    fail("Image guide is missing actionable image-reduction workflow steps: " + ", ".join(missing_reduction_steps))
image_guide_lastmod_errors = missing_sitemap_lastmod_sync(
    (ROOT / "sitemap.xml").read_text(encoding="utf-8"),
    DOMAIN + "/guides/reduce-image-size/",
    image_guide,
)
for message in image_guide_lastmod_errors:
    fail("Image guide sitemap lastmod is out of sync: " + message)

# Keep the batch image resizer metadata and output explanation aligned with its PNG implementation.
batch_image_resizer_page = (ROOT / "tools/batch-image-resizer/index.html").read_text(encoding="utf-8")
missing_batch_resizer_disclosures = missing_batch_image_resizer_disclosures(batch_image_resizer_page)
if missing_batch_resizer_disclosures:
    fail("Batch image resizer page is inaccurate or incomplete: " + ", ".join(missing_batch_resizer_disclosures))

batch_image_compressor_page = (ROOT / "tools/batch-image-compressor/index.html").read_text(encoding="utf-8")
for page_name, page_text in (("Batch image compressor", batch_image_compressor_page), ("Batch image resizer", batch_image_resizer_page)):
    if "25 MiB" not in page_text or "before loading the ZIP library" not in page_text or "warning, not a hard limit" not in page_text or "especially on mobile" not in page_text:
        fail(f"{page_name} page must disclose the 25 MiB memory warning, mobile caveat and soft-limit behavior.")

# Check that each homepage catalogue ID has a corresponding tool renderer branch.
home = (ROOT / "index.html").read_text(encoding="utf-8")
count_mismatch = homepage_tool_count_mismatch(home)
if count_mismatch:
    fail(count_mismatch)
missing_homepage_json = missing_homepage_json_syntax_disclosure(home)
if missing_homepage_json:
    fail("Homepage JSON Formatter card must identify JSON syntax search intent: " + ", ".join(missing_homepage_json))
batch_process_start = home.find("async function processBatchImages(id){")
batch_process_end = home.find("async function processImages(id){", batch_process_start)
batch_process_branch = home[batch_process_start:batch_process_end] if batch_process_start >= 0 and batch_process_end > batch_process_start else ""
batch_guard = batch_process_branch.find("const totalBatchBytes=files.reduce((total,file)=>total+file.size,0),largeBatchWarningThreshold=25*1024*1024")
batch_warning = batch_process_branch.find("25 MiB batch-image warning threshold")
batch_import = batch_process_branch.find("await import('https://esm.sh/jszip@3.10.2')")
if min(batch_guard, batch_warning, batch_import) < 0 or not (batch_guard < batch_warning < batch_import):
    fail("Batch image tools must confirm large selections before loading JSZip.")
if "Batch image processing cancelled" not in batch_process_branch:
    fail("Batch image tools must expose an actionable cancellation status.")
batch_privacy = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
if "25 MiB" not in batch_privacy or "before requesting the library" not in batch_privacy or "cancelling prevents that request" not in batch_privacy:
    fail("Privacy policy must explain the batch-image ZIP library confirmation behavior.")
batch_browser_smoke = (ROOT / "scripts/browser_smoke.mjs").read_text(encoding="utf-8")
batch_browser_workflow = (ROOT / ".github/workflows/browser.yml").read_text(encoding="utf-8")
if "https://esm.sh/jszip@3.10.2" not in batch_privacy or "jszip@3.10.1" in batch_privacy:
    fail("Privacy policy must disclose the exact pinned JSZip version.")
if "https://esm.sh/jszip@3.10.2" not in batch_browser_smoke or "jszip@3.10.1" in batch_browser_smoke:
    fail("Chromium regression tests must verify the exact pinned JSZip version.")
if "jszip@3.10.2" not in batch_browser_workflow or "jszip@3.10.1" in batch_browser_workflow:
    fail("Browser workflow must install the same JSZip version used by production.")
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
    or "new TextDecoder('utf-8',{fatal:true})" not in home
    or "new TextDecoder('utf-16le',{fatal:true})" not in home
    or "new TextDecoder('utf-16be',{fatal:true})" not in home
    or "contains invalid text encoding" not in home
):
    fail("CSV Viewer must strictly decode UTF-8 and UTF-16 BOM files and reject malformed byte sequences.")
if (
    "UTF-16LE BOM" not in csv_viewer_page
    or "UTF-16BE BOM" not in csv_viewer_page
    or "malformed UTF-8 or UTF-16 sequences are rejected" not in csv_viewer_page
):
    fail("CSV Viewer landing page must disclose supported BOM encodings and strict malformed-input handling.")
if (
    'id="csvDelimiter"' not in home
    or "function parseCSV(input,delimiter=',')" not in home
    or "parseCSV(text.value,$('#csvDelimiter').value)" not in home
    or "Choose comma, semicolon or tab" not in home
):
    fail("CSV Viewer must expose and use an explicit comma, semicolon or tab field-separator control.")
if "comma-, semicolon- and tab-separated values" not in csv_viewer_page or "normalized to comma-separated CSV" not in csv_viewer_page:
    fail("CSV Viewer landing page must disclose supported import separators and comma-normalized exports.")
if "CRLF, LF or CR line endings" not in csv_viewer_page or "if(ch==='\\r'||ch==='\\n')" not in home:
    fail("CSV Viewer must parse and document CRLF, LF and CR record separators.")
if "Unexpected character after a closing quote" not in home or "Unexpected quote in an unquoted CSV field" not in home or "Invalid quote placement" not in csv_viewer_page:
    fail("CSV Viewer must reject malformed quote placement rather than silently altering values.")

if "Choose a .csv file up to 5 MiB" not in csv_viewer_page or "not uploaded to a processing server" not in csv_viewer_page:
    fail("CSV Viewer landing page must accurately disclose local file selection and its size limit.")
if "Open comma-, semicolon- or tab-delimited CSV files" not in csv_viewer_page or "Open local CSV files up to 5 MiB with the browser File API" not in csv_viewer_page:
    fail("CSV Viewer metadata must describe supported field separators and local file selection accurately.")

privacy_text = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
missing_advertising_disclosure = missing_advertising_consent_disclosure(privacy_text)
if missing_advertising_disclosure:
    fail("Privacy policy must accurately disclose consent-gated Adsterra advertising, rejection behavior, analytics status and hosting logs: " + ", ".join(missing_advertising_disclosure))

ad_engine_path = ROOT / "assets" / "buytools-ads.js"
if not ad_engine_path.is_file():
    fail("Consent-aware advertising engine is missing: assets/buytools-ads.js")
else:
    ad_engine = ad_engine_path.read_text(encoding="utf-8")
    required_ad_engine_markers = (
        'var CONSENT_KEY = "buytools-ad-consent-v1";',
        'if (localStorage.getItem(CONSENT_KEY) === "accepted") { mountAds(); return; }',
        'if (localStorage.getItem(CONSENT_KEY) === "rejected") return;',
        'src: "https://bicea.org/21/" + NATIVE_ID',
        'src: "https://bicea.org/22/" + key',
        'accept.addEventListener("click"',
        'reject.addEventListener("click"',
        'localStorage.setItem(CONSENT_KEY, "accepted")',
        'localStorage.setItem(CONSENT_KEY, "rejected")',
    )
    for marker in required_ad_engine_markers:
        if marker not in ad_engine:
            fail("Consent-aware advertising engine is missing required behavior: " + marker)
for public_page in html_files:
    public_html = public_page.read_text(encoding="utf-8")
    tracking_markers = known_analytics_or_ad_markers(public_html)
    if tracking_markers:
        fail(
            f"Unapproved analytics/advertising marker(s) found in {public_page.relative_to(ROOT)}: "
            + ", ".join(tracking_markers)
        )
if "CSV Viewer" not in privacy_text or "5 MiB" not in privacy_text or "browser File API" not in privacy_text or "not uploaded to a BuyTools.si processing endpoint" not in privacy_text:
    fail("Privacy policy must describe local CSV file reading and the 5 MiB limit.")
if "JSON Formatter" not in privacy_text or "selected UTF-8 .json file up to 5 MiB" not in privacy_text:
    fail("Privacy policy must describe local JSON file reading and the 5 MiB limit.")

# Keep privacy disclosures synchronized with third-party requests in the homepage tool code.
dynamic_import_urls = re.findall(r"""import\(['"](https?://[^'"]+)['"]\)""", home)
for dependency_url in dynamic_import_urls:
    if dependency_url not in privacy_text:
        fail(f"Third-party library import missing from privacy policy: {dependency_url}")
    if dependency_url not in licenses_page:
        fail(f"Direct browser package import missing from third-party license notice: {dependency_url}")
for host in ("staticimgly.com",):
    if host not in privacy_text:
        fail(f"Third-party processing or asset host missing from privacy policy: {host}")
qr_notice_requirements = (
    'for="text"',
    'aria-describedby="qrPrivacyNotice"',
    'id="qrPrivacyNotice"',
    'encoded locally in your browser',
    'not sent to a QR-generation service',
    'href="/privacy/"',
    'id="result" role="status" aria-live="polite"',
)
if any(requirement.lower() not in home.lower() for requirement in qr_notice_requirements):
    fail("QR generator must show an accessible disclosure that QR payloads are encoded locally.")
if "api.qrserver.com" in home.lower() or "api.qrserver.com" in privacy_text.lower():
    fail("QR content must not be sent to the retired third-party QR generation endpoint.")
if "buytools-theme" not in privacy_text:
    fail("Browser theme storage key is not disclosed in the privacy policy.")

# Password generation must use rejection sampling for an unbiased cryptographic alphabet mapping.
if (
    "function secureRandomString(length,alphabet,fillRandom=" not in home
    or "secureRandomString(n,chars)" not in home
    or "bytes[b%chars.length]" in home
):
    fail("Password generator must use unbiased rejection sampling over crypto.getRandomValues().")

# Large PDF jobs should warn before importing the browser-side PDF library.
# Images-to-PDF should warn before loading jsPDF and avoid base64 data-URL expansion.
images_pdf_start = home.find("if(id==='pdf-images'){")
images_pdf_end = home.find("if(id==='background')", images_pdf_start)
images_pdf_branch = home[images_pdf_start:images_pdf_end] if images_pdf_start >= 0 and images_pdf_end > images_pdf_start else ""
images_pdf_import = images_pdf_branch.find("const mod=await import('https://esm.sh/jspdf@4.2.1')")
images_pdf_guard = images_pdf_branch.find("const totalImageBytes=files.reduce((total,file)=>total+file.size,0),largeImageWarningThreshold=25*1024*1024")
images_pdf_warning = images_pdf_branch.find("25 MiB large-image warning threshold")
if min(images_pdf_import, images_pdf_guard, images_pdf_warning) < 0 or not (images_pdf_guard < images_pdf_warning < images_pdf_import):
    fail("Images-to-PDF must confirm large selections before loading jsPDF.")
if "https://esm.sh/jspdf@4.2.1" not in images_pdf_branch or "jspdf@2.5.2" in home:
    fail("Images-to-PDF must use patched jsPDF 4.2.1, not vulnerable 2.5.2.")
if "new Uint8Array(await f.arrayBuffer())" not in images_pdf_branch or "doc.addImage(imageBytes" not in images_pdf_branch or "readAsDataURL" in images_pdf_branch:
    fail("Images-to-PDF must pass binary image bytes to jsPDF instead of creating base64 data URLs.")
images_pdf_tool_page = (ROOT / "tools/images-to-pdf/index.html").read_text(encoding="utf-8")
images_pdf_guide = (ROOT / "guides/convert-images-to-pdf/index.html").read_text(encoding="utf-8")
for page_name, page_text in (("Images-to-PDF tool", images_pdf_tool_page), ("Images-to-PDF guide", images_pdf_guide)):
    if "25 MiB" not in page_text or "before loading the PDF library" not in page_text or "especially on mobile" not in page_text or "warning, not a hard" not in page_text:
        fail(f"{page_name} must disclose the 25 MiB memory warning, mobile caveat and soft-limit behavior.")
if "25 MiB" not in privacy_text or "before requesting the library" not in privacy_text or "cancelling prevents that request" not in privacy_text:
    fail("Privacy policy must explain the Images-to-PDF CDN request confirmation behavior.")

pdf_import = home.find("const {PDFDocument}=await import('https://esm.sh/pdf-lib@1.17.1')")
pdf_warning_guard = home.find("const totalPdfBytes=chosenFiles.reduce((total,file)=>total+file.size,0),largePdfWarningThreshold=25*1024*1024")
pdf_warning_dialog = home.find("25 MiB large-file warning threshold")
if min(pdf_import, pdf_warning_guard, pdf_warning_dialog) < 0 or not (pdf_warning_guard < pdf_warning_dialog < pdf_import):
    fail("PDF merge/split must validate size and ask before loading the PDF library for selections above 25 MiB.")
pdf_privacy_requirements = (
    "selected PDF files total more than 25 MiB",
    "before requesting the library",
    "cancelling prevents that request",
    "warning, not a hard limit",
    "especially on mobile devices",
)
if any(requirement not in privacy_text for requirement in pdf_privacy_requirements):
    fail("Privacy policy must disclose the PDF merge/split 25 MiB confirmation, cancellation behavior and mobile-memory caveat.")
if '<div class="result" id="result" role="status" aria-live="polite"></div>' not in home:
    fail("File-processing status messages must be exposed to assistive technology.")
pdf_merger_text = (ROOT / "tools/pdf-merger/index.html").read_text(encoding="utf-8")
pdf_splitter_text = (ROOT / "tools/pdf-splitter/index.html").read_text(encoding="utf-8")
for page_name, page_text in (("PDF merger", pdf_merger_text), ("PDF splitter", pdf_splitter_text)):
    if "25 MiB" not in page_text or "before loading the PDF library" not in page_text or "especially on mobile" not in page_text:
        fail(f"{page_name} page must disclose the large-file memory confirmation and mobile-memory caveat.")
background_tool_page = (ROOT / "tools/remove-background/index.html").read_text(encoding="utf-8")
for required in ('id="backgroundModel"', 'aria-describedby="backgroundModelHelp"', 'value="isnet_fp16"', 'value="isnet_quint8"'):
    if required not in home:
        fail(f"Background-removal model selector is missing: {required}")
if "const selectedBackgroundModel=$('#backgroundModel')?.value==='isnet_quint8'?'isnet_quint8':'isnet_fp16'" not in home or "model:selectedBackgroundModel" not in home:
    fail("Background removal must pass the user's selected model to IMG.LY.")
if "at least 90.2 MiB" not in home or "at least 48.4 MiB" not in home or "at least 48.4 MiB" not in background_tool_page:
    fail("Background-removal workspace and landing page must disclose both measured first-download lower bounds.")
if "94,553,445 bytes" not in privacy_text or "50,749,677 bytes" not in privacy_text or "46.3%" not in privacy_text:
    fail("Privacy policy must disclose both measured model-transfer lower bounds and their observed comparison.")
consent_key = "buytools-background-removal-consent-v1:"
consent_gate = home.find("const consentKey='" + consent_key + "'+selectedBackgroundModel")
model_import = home.find("const mod=await import('https://esm.sh/@imgly/background-removal@1.5.5')")
if consent_gate < 0 or model_import < 0 or consent_gate > model_import or "window.confirm(" not in home:
    fail("Each background-removal model must require its own explicit consent before the third-party import.")
if consent_key not in privacy_text:
    fail("Model-specific temporary background-removal consent storage must be disclosed in the privacy policy.")
if "separate confirmation is shown for each model" not in background_tool_page.lower():
    fail("Background-removal landing page must explain model-specific first-use confirmation.")
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

# Keep GitHub Pages write/OIDC permissions confined to the deploy job.
pages_workflow = ROOT / ".github" / "workflows" / "pages.yml"
if not pages_workflow.is_file():
    fail("GitHub Pages workflow is missing: .github/workflows/pages.yml")
else:
    for message in missing_pages_workflow_least_privilege(pages_workflow.read_text(encoding="utf-8")):
        fail("GitHub Pages workflow permissions are not least-privilege: " + message)

# Pin every external GitHub Action to a reviewed immutable commit.
workflow_dir = ROOT / ".github" / "workflows"
if not workflow_dir.is_dir():
    fail("GitHub Actions workflow directory is missing: .github/workflows")
else:
    workflow_files = sorted(
        list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    )
    if not workflow_files:
        fail("No GitHub Actions workflow files were found.")
    for workflow_file in workflow_files:
        for message in missing_immutable_action_pins(workflow_file.read_text(encoding="utf-8")):
            fail(
                "GitHub Actions references are not immutable in "
                + workflow_file.relative_to(ROOT).as_posix()
                + ": "
                + message
            )

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
