"""Unit tests for internal URL fragment validation."""
import unittest

from site_validation import (fragment_target_exists, has_shared_favicon, missing_image_compressor_disclosures, missing_csv_export_safety_disclosures, missing_json_file_workflow_disclosures, missing_batch_image_resizer_disclosures)


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


if __name__ == "__main__":
    unittest.main()
