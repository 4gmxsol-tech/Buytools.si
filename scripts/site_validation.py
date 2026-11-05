"""Small, independently tested helpers for static site validation."""
from urllib.parse import unquote


def fragment_target_exists(fragment, target_ids):
    """Return whether a URL fragment resolves to an ID in the target document."""
    if not fragment:
        return True
    return unquote(fragment) in set(target_ids)
