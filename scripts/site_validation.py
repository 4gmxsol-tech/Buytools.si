"""Small, independently tested helpers for static site validation."""
import re
import json
from html import unescape
from datetime import datetime
from urllib.parse import unquote, urljoin, urlparse
import xml.etree.ElementTree as ET


def fragment_target_exists(fragment, target_ids):
    """Return whether a URL fragment resolves to an ID in the target document."""
    if not fragment:
        return True
    return unquote(fragment) in set(target_ids)


def has_shared_favicon(icon_hrefs, expected="/assets/favicon.svg"):
    """Return whether a page declares the site's shared SVG favicon."""
    return expected in set(icon_hrefs)


def noncanonical_internal_index_links(hrefs, page_url, site_origin="https://buytools.si"):
    """Return same-site links that point at an index.html alias instead of a canonical directory URL."""
    origin = urlparse(site_origin).netloc.lower()
    aliases = []
    for href in hrefs:
        resolved = urljoin(page_url, href)
        parsed = urlparse(resolved)
        if (
            parsed.scheme in ("http", "https")
            and parsed.netloc.lower() == origin
            and parsed.path.lower().endswith("/index.html")
        ):
            aliases.append(href)
    return aliases


ANALYTICS_AND_AD_MARKERS = (
    "googletagmanager.com",
    "google-analytics.com",
    "gtag(",
    "connect.facebook.net",
    "fbq(",
    "clarity.ms",
    "hotjar.com",
    "plausible.io/js/script",
    "umami.is/script.js",
    "pagead2.googlesyndication.com",
    "googlesyndication.com",
    "doubleclick.net",
    "adsbygoogle",
    "adsterra.com",
    "popads.net",
)


def known_analytics_or_ad_markers(html):
    """Return known client-side analytics or advertising tags found in public HTML."""
    normalized = html.lower()
    markers = [marker for marker in ANALYTICS_AND_AD_MARKERS if marker not in ("gtag(", "fbq(") and marker in normalized]
    # Avoid false positives such as createSvgTag(), which contains the substring "gtag(".
    if re.search(r"(?<![a-z0-9_$])gtag\\s*\\(", normalized):
        markers.append("gtag(")
    if re.search(r"(?<![a-z0-9_$])fbq\\s*\\(", normalized):
        markers.append("fbq(")
    return markers


def missing_no_analytics_disclosure(html):
    """Return explicit current-state privacy disclosures missing from the policy."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    required = (
        "no third-party advertising or site-analytics scripts, pixels, or ad tags are currently loaded by buytools.si",
        "hosting provider may process technical information",
        "before activation",
    )
    return [phrase for phrase in required if phrase not in visible_text]


def missing_image_compressor_disclosures(html):
    """Return required, user-facing output limitations missing from the image guide."""
    normalized = " ".join(html.lower().split())
    required = (
        "currently exports jpeg files",
        "does not preserve transparency",
        "not a lossless png optimizer",
    )
    return [phrase for phrase in required if phrase not in normalized]


def missing_image_lossless_workflow_disclosures(html):
    """Return missing or inaccurate guidance about pixel-preserving image workflows."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    required = (
        "does not currently offer a pixel-preserving lossless image optimizer",
        "keeps the original pixel dimensions and decoded pixel values",
        "image compressor exports lossy jpeg files",
        "image resizer exports png files but changes pixel dimensions",
        "keep an untouched original copy",
        "can remove exif, orientation or color-profile information",
    )
    return [phrase for phrase in required if phrase not in visible_text]



def missing_image_reduction_workflow_steps(html):
    """Return missing actionable steps for preserving image quality while reducing file size."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    required = (
        "record the original format, pixel dimensions and file size",
        "run lossless optimization before resizing or lossy compression",
        "resize only to the largest dimensions needed for the final display",
        "compare the exported image at 100% zoom and at its intended display size",
        "check transparency, orientation and color before replacing the original",
    )
    return [phrase for phrase in required if phrase not in visible_text]


def missing_csv_export_safety_disclosures(html):
    """Return required user-facing CSV formula-safety disclosures missing from a page."""
    normalized = " ".join(html.lower().split())
    required = (
        "formula-like values",
        "leading apostrophe",
        "compatibility safeguard",
        "leading tab",
    )
    return [phrase for phrase in required if phrase not in normalized]


def missing_csv_troubleshooting_guidance(html_content):
    """Return missing practical diagnostics for common CSV import failures."""
    raw = str(html_content).lower()
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", raw).split())
    required = (
        "every value appears in one column",
        "save the file as utf-8",
        "same number of fields as the header row",
        "line breaks inside quoted fields",
        "normalized to comma-separated csv",
    )
    missing = [phrase for phrase in required if phrase not in visible_text]
    if 'id="csv-troubleshooting"' not in raw and "id='csv-troubleshooting'" not in raw:
        missing.append('troubleshooting section must have id="csv-troubleshooting"')
    return missing


def faq_schema_mismatches(html_content):
    """Require FAQPage JSON-LD questions and answers to mirror visible FAQ content."""
    content = str(html_content)
    visible_section = re.search(
        r"<section[^>]*>\s*<h2>\s*Frequently asked questions\s*</h2>(.*?)</section\s*>",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not visible_section:
        return ["Visible FAQ section is missing."]

    def normalize(value):
        text = unescape(re.sub(r"<[^>]+>", " ", str(value)))
        return " ".join(text.split()).casefold()

    visible_questions = [
        normalize(question)
        for question in re.findall(r"<h3[^>]*>(.*?)</h3\s*>", visible_section.group(1), flags=re.IGNORECASE | re.DOTALL)
    ]
    visible_answers = [
        normalize(answer)
        for answer in re.findall(r"<p[^>]*>(.*?)</p\s*>", visible_section.group(1), flags=re.IGNORECASE | re.DOTALL)
    ]
    if not visible_questions:
        return ["Visible FAQ section has no questions."]
    if len(visible_questions) != len(visible_answers):
        return ["Visible FAQ questions and answers are not paired."]
    visible_items = list(zip(visible_questions, visible_answers))

    for tag, script in re.findall(
        r"(<script[^>]*>)(.*?)</script\s*>",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if "application/ld+json" not in tag.lower():
            continue
        try:
            data = json.loads(script)
        except (TypeError, json.JSONDecodeError):
            continue
        nodes = data.get("@graph", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        if isinstance(data, dict) and data.get("@type") == "FAQPage":
            nodes = [data] + list(nodes)
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type", [])
            if node_type != "FAQPage" and not (isinstance(node_type, list) and "FAQPage" in node_type):
                continue
            schema_items = []
            for item in node.get("mainEntity", []):
                if not isinstance(item, dict) or item.get("@type") != "Question":
                    continue
                answer = item.get("acceptedAnswer", {})
                answer_text = answer.get("text", "") if isinstance(answer, dict) else ""
                schema_items.append((normalize(item.get("name", "")), normalize(answer_text)))
            if schema_items != visible_items:
                return ["FAQPage JSON-LD questions and answers must exactly match visible FAQ content."]
            return []
    return ["FAQPage JSON-LD node is missing."]

def missing_json_file_workflow_disclosures(html):
    """Return practical local JSON file workflow details missing from a page."""
    normalized = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    required = (
        "local",
        ".json file",
        "up to 5 mib",
        "browser file api",
        "not uploaded to a buytools.si processing endpoint",
    )
    missing = [phrase for phrase in required if phrase not in normalized]
    if "rather than a direct file upload" in normalized or "not currently. the json formatter accepts pasted text" in normalized:
        missing.append("outdated copy-only file workflow disclosure")
    return missing


def missing_json_schema_scope_disclosures(html):
    """Return missing distinctions between JSON syntax parsing and schema validation."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    required = (
        "json syntax only",
        "does not validate json schema",
        "required fields",
        "expected value types",
        "api contract",
    )
    return [phrase for phrase in required if phrase not in visible_text]


def missing_json_scope_metadata_disclosures(html):
    """Return missing JSON formatter/syntax-checker title and syntax/schema scope terms."""
    missing = []
    title_match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    title = " ".join(re.sub(r"<[^>]+>", " ", title_match.group(1)).lower().split()) if title_match else ""
    if not title:
        missing.append("title is missing")
    elif "json formatter" not in title or "syntax checker" not in title:
        missing.append("title must identify a JSON formatter and syntax checker")

    descriptions = (
        ("meta description", "name", "description"),
        ("Open Graph description", "property", "og:description"),
    )
    for label, attribute, expected in descriptions:
        value = " ".join(_meta_content(html, attribute, expected).lower().split())
        if not value:
            missing.append(f"{label} is missing")
            continue
        if "json syntax" not in value:
            missing.append(f"{label} must describe JSON syntax validation")
        if "json schema" not in value:
            missing.append(f"{label} must distinguish JSON Schema validation")
    return missing

def missing_homepage_json_syntax_disclosure(html):
    """Return missing JSON syntax wording from the homepage tool card and search tags."""
    match = re.search(
        r"\{id:'json',name:'JSON Formatter'.*?desc:'([^']*)',tags:'([^']*)'",
        html,
        flags=re.DOTALL,
    )
    if not match:
        return ["Homepage JSON Formatter catalogue entry is missing."]

    description, tags = match.groups()
    missing = []
    if "json syntax" not in description.lower():
        missing.append("description must identify JSON syntax checking")
    if "json syntax" not in tags.lower():
        missing.append("search tags must include JSON syntax")
    return missing


def _meta_content(html, attribute, expected):
    """Return the content value for a meta tag matching one attribute."""
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
        attrs = {}
        for match in re.finditer(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", tag):
            attrs[match.group(1).lower()] = match.group(2) if match.group(2) is not None else match.group(3)
        if attrs.get(attribute) == expected:
            return attrs.get("content", "")
    return ""


def missing_batch_image_resizer_disclosures(html):
    """Return inaccurate or missing metadata and output-format disclosures."""
    description = " ".join(_meta_content(html, "name", "description").lower().split())
    og_description = " ".join(_meta_content(html, "property", "og:description").lower().split())
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    missing = []

    description_required = ("resize multiple images online", "maximum width and height", "png results")
    if not all(phrase in description for phrase in description_required) or any(term in description for term in ("compress", "jpeg")):
        missing.append("meta description must describe PNG resizing rather than JPEG compression")

    og_required = ("resize multiple photos", "png results")
    if not all(phrase in og_description for phrase in og_required) or any(term in og_description for term in ("compress", "jpeg")):
        missing.append("Open Graph description must describe PNG resizing rather than JPEG compression")

    output_required = (
        "the resizer exports png files",
        "png encoding is lossless for the resized image",
        "resizing changes its pixel dimensions",
    )
    if not all(phrase in visible_text for phrase in output_required):
        missing.append("visible output-format disclosure must explain PNG encoding and resize dimensions")

    return missing


def homepage_tool_count_mismatch(html):
    """Return a message when the static homepage count disagrees with the tool catalogue."""
    catalogue_match = re.search(r"const tools\s*=\s*\[(.*?)\n\];", html, flags=re.DOTALL)
    count_match = re.search(
        r'<[^>]*\bid=["\']count["\'][^>]*>\s*(\d+)\s+tools\s*</',
        html,
        flags=re.IGNORECASE,
    )
    if not catalogue_match:
        return "Could not locate the homepage tool catalogue."
    if not count_match:
        return "Homepage static tool count label is missing or malformed."
    tool_ids = re.findall(r"\{id:'([^']+)'", catalogue_match.group(1))
    if not tool_ids:
        return "Homepage tool catalogue contains no identifiable tool IDs."
    displayed_count = int(count_match.group(1))
    if displayed_count != len(tool_ids):
        return (
            f"Homepage static count says {displayed_count} tools, "
            f"but the catalogue contains {len(tool_ids)} entries."
        )
    return None



def missing_license_footer_link(html):
    """Return an error when a key landing page footer omits the software-notice link."""
    footer = re.search(r"<footer\b[^>]*>(.*?)</footer\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    if not footer:
        return "Page footer is missing."
    if not re.search(r"""href\s*=\s*["']/licenses/["']""", footer.group(1), flags=re.IGNORECASE):
        return "Page footer must link to /licenses/."
    return None

def missing_direct_browser_package_notices(site_html, licenses_html):
    """Return missing license entries for version-pinned esm.sh dynamic imports."""
    imports = re.findall(
        r"""import\s*\(\s*(['"])https://esm\.sh/([^'"]+)\1\s*\)""",
        site_html,
        flags=re.IGNORECASE,
    )
    package_versions = set()
    missing = []
    for _, import_path in imports:
        spec = re.split(r"[?#]", import_path, maxsplit=1)[0].strip("/")
        package, separator, version = spec.rpartition("@")
        if not separator or not package or not version:
            missing.append(f"Direct esm.sh package import must pin a version: {spec}")
            continue
        package_versions.add((package, version))

    license_text = " ".join(re.sub(r"<[^>]+>", " ", licenses_html).casefold().split())
    for package, version in sorted(package_versions):
        pattern = (
            re.escape(package.casefold())
            + r"\s*[—–-]\s*version\s*"
            + re.escape(version.casefold())
            + r"(?![0-9a-z.-])"
        )
        if not re.search(pattern, license_text):
            missing.append(f"License notice missing exact package/version: {package}@{version}")
    return missing

def missing_runtime_dependency_notices(manifest, licenses_html):
    """Return missing notices for packages observed in the background-removal runtime graph."""
    missing = []
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        return ["Runtime dependency baseline is missing or has an unsupported schema version."]

    packages = manifest.get("observedModules")
    if not isinstance(packages, list) or not packages:
        return ["Runtime dependency baseline has no observed modules."]

    if not re.search(r"""id\s*=\s*["']background-removal-runtime["']""", licenses_html, flags=re.IGNORECASE):
        missing.append("License page is missing the background-removal runtime inventory section.")

    license_text = " ".join(re.sub(r"<[^>]+>", " ", licenses_html).casefold().split())
    for package in packages:
        name = str(package.get("name", "")).strip()
        version = str(package.get("resolvedVersion", "")).strip()
        license_name = str(package.get("license", "")).strip()
        npm_url = str(package.get("npmUrl", "")).strip()
        if not name or not version or not license_name:
            missing.append("Runtime dependency baseline contains an incomplete package record.")
            continue

        pattern = (
            re.escape(name.casefold())
            + r"\s*[—–-]\s*version\s*"
            + re.escape(version.casefold())
            + r"(?![0-9a-z.-])"
        )
        if not re.search(pattern, license_text):
            missing.append(f"Runtime dependency license notice missing exact package/version: {name}@{version}")
        if f"license: {license_name}".casefold() not in license_text:
            missing.append(f"Runtime dependency license notice missing license identifier: {name}@{version} ({license_name})")
        if npm_url and npm_url not in licenses_html:
            missing.append(f"Runtime dependency license notice missing versioned npm metadata link: {name}@{version}")
    return missing


def missing_upstream_lock_evidence(manifest):
    """Validate source-lock dependency versions, license evidence and advisory assessments."""
    missing = []
    if not isinstance(manifest, dict):
        return ["Runtime dependency baseline must be a JSON object."]
    evidence = manifest.get("upstreamLockEvidence")
    if not isinstance(evidence, dict):
        return ["Upstream ONNX Runtime lockfile evidence is missing."]
    source_url = str(evidence.get("sourceUrl", "")).strip()
    if source_url != "https://raw.githubusercontent.com/microsoft/onnxruntime/v1.18.0/js/web/package-lock.json":
        missing.append("Upstream lockfile source must identify ONNX Runtime v1.18.0 js/web/package-lock.json.")
    if evidence.get("sourceTag") != "v1.18.0" or evidence.get("lockfileVersion") != 2:
        missing.append("Upstream lockfile tag or lockfile version is inconsistent.")
    records = evidence.get("packages")
    if not isinstance(records, list) or not records:
        return missing + ["Upstream lockfile evidence has no package records."]
    by_name = {}
    for record in records:
        if not isinstance(record, dict):
            missing.append("Upstream lockfile package record must be an object.")
            continue
        name = str(record.get("name", "")).strip()
        version = str(record.get("version", "")).strip()
        license_name = str(record.get("license", "")).strip()
        lock_path = str(record.get("lockPath", "")).strip()
        npm_url = str(record.get("npmUrl", "")).strip()
        if not all((name, version, license_name, lock_path, npm_url)):
            missing.append("Upstream lockfile package record is missing name, version, license, lock path or npm URL.")
            continue
        if name in by_name:
            missing.append(f"Duplicate upstream lockfile package record: {name}.")
            continue
        expected_npm_url = f"https://www.npmjs.com/package/{name}/v/{version}"
        if npm_url != expected_npm_url:
            missing.append(f"Upstream package metadata URL does not match {name}@{version}.")
        resolved = record.get("resolved")
        integrity = record.get("integrity")
        if resolved:
            if not str(resolved).startswith("https://registry.npmjs.org/"):
                missing.append(f"Upstream package tarball URL is not an npm registry URL: {name}@{version}.")
            if not str(integrity or "").startswith("sha512-"):
                missing.append(f"Upstream package lock integrity is missing SHA-512 evidence: {name}@{version}.")
        elif not (name == "onnxruntime-common" and lock_path == "../common" and record.get("resolutionType") == "source-local-file"):
            missing.append(f"Only onnxruntime-common may use the documented source-local lock path: {name}@{version}.")
        by_name[name] = record
    required_names = evidence.get("requiredPackageNames")
    if not isinstance(required_names, list) or not required_names:
        missing.append("Upstream lockfile required package-name list is missing.")
    else:
        for name in required_names:
            if name not in by_name:
                missing.append(f"Upstream lockfile evidence is missing required package: {name}.")
    for dependency in manifest.get("unresolvedBundledDependencies", []):
        if not isinstance(dependency, dict):
            missing.append("Unresolved runtime dependency record must be an object.")
            continue
        name = str(dependency.get("name", "")).strip()
        record = by_name.get(name)
        if not record:
            missing.append(f"Unresolved runtime dependency has no upstream lockfile record: {name}.")
            continue
        if dependency.get("upstreamLockedVersion") != record.get("version"):
            missing.append(f"Upstream locked version mismatch for {name}.")
        if dependency.get("license") != record.get("license") or dependency.get("npmUrl") != record.get("npmUrl"):
            missing.append(f"Upstream license or package metadata mismatch for {name}.")
        if "not individually observed" not in str(dependency.get("runtimeObservation", "")).lower():
            missing.append(f"Runtime observation limitation must remain explicit for {name}.")
    advisories = manifest.get("securityReview", {}).get("transitiveAdvisories")
    if not isinstance(advisories, list) or not advisories:
        missing.append("Transitive dependency advisory review is missing.")
    else:
        for advisory in advisories:
            if not isinstance(advisory, dict):
                missing.append("Transitive advisory record must be an object.")
                continue
            name = str(advisory.get("package", "")).strip()
            record = by_name.get(name)
            if not record or advisory.get("version") != record.get("version"):
                missing.append(f"Transitive advisory package/version is not in the upstream lock evidence: {name}.")
            if not str(advisory.get("advisoryUrl", "")).startswith("https://github.com/advisories/"):
                missing.append(f"Transitive advisory must link to a GitHub-reviewed advisory: {name}.")
            for field in ("affectedRange", "patchedVersion", "preconditions", "buytoolsAssessment"):
                if not str(advisory.get(field, "")).strip():
                    missing.append(f"Transitive advisory record is missing {field}: {name}.")
    if not str(manifest.get("securityReview", {}).get("transitiveExposureConclusion", "")).strip():
        missing.append("Transitive dependency exposure conclusion is missing.")

    bundle = manifest.get("upstreamBundleEvidence")
    if not isinstance(bundle, dict):
        missing.append("Upstream ONNX Runtime ESM source-map evidence is missing.")
    else:
        if bundle.get("packageManifestUrl") != "https://unpkg.com/onnxruntime-web@1.18.0/package.json":
            missing.append("ONNX Runtime package manifest URL is inconsistent.")
        if bundle.get("cpuEsmExport") != "./dist/esm/ort.min.js":
            missing.append("ONNX Runtime CPU ESM export path is inconsistent.")
        if bundle.get("cpuSourceMapUrl") != "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.min.js.map":
            missing.append("ONNX Runtime CPU source-map URL is inconsistent.")
        if bundle.get("webgpuEsmExport") != "./dist/esm/ort.webgpu.min.js":
            missing.append("ONNX Runtime WebGPU ESM export path is inconsistent.")
        if bundle.get("webgpuSourceMapUrl") != "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.webgpu.min.js.map":
            missing.append("ONNX Runtime WebGPU source-map URL is inconsistent.")

        cpu_sources = bundle.get("cpuSourcePaths")
        if not isinstance(cpu_sources, list):
            missing.append("ONNX Runtime CPU source-map paths must be a list.")
            cpu_sources = []
        for required_path, message in (
            ("../../node_modules/protobufjs/src/reader.js", "ONNX Runtime CPU source map must include protobufjs reader code."),
            ("../../node_modules/protobufjs/src/writer.js", "ONNX Runtime CPU source map must include protobufjs writer code."),
            ("../../node_modules/@protobufjs/utf8/index.js", "ONNX Runtime CPU source map must include @protobufjs/utf8."),
        ):
            if required_path not in cpu_sources:
                missing.append(message)

        webgpu_protobuf_sources = bundle.get("webgpuProtobufSourcePaths")
        if not isinstance(webgpu_protobuf_sources, list) or webgpu_protobuf_sources:
            missing.append("WebGPU source-map review must not claim protobufjs/@protobufjs source paths.")

        confirmed = bundle.get("confirmedBundledPackages")
        if not isinstance(confirmed, list) or not confirmed:
            missing.append("Confirmed ONNX Runtime source-map package records are missing.")
            confirmed = []
        confirmed_names = set()
        for package in confirmed:
            if not isinstance(package, dict):
                missing.append("Confirmed source-map package record must be an object.")
                continue
            name = str(package.get("name", "")).strip()
            confirmed_names.add(name)
            record = by_name.get(name)
            if not record:
                missing.append(f"Confirmed bundled dependency has no upstream lockfile record: {name}.")
                continue
            if package.get("version") != record.get("version") or package.get("license") != record.get("license"):
                missing.append(f"Confirmed bundled dependency version/license differs from source-lock evidence: {name}.")
            source_paths = package.get("sourcePaths")
            if not isinstance(source_paths, list) or not source_paths or not any(path in cpu_sources for path in source_paths):
                missing.append(f"Confirmed bundled dependency has no matching CPU source-map path: {name}.")
        for required_name in ("protobufjs", "@protobufjs/utf8"):
            if required_name not in confirmed_names:
                missing.append(f"CPU source-map evidence must confirm advisory-relevant package: {required_name}.")

        unconfirmed = bundle.get("unconfirmedLockPackages")
        if not isinstance(unconfirmed, list):
            missing.append("Unconfirmed source-lock package list must be explicit.")
        else:
            for name in unconfirmed:
                if name not in by_name:
                    missing.append(f"Unconfirmed source-lock package has no lockfile record: {name}.")

        observed_ort = next(
            (module for module in manifest.get("observedModules", []) if isinstance(module, dict) and module.get("name") == "onnxruntime-web"),
            None,
        )
        if not observed_ort or observed_ort.get("resolvedVersion") != "1.18.0":
            missing.append("Observed runtime baseline must identify onnxruntime-web@1.18.0.")
        else:
            module_paths = observed_ort.get("modulePaths", [])
            if not all(path in module_paths for path in (
                "/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs",
                "/onnxruntime-web@1.18.0/es2022/webgpu.mjs",
            )):
                missing.append("Observed esm.sh CPU and WebGPU module paths are incomplete.")

        scope_note = str(bundle.get("scopeNote", "")).casefold()
        if "not a byte-for-byte comparison" not in scope_note or "esm.sh" not in scope_note:
            missing.append("Bundle source-map scope note must distinguish upstream evidence from the esm.sh transformed response.")
        runtime_hash_note = str(bundle.get("runtimeHashNote", "")).casefold()
        if "sha-256" not in runtime_hash_note or "subresource integrity" not in runtime_hash_note:
            missing.append("Bundle runtime hash limitation must distinguish CI hashes from runtime Subresource Integrity.")

    response_evidence = manifest.get("observedEsmShResponseEvidence")
    if not isinstance(response_evidence, dict):
        missing.append("Exact esm.sh ONNX Runtime response evidence is missing.")
    else:
        if not isinstance(response_evidence.get("workflowRunId"), int):
            missing.append("esm.sh response evidence must identify its GitHub Actions run.")
        if not str(response_evidence.get("workflowRunUrl", "")).startswith("https://github.com/4gmxsol-tech/Buytools.si/actions/runs/"):
            missing.append("esm.sh response evidence must link to the BuyTools browser audit run.")
        modules = response_evidence.get("modules")
        if not isinstance(modules, list) or len(modules) != 2:
            missing.append("esm.sh response evidence must include CPU and WebGPU module records.")
            modules = []
        by_kind = {item.get("kind"): item for item in modules if isinstance(item, dict)}
        for kind, expected_path in (
            ("CPU ESM", "/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs"),
            ("WebGPU ESM", "/onnxruntime-web@1.18.0/es2022/webgpu.mjs"),
        ):
            item = by_kind.get(kind)
            if not item:
                missing.append("esm.sh response evidence is missing " + kind + ".")
                continue
            if not str(item.get("url", "")).startswith("https://esm.sh" + expected_path):
                missing.append("esm.sh response URL is inconsistent for " + kind + ".")
            browser_hash = str(item.get("browserResponseSha256", ""))
            refetched_hash = str(item.get("refetchedResponseSha256", ""))
            if item.get("responseHashMatch") is not True or not re.fullmatch(r"[0-9a-f]{64}", browser_hash) or browser_hash != refetched_hash:
                missing.append("Same-run Chromium/refetch SHA-256 evidence does not match for " + kind + ".")
            if item.get("sourceMapReferenceKind") not in ("response-comment", "response-header"):
                missing.append("esm.sh source map must be declared by the response for " + kind + ".")
            if not str(item.get("sourceMapUrl", "")).startswith("https://esm.sh/") or item.get("sourceMapHttpStatus") != 200:
                missing.append("esm.sh source map must be retrievable for " + kind + ".")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sourceMapSha256", ""))) or not isinstance(item.get("sourceMapSourceCount"), int) or item.get("sourceMapSourceCount", 0) < 1:
                missing.append("esm.sh source map hash or source count is missing for " + kind + ".")
            if not str(item.get("upstreamSourceMapUrl", "")).startswith("https://unpkg.com/onnxruntime-web@1.18.0/") or item.get("upstreamSourceMapHttpStatus") != 200:
                missing.append("Corresponding upstream ONNX Runtime source map is missing for " + kind + ".")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("upstreamSourceMapSha256", ""))) or not isinstance(item.get("upstreamSourceMapSourceCount"), int):
                missing.append("Upstream source map hash or source count is missing for " + kind + ".")
            if item.get("sourceCountMatchesUpstream") is not True or item.get("packagePathSignalParity") is not True:
                missing.append("esm.sh source-map package-path signals do not match the upstream map for " + kind + ".")
            signals = item.get("sourcePathSignals")
            if not isinstance(signals, dict):
                missing.append("esm.sh source-path signals are missing for " + kind + ".")
                signals = {}
            if kind == "CPU ESM":
                for name in ("protobufReader", "protobufWriter", "protobufUtf8", "flatbuffers", "long", "guidTypescript", "onnxruntimeCommon"):
                    if signals.get(name) is not True:
                        missing.append("CPU esm.sh source map must confirm " + name + ".")
            else:
                for name in ("protobufReader", "protobufWriter", "protobufUtf8", "flatbuffers", "long", "guidTypescript"):
                    if signals.get(name) is not False:
                        missing.append("WebGPU esm.sh source map must not claim " + name + ".")
                if signals.get("onnxruntimeCommon") is not True:
                    missing.append("WebGPU esm.sh source map must confirm ONNX Runtime Common source paths.")

    return missing


def missing_confirmed_bundled_license_notices(manifest, licenses_html):
    """Ensure every source-map-confirmed transitive package has a versioned public notice."""
    bundle = manifest.get("upstreamBundleEvidence", {}) if isinstance(manifest, dict) else {}
    packages = bundle.get("confirmedBundledPackages", []) if isinstance(bundle, dict) else []
    lock_evidence = manifest.get("upstreamLockEvidence", {}) if isinstance(manifest, dict) else {}
    lock_records = {
        record.get("name"): record
        for record in lock_evidence.get("packages", [])
        if isinstance(record, dict)
    } if isinstance(lock_evidence, dict) else {}
    section = re.search(
        r'<section\b[^>]*id=["\']onnxruntime-transitive-notices["\'][^>]*>(.*?)</section\s*>',
        str(licenses_html),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not section:
        return ["License page is missing the confirmed ONNX Runtime transitive-notices section."]
    html = section.group(1)
    missing = []
    licenses_present = set()
    for package in packages:
        if not isinstance(package, dict):
            missing.append("Confirmed bundled license notice record must be an object.")
            continue
        name = str(package.get("name", "")).strip()
        version = str(package.get("version", "")).strip()
        license_name = str(package.get("license", "")).strip()
        record = lock_records.get(name, {})
        npm_url = str(package.get("npmUrl") or record.get("npmUrl", "")).strip()
        if not name or not version or not license_name or not npm_url:
            missing.append("Confirmed bundled license notice record is missing name, version, license or npm URL.")
            continue
        licenses_present.add(license_name)
        if name + " — version " + version not in html:
            missing.append("Public transitive license notice missing exact package/version: " + name + "@" + version)
        if license_name not in html:
            missing.append("Public transitive license notice missing license identifier: " + name + "@" + version)
        if npm_url not in html:
            missing.append("Public transitive license notice missing versioned npm metadata link: " + name + "@" + version)

    copyright_requirements = {
        "BSD-3-Clause": ("Copyright (c) 2016, Daniel Wirtz",),
        "Apache-2.0": ("Google Inc.", "Daniel Wirtz", "Closure Library Authors"),
        "ISC": ("Nicolas Silva dos Santos",),
        "MIT": ("Microsoft Corporation",),
    }
    for license_name in licenses_present:
        if license_name not in copyright_requirements:
            continue
        for notice in copyright_requirements[license_name]:
            if notice not in html:
                missing.append("Public transitive license notice is missing copyright attribution for " + license_name + ": " + notice)

    for license_name, url in (
        ("BSD-3-Clause", "https://spdx.org/licenses/BSD-3-Clause.html"),
        ("Apache-2.0", "https://spdx.org/licenses/Apache-2.0.html"),
        ("ISC", "https://spdx.org/licenses/ISC.html"),
        ("MIT", "https://spdx.org/licenses/MIT.html"),
    ):
        if license_name in licenses_present and url not in html:
            missing.append("Public transitive license notice is missing the canonical full-text link for " + license_name + ".")
    return missing

def has_head_license_declaration(html):
    """Return whether the document head declares a document-level license."""
    head = re.search(r"<head\b[^>]*>(.*?)</head\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    if not head:
        return False
    for tag in re.findall(r"<link\b[^>]*>", head.group(1), flags=re.IGNORECASE):
        rel = re.search(r"""\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", tag, flags=re.IGNORECASE)
        if rel:
            value = next((part for part in rel.groups() if part is not None), "")
            if "license" in value.lower().split():
                return True
    return False



def missing_sitemap_lastmod_sync(sitemap_content, page_url, page_html):
    """Return errors when a page's visible update date and sitemap lastmod disagree."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", page_html).lower().split())
    match = re.search(r"last updated:\s*([a-z]+\s+\d{1,2},\s+\d{4})", visible_text, re.IGNORECASE)
    if not match:
        return ["page is missing a visible 'Last updated: Month D, YYYY' date"]

    try:
        page_date = datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return ["page has an invalid visible last-updated date"]

    try:
        root = ET.fromstring(sitemap_content)
    except ET.ParseError:
        return ["sitemap XML cannot be parsed"]

    entry = next(
        (
            item for item in root.findall(".//{*}url")
            if (item.findtext("{*}loc") or "").strip() == page_url
        ),
        None,
    )
    if entry is None:
        return ["page URL is missing from sitemap"]

    lastmod = (entry.findtext("{*}lastmod") or "").strip()
    if not lastmod:
        return ["page URL is missing sitemap lastmod"]

    try:
        sitemap_date = datetime.strptime(lastmod, "%Y-%m-%d").date()
    except ValueError:
        return ["page URL has an invalid sitemap lastmod date"]

    if sitemap_date != page_date:
        return [
            "sitemap lastmod " + sitemap_date.isoformat()
            + " does not match visible page date " + page_date.isoformat()
        ]
    return []



def missing_article_date_modified_sync(html):
    """Return errors when Article JSON-LD dateModified differs from the visible update date."""
    visible_text = " ".join(re.sub(r"<[^>]+>", " ", html).lower().split())
    visible_match = re.search(r"last updated:\s*([a-z]+\s+\d{1,2},\s+\d{4})", visible_text, re.IGNORECASE)
    if not visible_match:
        return ["page is missing a visible 'Last updated: Month D, YYYY' date"]

    try:
        visible_date = datetime.strptime(visible_match.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ["page has an invalid visible last-updated date"]

    schema_dates = re.findall(r'"dateModified"\s*:\s*"([^"]+)"', html)
    if len(schema_dates) != 1:
        return ["Article JSON-LD must contain exactly one dateModified value"]
    if schema_dates[0] != visible_date:
        return [
            "Article dateModified " + schema_dates[0]
            + " does not match visible page date " + visible_date
        ]
    return []


def missing_pages_workflow_least_privilege(workflow_text):
    """Return errors when Pages write/OIDC permissions are not isolated to deploy."""
    errors = []
    top_permissions = re.search(r"(?m)^permissions:\s*(.*?)\s*$", workflow_text)
    if not top_permissions or top_permissions.group(1) != "{}":
        errors.append("workflow-level permissions must be empty so job permissions are explicit")

    jobs_match = re.search(r"(?ms)^jobs:\s*\n(.*)\Z", workflow_text)
    if not jobs_match:
        return errors + ["Pages workflow is missing its jobs section."]

    jobs_text = jobs_match.group(1)
    build_match = re.search(r"(?m)^  build:\s*$", jobs_text)
    deploy_match = re.search(r"(?m)^  deploy:\s*$", jobs_text)
    if not build_match or not deploy_match or deploy_match.start() <= build_match.start():
        return errors + ["Pages workflow must define build and deploy jobs in order."]

    build_block = jobs_text[build_match.end():deploy_match.start()]
    deploy_block = jobs_text[deploy_match.end():]

    def parse_permissions(job_block):
        lines = job_block.splitlines()
        for index, line in enumerate(lines):
            if line == "    permissions:":
                permissions = {}
                for candidate in lines[index + 1:]:
                    if not candidate.startswith("      "):
                        break
                    match = re.fullmatch(r"      ([a-z0-9-]+): (read|write|none)", candidate)
                    if not match:
                        return None
                    permissions[match.group(1)] = match.group(2)
                return permissions
        return None

    if parse_permissions(build_block) != {"contents": "read", "pages": "read"}:
        errors.append("build job must have only contents:read and pages:read permissions")
    if parse_permissions(deploy_block) != {"contents": "read", "pages": "write", "id-token": "write"}:
        errors.append("deploy job must have contents:read, pages:write and id-token:write permissions")
    return errors





def missing_immutable_action_pins(workflow_text):
    """Return errors for external Actions that are not pinned to immutable commits."""
    errors = []
    for line_number, line in enumerate(workflow_text.splitlines(), start=1):
        match = re.match(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*(.*))?\s*$", line)
        if not match:
            continue

        reference, annotation = match.groups()
        if reference.startswith("./"):
            continue
        if reference.startswith("docker://"):
            if not re.search(r"@sha256:[0-9a-f]{64}$", reference):
                errors.append(f"line {line_number}: Docker action must use an immutable sha256 digest")
            continue

        action_name, separator, revision = reference.rpartition("@")
        if not separator or not action_name or not re.fullmatch(r"[0-9a-f]{40}", revision):
            errors.append(f"line {line_number}: {reference} must use a full 40-character commit SHA")
            continue
        if not annotation or not re.search(r"\bv\d+(?:\.\d+){0,2}\b", annotation, re.IGNORECASE):
            errors.append(f"line {line_number}: {action_name} must include an upstream version annotation such as '# v5'")
    return errors
