"""Unit tests for internal URL fragment validation."""
import unittest

from site_validation import (fragment_target_exists, has_shared_favicon, missing_image_compressor_disclosures, missing_csv_export_safety_disclosures, missing_json_file_workflow_disclosures, missing_batch_image_resizer_disclosures, homepage_tool_count_mismatch, missing_image_lossless_workflow_disclosures, missing_json_schema_scope_disclosures, missing_json_scope_metadata_disclosures, missing_homepage_json_syntax_disclosure)


class SharedFaviconTests(unittest.TestCase):
    def test_shared_svg_favicon_is_accepted(self):
        self.assertTrue(has_shared_favicon(["/assets/favicon.svg"]))

    def test_missing_favicon_is_rejected(self):
        self.assertFalse(has_shared_favicon([]))

    def test_unrelated_icon_path_is_rejected(self):
        self.assertFalse(has_shared_favicon(["/favicon.ico"]))


class FragmentTargetExistsTests(unittest.TestCase):
    def test_empty_fragment_is_valid(self):
        self.assertTrue(fragment_target_exists("", []))

    def test_existing_fragment_is_valid(self):
        self.assertTrue(fragment_target_exists("faq", ["intro", "faq"]))

    def test_missing_fragment_is_rejected(self):
        self.assertFalse(fragment_target_exists("missing", ["intro", "faq"]))

    def test_percent_encoded_fragment_matches_decoded_id(self):
        self.assertTrue(fragment_target_exists("how%20it%20works", ["how it works"]))


class ImageCompressorDisclosureTests(unittest.TestCase):
    def test_complete_output_disclosure_is_accepted(self):
        html = ("The compressor currently exports JPEG files, does not preserve transparency, "
                "and is not a lossless PNG optimizer.")
        self.assertEqual(missing_image_compressor_disclosures(html), [])

    def test_missing_output_format_is_reported(self):
        html = "Does not preserve transparency and is not a lossless PNG optimizer."
        self.assertEqual(missing_image_compressor_disclosures(html), ["currently exports jpeg files"])

    def test_missing_transparency_caveat_is_reported(self):
        html = "Currently exports JPEG files and is not a lossless PNG optimizer."
        self.assertEqual(missing_image_compressor_disclosures(html), ["does not preserve transparency"])

    def test_missing_lossless_caveat_is_reported(self):
        html = "Currently exports JPEG files and does not preserve transparency."
        self.assertEqual(missing_image_compressor_disclosures(html), ["not a lossless png optimizer"])


class BatchImageResizerDisclosureTests(unittest.TestCase):
    def test_accurate_png_resizer_metadata_and_output_disclosure_is_accepted(self):
        html = (
            '<meta name="description" content="Resize multiple images online to fit maximum width and height, '
            'keep aspect ratios, and download PNG results in one ZIP.">' 
            '<meta property="og:description" content="Resize multiple photos to maximum dimensions and '
            'download PNG results together in one ZIP.">' 
            '<p>The resizer exports PNG files. PNG encoding is lossless for the resized image, '
            'but resizing changes its pixel dimensions.</p>'
        )
        self.assertEqual(missing_batch_image_resizer_disclosures(html), [])

    def test_jpeg_compressor_metadata_is_rejected(self):
        html = (
            '<meta name="description" content="Compress multiple images and download JPEGs.">' 
            '<meta property="og:description" content="Compress multiple images into JPEG files.">' 
            '<p>The resizer exports PNG files. PNG encoding is lossless for the resized image, '
            'but resizing changes its pixel dimensions.</p>'
        )
        self.assertEqual(
            missing_batch_image_resizer_disclosures(html),
            [
                "meta description must describe PNG resizing rather than JPEG compression",
                "Open Graph description must describe PNG resizing rather than JPEG compression",
            ],
        )

    def test_incomplete_png_output_explanation_is_rejected(self):
        html = (
            '<meta name="description" content="Resize multiple images online to fit maximum width and height, '
            'keep aspect ratios, and download PNG results in one ZIP.">' 
            '<meta property="og:description" content="Resize multiple photos to maximum dimensions and '
            'download PNG results together in one ZIP.">' 
            '<p>The resizer exports PNG files.</p>'
        )
        self.assertEqual(
            missing_batch_image_resizer_disclosures(html),
            ["visible output-format disclosure must explain PNG encoding and resize dimensions"],
        )


class CsvExportSafetyDisclosureTests(unittest.TestCase):
    def test_complete_disclosure_is_accepted(self):
        html = "Formula-like values get a leading apostrophe as a compatibility safeguard; leading tabs are also handled."
        self.assertEqual(missing_csv_export_safety_disclosures(html), [])

    def test_missing_formula_description_is_reported(self):
        html = "A leading apostrophe is added as a compatibility safeguard."
        self.assertEqual(missing_csv_export_safety_disclosures(html), ["formula-like values", "leading tab"])

    def test_missing_apostrophe_disclosure_is_reported(self):
        html = "Formula-like values are changed as a compatibility safeguard."
        self.assertEqual(missing_csv_export_safety_disclosures(html), ["leading apostrophe", "leading tab"])

    def test_missing_compatibility_caveat_is_reported(self):
        html = "Formula-like values get a leading apostrophe."
        self.assertEqual(missing_csv_export_safety_disclosures(html), ["compatibility safeguard", "leading tab"])

    def test_missing_leading_tab_disclosure_is_reported(self):
        html = "Formula-like values get a leading apostrophe as a compatibility safeguard."
        self.assertEqual(missing_csv_export_safety_disclosures(html), ["leading tab"])


class JsonFileWorkflowDisclosureTests(unittest.TestCase):
    def test_complete_local_file_workflow_is_accepted(self):
        html = (
            "Select a local UTF-8 .json file up to 5 MiB. The browser File API reads it locally; "
            "the file is not uploaded to a BuyTools.si processing endpoint."
        )
        self.assertEqual(missing_json_file_workflow_disclosures(html), [])

    def test_missing_file_size_limit_is_reported(self):
        html = (
            "Select a local UTF-8 .json file. The browser File API reads it locally; "
            "the file is not uploaded to a BuyTools.si processing endpoint."
        )
        self.assertEqual(missing_json_file_workflow_disclosures(html), ["up to 5 mib"])

    def test_missing_local_processing_disclosure_is_reported(self):
        html = "Select a local UTF-8 .json file up to 5 MiB."
        self.assertEqual(
            missing_json_file_workflow_disclosures(html),
            ["browser file api", "not uploaded to a buytools.si processing endpoint"],
        )

    def test_outdated_copy_only_workflow_is_rejected(self):
        html = (
            "Select a local UTF-8 .json file up to 5 MiB. The browser File API reads it locally; "
            "the file is not uploaded to a BuyTools.si processing endpoint. "
            "The tool accepts pasted text rather than a direct file upload."
        )
        self.assertEqual(
            missing_json_file_workflow_disclosures(html),
            ["outdated copy-only file workflow disclosure"],
        )


class JsonSchemaScopeDisclosureTests(unittest.TestCase):
    COMPLETE = (
        "The formatter checks JSON syntax only. It does not validate JSON Schema, "
        "required fields, expected value types or an API contract."
    )

    def test_complete_schema_scope_disclosure_is_accepted(self):
        self.assertEqual(missing_json_schema_scope_disclosures(self.COMPLETE), [])

    def test_missing_schema_validation_limit_is_reported(self):
        html = self.COMPLETE.replace("does not validate JSON Schema, ", "")
        self.assertEqual(
            missing_json_schema_scope_disclosures(html),
            ["does not validate json schema"],
        )

    def test_missing_api_contract_limit_is_reported(self):
        html = self.COMPLETE.replace("or an API contract", "")
        self.assertEqual(
            missing_json_schema_scope_disclosures(html),
            ["api contract"],
        )


class JsonMetadataScopeDisclosureTests(unittest.TestCase):
    COMPLETE = (
        '<meta name="description" content="Format and validate JSON syntax in your browser; '
        'JSON Schema and API rules are not checked.">'
        '<meta property="og:description" content="Format JSON syntax and distinguish JSON Schema validation.">'
    )

    def test_both_descriptions_explain_syntax_and_schema_scope(self):
        self.assertEqual(missing_json_scope_metadata_disclosures(self.COMPLETE), [])

    def test_missing_schema_scope_in_meta_description_is_reported(self):
        html = self.COMPLETE.replace("JSON Schema and API rules are not checked.", "API rules are not checked.")
        self.assertEqual(
            missing_json_scope_metadata_disclosures(html),
            ["meta description must distinguish JSON Schema validation"],
        )

    def test_missing_syntax_scope_in_open_graph_description_is_reported(self):
        html = self.COMPLETE.replace("Format JSON syntax and distinguish", "Format JSON and distinguish")
        self.assertEqual(
            missing_json_scope_metadata_disclosures(html),
            ["Open Graph description must describe JSON syntax validation"],
        )


class HomepageJsonSyntaxDisclosureTests(unittest.TestCase):
    COMPLETE = (
        "<script>const tools=[{id:'json',name:'JSON Formatter',cat:'Developer',"
        "desc:'Format, check JSON syntax and minify JSON data.',"
        "tags:'developer code json syntax check validate pretty print'}];</script>"
    )

    def test_json_card_description_and_search_tags_identify_syntax(self):
        self.assertEqual(missing_homepage_json_syntax_disclosure(self.COMPLETE), [])

    def test_missing_syntax_in_description_is_reported(self):
        html = self.COMPLETE.replace("check JSON syntax", "validate")
        self.assertEqual(
            missing_homepage_json_syntax_disclosure(html),
            ["description must identify JSON syntax checking"],
        )

    def test_missing_syntax_search_tag_is_reported(self):
        html = self.COMPLETE.replace("json syntax check", "developer syntax check")
        self.assertEqual(
            missing_homepage_json_syntax_disclosure(html),
            ["search tags must include JSON syntax"],
        )

    def test_missing_json_card_is_reported(self):
        self.assertEqual(
            missing_homepage_json_syntax_disclosure("<script>const tools=[];</script>"),
            ["Homepage JSON Formatter catalogue entry is missing."],
        )


class HomepageToolCountTests(unittest.TestCase):
    def test_matching_static_count_is_accepted(self):
        html = '<span class="pill" id="count">2 tools</span><script>const tools=[{id:\'one\'},{id:\'two\'}\n];</script>'
        self.assertIsNone(homepage_tool_count_mismatch(html))

    def test_stale_static_count_is_reported(self):
        html = '<span class="pill" id="count">16 tools</span><script>const tools=[{id:\'one\'},{id:\'two\'}\n];</script>'
        self.assertEqual(
            homepage_tool_count_mismatch(html),
            "Homepage static count says 16 tools, but the catalogue contains 2 entries.",
        )

    def test_missing_count_label_is_reported(self):
        html = '<script>const tools=[{id:\'one\'}\n];</script>'
        self.assertEqual(
            homepage_tool_count_mismatch(html),
            "Homepage static tool count label is missing or malformed.",
        )

class ImageLosslessWorkflowDisclosureTests(unittest.TestCase):
    COMPLETE = (
        "<p>BuyTools.si does not currently offer a pixel-preserving lossless image optimizer. "
        "Lossless optimization keeps the original pixel dimensions and decoded pixel values. "
        "The Image Compressor exports lossy JPEG files. "
        "The Image Resizer exports PNG files but changes pixel dimensions. "
        "Keep an untouched original copy. Metadata removal can remove EXIF, orientation or "
        "color-profile information.</p>"
    )

    def test_complete_lossless_workflow_disclosure_is_accepted(self):
        self.assertEqual(missing_image_lossless_workflow_disclosures(self.COMPLETE), [])

    def test_missing_product_limitation_is_reported(self):
        html = self.COMPLETE.replace(
            "does not currently offer a pixel-preserving lossless image optimizer",
            "offers a lossless image optimizer",
        )
        self.assertEqual(
            missing_image_lossless_workflow_disclosures(html),
            ["does not currently offer a pixel-preserving lossless image optimizer"],
        )

    def test_missing_metadata_caveat_is_reported(self):
        html = self.COMPLETE.replace(
            "Metadata removal can remove EXIF, orientation or color-profile information.",
            "",
        )
        self.assertEqual(
            missing_image_lossless_workflow_disclosures(html),
            ["can remove exif, orientation or color-profile information"],
        )


if __name__ == "__main__":
    unittest.main()
