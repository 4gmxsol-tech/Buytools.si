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
