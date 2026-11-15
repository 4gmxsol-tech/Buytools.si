"""Keep monetization documentation aligned with the deployed consent-gated ad engine."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "MONETIZATION.md").read_text(encoding="utf-8")
ENGINE = (ROOT / "assets" / "buytools-ads.js").read_text(encoding="utf-8")
INJECTOR = (ROOT / "scripts" / "inject_ads.py").read_text(encoding="utf-8")
POLICY = (ROOT / "privacy" / "index.html").read_text(encoding="utf-8")


class MonetizationDocumentationTests(unittest.TestCase):
    def test_documentation_describes_the_existing_adsterra_integration(self):
        self.assertIn("Adsterra is integrated into the production build", DOC)
        self.assertIn("scripts/inject_ads.py", DOC)
        self.assertIn("assets/buytools-ads.js", DOC)
        self.assertIn("bicea.org", DOC)
        self.assertNotIn("No advertising network is wired into the site", DOC)

    def test_documented_consent_states_match_runtime_and_privacy_policy(self):
        for snippet in (
            'var CONSENT_KEY = "buytools-ad-consent-v1";',
            'var consentReadFailed = false;',
            'function readConsent()',
            'window.localStorage.getItem(CONSENT_KEY)',
            'catch (error) { consentReadFailed = true; return null; }',
            'function saveConsent(value)',
            'window.localStorage.setItem(CONSENT_KEY, value); return true;',
            'catch (error) { return false; }',
            'function showConsentNotice(adWasAlreadyRequested)',
            'if (!saveConsent("accepted"))',
            'var saved = saveConsent("rejected");',
            'if (!saved || consentReadFailed) showConsentNotice(hadAdSlot);',
            'function addPreferencesControl()',
            'showConsent(true)',
            'if (saved && hadAdSlot) window.location.reload();',
            'var openPreferences = /(?:^|[?&])ad-preferences=1(?:&|$)/.test(window.location.search);',
            'Your rejection applies to this page, but your browser could not confirm that it saved the preference.',
            'Advertising will remain disabled for this visit.',
            'src: "https://bicea.org/21/"',
        ):
            self.assertIn(snippet, ENGINE)
        self.assertIn("buytools-ad-consent-v1", POLICY)
        self.assertIn("not loaded unless a visitor chooses “Accept advertising”", POLICY)
        self.assertIn("can choose “Reject”", POLICY)
        self.assertIn("a rejection that cannot be saved still keeps advertising disabled for the current page", POLICY)
        self.assertIn("page-level status explains", DOC)
        self.assertIn("Accept advertising", DOC)
        self.assertIn("Reject", DOC)
        self.assertIn("fails closed and does not request new ad delivery", DOC)
        self.assertIn("a previously saved preference, if any, may still be applied on later page loads", DOC)
        self.assertIn("A persistent **Advertising preferences** control", DOC)
        self.assertIn("without clearing all site data", DOC)
        self.assertIn("page reloads so subsequent page loads do not mount the ad slot", DOC)
        self.assertIn("Advertising preferences", POLICY)

    def test_saved_preferences_synchronize_across_open_tabs(self):
        for snippet in (
            'function closeConsentPanel()',
            'function showCrossTabNotice()',
            'function handleConsentStorage(event)',
            'event.key !== CONSENT_KEY && event.key !== null',
            'if (!event.storageArea || event.storageArea !== window.localStorage) return;',
            'if (nextValue === "accepted")',
            'if (hadAdSlot) showCrossTabNotice();',
            'if (nextValue !== "rejected") showConsent(false);',
            'window.addEventListener("storage", handleConsentStorage);',
        ):
            self.assertIn(snippet, ENGINE)
        self.assertIn("synchronize across other open BuyTools.si tabs", DOC)
        self.assertIn("synchronized with other open BuyTools.si tabs", POLICY)
        self.assertIn("rejection removes slots in other tabs without interrupting their current work", DOC)
        self.assertIn("rejection removes existing slots in other tabs without interrupting current work", POLICY)
        self.assertIn("clearing the preference in one tab reopens the prompt in other tabs", DOC)
        self.assertIn("clearing the key reopens the prompt in other tabs", POLICY)
        handler = ENGINE.split("function handleConsentStorage(event) {", 1)[1].split("function showConsent(", 1)[0]
        self.assertNotIn("window.location.reload()", handler)
        self.assertIn("event.storageArea !== window.localStorage", handler)

    def test_documented_placements_and_exclusions_match_source(self):
        self.assertIn('var nativePages = location.pathname === "/" || location.pathname.indexOf("/guides/") === 0;', ENGINE)
        self.assertIn(
            "var size = width < 520 ? [320, 50, units.mobile] : width < 900 ? [300, 250, units.tablet] : [728, 90, units.desktop];",
            ENGINE,
        )
        self.assertIn('SKIP = {"privacy", "terms", "licenses"}', INJECTOR)
        self.assertIn("320 × 50 below 520 px", DOC)
        self.assertIn("300 × 250 from 520 px to below 900 px", DOC)
        self.assertIn("728 × 90 at 900 px or wider", DOC)
        self.assertIn("privacy/", DOC)
        self.assertIn("terms/", DOC)
        self.assertIn("licenses/", DOC)

    def test_documentation_does_not_claim_legal_clearance_or_revenue(self):
        self.assertIn("not a certification of legal compliance", DOC)
        self.assertIn("not a full consent-management platform", DOC)
        self.assertIn("No revenue amount, RPM, approval status or delivery rate is asserted", DOC)
        self.assertIn("AGPL-3.0", DOC)
        self.assertIn("Section 13", DOC)


if __name__ == "__main__":
    unittest.main()
