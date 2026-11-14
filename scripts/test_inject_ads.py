"""Regression tests for the build-time Adsterra script injector."""
import tempfile
import unittest
from pathlib import Path

from inject_ads import TAG, inject_ads

ROOT = Path(__file__).resolve().parents[1]


class InjectAdsTests(unittest.TestCase):
    def make_site(self, root):
        (root / "assets").mkdir(parents=True)
        (root / "assets" / "buytools-ads.js").write_text(
            "/* consent-aware ad engine fixture */", encoding="utf-8"
        )
        pages = {
            "index.html": "<html><body><main>Home</main><footer>Footer</footer></body></html>",
            "guides/example/index.html": "<html><body><main>Guide</main></body></html>",
            "tools/example/index.html": "<html><body><main>Tool</main></body></html>",
            "about/index.html": "<html><body><main>About</main></body></html>",
            "privacy/index.html": "<html><body><main>Privacy</main></body></html>",
            "terms/index.html": "<html><body><main>Terms</main></body></html>",
            "licenses/index.html": "<html><body><main>Licenses</main></body></html>",
        }
        for name, content in pages.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return pages

    def test_injects_once_into_eligible_pages_and_skips_legal_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_site(root)

            injected, eligible = inject_ads(root)

            self.assertEqual((injected, eligible), (4, 4))
            for name in ("index.html", "guides/example/index.html", "tools/example/index.html", "about/index.html"):
                content = (root / name).read_text(encoding="utf-8")
                self.assertEqual(content.count(TAG), 1)
                self.assertLess(content.index(TAG), content.lower().index("</body>"))
            for name in ("privacy/index.html", "terms/index.html", "licenses/index.html"):
                content = (root / name).read_text(encoding="utf-8")
                self.assertNotIn(TAG, content)

    def test_injection_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_site(root)

            self.assertEqual(inject_ads(root), (4, 4))
            self.assertEqual(inject_ads(root), (0, 4))
            self.assertEqual(
                (root / "index.html").read_text(encoding="utf-8").count(TAG),
                1,
            )

    def test_missing_body_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "assets").mkdir()
            (root / "assets" / "buytools-ads.js").write_text("/* engine */", encoding="utf-8")
            (root / "broken.html").write_text("<html><main>No body close</main></html>", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing </body>"):
                inject_ads(root)

    def test_missing_engine_asset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ad engine is missing"):
                inject_ads(root)


class AdConsentPrivacyLinkTests(unittest.TestCase):
    def test_consent_prompt_links_to_existing_advertising_disclosure(self):
        engine = (ROOT / "assets" / "buytools-ads.js").read_text(encoding="utf-8")
        policy = (ROOT / "privacy" / "index.html").read_text(encoding="utf-8")

        self.assertIn(
            'var privacyLink = el("a", { href: "/privacy/", class: "buytools-consent-privacy-link" }, "Read the privacy policy");',
            engine,
        )
        self.assertIn("panel.appendChild(copy); panel.appendChild(privacyLink); panel.appendChild(actions);", engine)
        self.assertIn(".buytools-consent-privacy-link:focus-visible", engine)
        self.assertIn("<h2>Advertising and analytics</h2>", policy)
        self.assertIn("Adsterra and its partners may process technical information", policy)

    def test_consent_prompt_uses_a_named_nonmodal_region_with_description(self):
        engine = (ROOT / "assets" / "buytools-ads.js").read_text(encoding="utf-8")

        self.assertIn(
            'var panel = el("aside", { id: "buytools-ad-consent", role: "region", "aria-live": "polite", "aria-label": "Advertising preferences", "aria-describedby": "buytools-ad-consent-description" });',
            engine,
        )
        self.assertIn(
            'var copy = el("p", { id: "buytools-ad-consent-description" }, "BuyTools.si uses Adsterra advertising.',
            engine,
        )
        self.assertNotIn('role: "dialog"', engine)


if __name__ == "__main__":
    unittest.main()
