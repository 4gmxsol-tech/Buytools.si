"""Regression tests for the JSON Formatter's explicit validation action."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


class JsonFormatterValidationActionTests(unittest.TestCase):
    def test_validate_button_is_exposed_with_a_clear_label(self):
        self.assertRegex(
            HTML,
            r'<button class="close" data-json="validate">Validate JSON</button>',
        )

    def test_validate_action_parses_without_rewriting_the_editor(self):
        self.assertIn(
            "if(b.dataset.json==='validate'){$('#result').textContent='Valid JSON ✓';return}",
            HTML,
        )

    def test_format_and_minify_actions_remain_available(self):
        self.assertIn('data-json="pretty">Format JSON</button>', HTML)
        self.assertIn('data-json="min">Minify</button>', HTML)
        self.assertIn("JSON.stringify(parsed,null,2)", HTML)
        self.assertIn("JSON.stringify(parsed)", HTML)

    def test_file_load_message_lists_all_three_actions(self):
        self.assertIn("Select Format, Validate or Minify to continue.", HTML)

    def test_result_is_announced_to_assistive_technology(self):
        self.assertIn(
            'id="result" role="status" aria-live="polite"',
            HTML,
        )

    def test_invalid_json_still_returns_a_parser_error(self):
        self.assertIn(
            "$('#result').textContent='Invalid JSON: '+e.message",
            HTML,
        )


if __name__ == "__main__":
    unittest.main()
