"""Small, independently tested helpers for static site validation."""
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
