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


def missing_image_compressor_disclosures(html):
    """Return required, user-facing output limitations missing from the image guide."""
    normalized = " ".join(html.lower().split())
    required = (
        "currently exports jpeg files",
        "does not preserve transparency",
        "not a lossless png optimizer",
    )
    return [phrase for phrase in required if phrase not in normalized]


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
