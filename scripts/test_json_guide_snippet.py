"""Regression tests for the JSON guide search snippet and update metadata."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "guides/format-json-online/index.html").read_text(encoding="utf-8")
SITEMAP = (ROOT / "sitemap.xml").read_text(encoding="utf-8")


class JsonGuideSnippetTests(unittest.TestCase):
    def test_meta_description_matches_search_intent_and_length(self):
        match = re.search(r'<meta name="description" content="([^"]+)"', HTML)
        self.assertIsNotNone(match)
        description = match.group(1)
        self.assertGreaterEqual(len(description), 120)
        self.assertLessEqual(len(description), 160)
        for phrase in ("Format JSON online for free", "local .json file", "JSON syntax", "JSON Schema", "line/column errors", "No upload"):
            self.assertIn(phrase, description)

    def test_open_graph_and_twitter_descriptions_match_meta(self):
        meta = re.search(r'<meta name="description" content="([^"]+)"', HTML).group(1)
        og = re.search(r'<meta property="og:description" content="([^"]+)"', HTML).group(1)
        twitter = re.search(r'<meta name="twitter:description" content="([^"]+)"', HTML).group(1)
        self.assertEqual(og, meta)
        self.assertEqual(twitter, meta)
        self.assertIn('name="twitter:title"', HTML)

    def test_article_modified_date_matches_sitemap(self):
        self.assertIn('"dateModified":"2026-11-12"', HTML)
        pattern = r'<loc>https://buytools\.si/guides/format-json-online/</loc><lastmod>([^<]+)</lastmod>'
        match = re.search(pattern, SITEMAP)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "2026-11-12")

    def test_canonical_and_tool_cta_are_preserved(self):
        self.assertIn('href="https://buytools.si/guides/format-json-online/"', HTML)
        self.assertIn('href="/tools/json-formatter/"', HTML)
        self.assertIn('Open the free JSON formatter', HTML)


if __name__ == "__main__":
    unittest.main()
