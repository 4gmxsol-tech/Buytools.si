"""Small, independently tested helpers for static site validation."""
import re
from urllib.parse import unquote


def fragment_target_exists(fragment, target_ids):
    """Return whether a URL fragment resolves to an ID in the target document."""
    if not fragment:
        return True
    return unquote(fragment) in set(target_ids)


def has_shared_favicon(icon_hrefs, expected="/assets/favicon.svg"):
    """Return whether a page declares the site's shared SVG favicon."""
    return expected in set(icon_hrefs)


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
    return [marker for marker in ANALYTICS_AND_AD_MARKERS if marker in normalized]


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
    """Return missing JSON syntax/schema scope terms from search and social descriptions."""
    missing = []
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
