"""Ensure BuyTools.si ships without advertising or third-party ad tracking."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoAdvertisingTests(unittest.TestCase):
    def test_ad_runtime_and_build_injector_are_absent(self):
        self.assertFalse((ROOT / "assets" / "buytools-ads.js").exists())
        self.assertFalse((ROOT / "scripts" / "inject_ads.py").exists())
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("inject_ads.py", workflow)
        self.assertNotIn("Adsterra", workflow)

    def test_public_pages_contain_no_ad_delivery_or_consent_markup(self):
        forbidden = (
            "adsterra-ads.js",
            "buytools-ads.js",
            "data-adsterra",
            "buytools-ad-consent",
            "bicea.org",
            "ad-preferences=1",
        )
        for page in ROOT.rglob("*.html"):
            html = page.read_text(encoding="utf-8").lower()
            for marker in forbidden:
                self.assertNotIn(marker.lower(), html, f"{marker} remains in {page.relative_to(ROOT)}")

    def test_policy_and_readme_describe_the_no_ads_position(self):
        policy = (ROOT / "privacy" / "index.html").read_text(encoding="utf-8").lower()
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        monetization = (ROOT / "MONETIZATION.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("adsterra", policy)
        self.assertNotIn("bicea.org", policy)
        self.assertIn("currently runs no advertising network", readme)
        self.assertIn("no advertising network is active", monetization)


if __name__ == "__main__":
    unittest.main()
