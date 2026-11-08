"""Unit tests for internal URL fragment validation."""
import unittest

from site_validation import (fragment_target_exists, has_shared_favicon, known_analytics_or_ad_markers, missing_no_analytics_disclosure, missing_image_compressor_disclosures, missing_csv_export_safety_disclosures, missing_json_file_workflow_disclosures, missing_batch_image_resizer_disclosures, homepage_tool_count_mismatch, missing_image_lossless_workflow_disclosures, missing_json_schema_scope_disclosures, missing_json_scope_metadata_disclosures, missing_homepage_json_syntax_disclosure, missing_license_footer_link, missing_direct_browser_package_notices, missing_runtime_dependency_notices, missing_upstream_lock_evidence, missing_confirmed_bundled_license_notices, has_head_license_declaration, missing_sitemap_lastmod_sync, noncanonical_internal_index_links, missing_pages_workflow_least_privilege, missing_immutable_action_pins)


class SharedFaviconTests(unittest.TestCase):
    def test_shared_svg_favicon_is_accepted(self):
        self.assertTrue(has_shared_favicon(["/assets/favicon.svg"]))

    def test_missing_favicon_is_rejected(self):
        self.assertFalse(has_shared_favicon([]))

    def test_unrelated_icon_path_is_rejected(self):
        self.assertFalse(has_shared_favicon(["/favicon.ico"]))


class CanonicalInternalIndexLinkTests(unittest.TestCase):
    def test_canonical_trailing_slash_link_is_accepted(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["/tools/csv-viewer/"],
                "https://buytools.si/tools/json-formatter/",
            ),
            [],
        )

    def test_absolute_same_site_index_alias_is_reported(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["https://buytools.si/tools/remove-background/index.html"],
                "https://buytools.si/",
            ),
            ["https://buytools.si/tools/remove-background/index.html"],
        )

    def test_relative_same_site_index_alias_is_reported(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["../remove-background/index.html"],
                "https://buytools.si/tools/images-to-pdf/",
            ),
            ["../remove-background/index.html"],
        )

    def test_root_index_alias_is_reported(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["/index.html?source=nav#top"],
                "https://buytools.si/tools/csv-viewer/",
            ),
            ["/index.html?source=nav#top"],
        )

    def test_external_index_html_link_is_not_reported(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["https://cdn.example.test/docs/index.html"],
                "https://buytools.si/",
            ),
            [],
        )

    def test_non_http_links_are_not_reported(self):
        self.assertEqual(
            noncanonical_internal_index_links(
                ["mailto:help@buytools.si", "tel:+10000000000", "#faq"],
                "https://buytools.si/tools/csv-viewer/",
            ),
            [],
        )


class FragmentTargetExistsTests(unittest.TestCase):
    def test_empty_fragment_is_valid(self):
        self.assertTrue(fragment_target_exists("", []))

    def test_existing_fragment_is_valid(self):
        self.assertTrue(fragment_target_exists("faq", ["intro", "faq"]))

    def test_missing_fragment_is_rejected(self):
        self.assertFalse(fragment_target_exists("missing", ["intro", "faq"]))

    def test_percent_encoded_fragment_matches_decoded_id(self):
        self.assertTrue(fragment_target_exists("how%20it%20works", ["how it works"]))




class PrivacyStatusDisclosureTests(unittest.TestCase):
    COMPLETE = (
        "<p>No third-party advertising or site-analytics scripts, pixels, or ad tags are "
        "currently loaded by BuyTools.si. This does not mean that no technical data is "
        "processed: the static hosting provider may process technical information for "
        "security and delivery. Update this policy before activation if advertising or "
        "analytics are added.</p>"
    )

    def test_explicit_current_privacy_status_is_accepted(self):
        self.assertEqual(missing_no_analytics_disclosure(self.COMPLETE), [])

    def test_missing_current_status_is_reported(self):
        html = self.COMPLETE.replace(
            "No third-party advertising or site-analytics scripts, pixels, or ad tags are currently loaded by BuyTools.si. ",
            "",
        )
        self.assertEqual(
            missing_no_analytics_disclosure(html),
            ["no third-party advertising or site-analytics scripts, pixels, or ad tags are currently loaded by buytools.si"],
        )

    def test_known_analytics_tags_are_detected(self):
        html = '<script src="https://www.googletagmanager.com/gtag/js"></script><script>gtag("config","G-TEST")</script>'
        self.assertEqual(
            known_analytics_or_ad_markers(html),
            ["googletagmanager.com", "gtag("],
        )

    def test_known_advertising_tags_are_detected(self):
        html = '<ins class="adsbygoogle"></ins><script src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script>'
        self.assertEqual(
            known_analytics_or_ad_markers(html),
            ["pagead2.googlesyndication.com", "googlesyndication.com", "adsbygoogle"],
        )

    def test_generic_future_policy_wording_is_not_a_tracking_marker(self):
        self.assertEqual(
            known_analytics_or_ad_markers("<p>Advertising and analytics may be introduced later.</p>"),
            [],
        )


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


class LicenseDiscoveryLinkTests(unittest.TestCase):
    def test_license_link_in_footer_is_accepted(self):
        html = '<footer><a href="/privacy/">Privacy</a><a href="/licenses/">Licenses</a></footer>'
        self.assertIsNone(missing_license_footer_link(html))

    def test_missing_license_link_is_reported(self):
        html = '<footer><a href="/privacy/">Privacy</a></footer>'
        self.assertEqual(missing_license_footer_link(html), "Page footer must link to /licenses/.")

    def test_link_outside_footer_does_not_satisfy_check(self):
        html = '<a href="/licenses/">Licenses</a><footer><a href="/privacy/">Privacy</a></footer>'
        self.assertEqual(missing_license_footer_link(html), "Page footer must link to /licenses/.")

    def test_missing_footer_is_reported(self):
        self.assertEqual(missing_license_footer_link('<main>Content</main>'), "Page footer is missing.")




class HeadLicenseDeclarationTests(unittest.TestCase):
    def test_document_level_license_in_head_is_detected(self):
        html = '<head><link rel="license" href="https://www.gnu.org/licenses/agpl-3.0.html"></head>'
        self.assertTrue(has_head_license_declaration(html))

    def test_component_license_link_in_body_is_not_document_level(self):
        html = '<head></head><body><a rel="license" href="https://opensource.org/license/mit/">MIT</a></body>'
        self.assertFalse(has_head_license_declaration(html))

    def test_license_token_is_detected_with_other_rel_tokens(self):
        html = '<head><link rel="alternate license" href="/license"></head>'
        self.assertTrue(has_head_license_declaration(html))

    def test_missing_head_does_not_create_a_license_declaration(self):
        self.assertFalse(has_head_license_declaration('<body>Notices</body>'))


class DirectBrowserPackageNoticeTests(unittest.TestCase):
    SITE_IMPORTS = """
    <script>
    const pdf = await import('https://esm.sh/pdf-lib@1.17.1');
    const zip = await import("https://esm.sh/jszip@3.10.2?target=es2022");
    const image = await import('https://esm.sh/@imgly/background-removal@1.5.5');
    const output = await import('https://esm.sh/jspdf@4.2.1');
    </script>
    """
    LICENSE_NOTICES = """
    <h3>pdf-lib — version 1.17.1</h3>
    <h3>JSZip — version 3.10.2</h3>
    <h3>@imgly/background-removal — version 1.5.5</h3>
    <h3>jsPDF — version 4.2.1</h3>
    """

    def test_all_direct_package_versions_are_inventoried(self):
        self.assertEqual(
            missing_direct_browser_package_notices(self.SITE_IMPORTS, self.LICENSE_NOTICES),
            [],
        )

    def test_scoped_package_is_matched_as_a_single_package_name(self):
        html = "await import('https://esm.sh/@imgly/background-removal@1.5.5')"
        notice = "<h3>@imgly/background-removal — version 1.5.5</h3>"
        self.assertEqual(missing_direct_browser_package_notices(html, notice), [])

    def test_missing_package_notice_is_reported(self):
        notices = self.LICENSE_NOTICES.replace("<h3>JSZip — version 3.10.2</h3>", "")
        self.assertEqual(
            missing_direct_browser_package_notices(self.SITE_IMPORTS, notices),
            ["License notice missing exact package/version: jszip@3.10.2"],
        )

    def test_version_mismatch_is_reported(self):
        notices = self.LICENSE_NOTICES.replace("pdf-lib — version 1.17.1", "pdf-lib — version 1.17.0")
        self.assertEqual(
            missing_direct_browser_package_notices(self.SITE_IMPORTS, notices),
            ["License notice missing exact package/version: pdf-lib@1.17.1"],
        )

    def test_unpinned_import_is_rejected(self):
        html = "await import('https://esm.sh/example-package')"
        self.assertEqual(
            missing_direct_browser_package_notices(html, self.LICENSE_NOTICES),
            ["Direct esm.sh package import must pin a version: example-package"],
        )


class RuntimeDependencyNoticeTests(unittest.TestCase):
    MANIFEST = {
        "schemaVersion": 1,
        "observedModules": [
            {
                "name": "onnxruntime-web",
                "resolvedVersion": "1.18.0",
                "license": "MIT",
                "npmUrl": "https://www.npmjs.com/package/onnxruntime-web/v/1.18.0",
            },
            {
                "name": "zod",
                "resolvedVersion": "3.25.76",
                "license": "MIT",
                "npmUrl": "https://www.npmjs.com/package/zod/v/3.25.76",
            },
        ],
    }
    COMPLETE = """
    <section id="background-removal-runtime">
      <h3>onnxruntime-web — version 1.18.0</h3>
      <p>License: MIT</p>
      <a href="https://www.npmjs.com/package/onnxruntime-web/v/1.18.0">Package</a>
      <h3>zod — version 3.25.76</h3>
      <p>License: MIT</p>
      <a href="https://www.npmjs.com/package/zod/v/3.25.76">Package</a>
    </section>
    """

    def test_complete_runtime_inventory_is_accepted(self):
        self.assertEqual(missing_runtime_dependency_notices(self.MANIFEST, self.COMPLETE), [])

    def test_missing_runtime_section_is_reported(self):
        html = self.COMPLETE.replace('id="background-removal-runtime"', 'id="other-section"')
        self.assertIn(
            "License page is missing the background-removal runtime inventory section.",
            missing_runtime_dependency_notices(self.MANIFEST, html),
        )

    def test_missing_resolved_package_version_is_reported(self):
        html = self.COMPLETE.replace("zod — version 3.25.76", "zod — version 3.25.75")
        self.assertIn(
            "Runtime dependency license notice missing exact package/version: zod@3.25.76",
            missing_runtime_dependency_notices(self.MANIFEST, html),
        )

    def test_missing_license_metadata_link_is_reported(self):
        html = self.COMPLETE.replace('href="https://www.npmjs.com/package/zod/v/3.25.76"', 'href="/licenses/"')
        self.assertIn(
            "Runtime dependency license notice missing versioned npm metadata link: zod@3.25.76",
            missing_runtime_dependency_notices(self.MANIFEST, html),
        )

    def test_unsupported_manifest_schema_is_rejected(self):
        manifest = dict(self.MANIFEST, schemaVersion=2)
        self.assertEqual(
            missing_runtime_dependency_notices(manifest, self.COMPLETE),
            ["Runtime dependency baseline is missing or has an unsupported schema version."],
        )


class UpstreamLockEvidenceTests(unittest.TestCase):
    COMPLETE = {
        "upstreamLockEvidence": {
            "sourceUrl": "https://raw.githubusercontent.com/microsoft/onnxruntime/v1.18.0/js/web/package-lock.json",
            "sourceTag": "v1.18.0",
            "lockfileVersion": 2,
            "requiredPackageNames": ["protobufjs", "@protobufjs/utf8"],
            "packages": [
                {"name":"protobufjs","version":"7.2.5","license":"BSD-3-Clause","lockPath":"node_modules/protobufjs","resolutionType":"npm-registry-tarball","resolved":"https://registry.npmjs.org/protobufjs/-/protobufjs-7.2.5.tgz","integrity":"sha512-test","npmUrl":"https://www.npmjs.com/package/protobufjs/v/7.2.5"},
                {"name":"@protobufjs/utf8","version":"1.1.0","license":"BSD-3-Clause","lockPath":"node_modules/@protobufjs/utf8","resolutionType":"npm-registry-tarball","resolved":"https://registry.npmjs.org/@protobufjs/utf8/-/utf8-1.1.0.tgz","integrity":"sha512-test","npmUrl":"https://www.npmjs.com/package/@protobufjs/utf8/v/1.1.0"},
            ],
        },
        "observedModules": [
            {"name":"onnxruntime-web","resolvedVersion":"1.18.0","modulePaths":["/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs","/onnxruntime-web@1.18.0/es2022/webgpu.mjs"]}
        ],
        "observedEsmShResponseEvidence": {
            "workflowRunId": 123,
            "workflowRunUrl": "https://github.com/4gmxsol-tech/Buytools.si/actions/runs/123",
            "capturedAt": "2026-11-08T00:00:00Z",
            "modules": [
                {
                    "kind": "CPU ESM",
                    "url": "https://esm.sh/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs",
                    "browserResponseSha256": "a" * 64,
                    "refetchedResponseSha256": "a" * 64,
                    "responseHashMatch": True,
                    "sourceMapReferenceKind": "response-comment",
                    "sourceMapUrl": "https://esm.sh/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs.map",
                    "sourceMapHttpStatus": 200,
                    "sourceMapSha256": "b" * 64,
                    "sourceMapSourceCount": 146,
                    "upstreamSourceMapUrl": "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.min.js.map",
                    "upstreamSourceMapHttpStatus": 200,
                    "upstreamSourceMapSha256": "c" * 64,
                    "upstreamSourceMapSourceCount": 146,
                    "sourceCountMatchesUpstream": True,
                    "packagePathSignalParity": True,
                    "sourcePathSignals": {"protobufReader": True, "protobufWriter": True, "protobufUtf8": True, "flatbuffers": True, "long": True, "guidTypescript": True, "onnxruntimeCommon": True}
                },
                {
                    "kind": "WebGPU ESM",
                    "url": "https://esm.sh/onnxruntime-web@1.18.0/es2022/webgpu.mjs",
                    "browserResponseSha256": "d" * 64,
                    "refetchedResponseSha256": "d" * 64,
                    "responseHashMatch": True,
                    "sourceMapReferenceKind": "response-comment",
                    "sourceMapUrl": "https://esm.sh/onnxruntime-web@1.18.0/es2022/webgpu.mjs.map",
                    "sourceMapHttpStatus": 200,
                    "sourceMapSha256": "e" * 64,
                    "sourceMapSourceCount": 99,
                    "upstreamSourceMapUrl": "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.webgpu.min.js.map",
                    "upstreamSourceMapHttpStatus": 200,
                    "upstreamSourceMapSha256": "f" * 64,
                    "upstreamSourceMapSourceCount": 99,
                    "sourceCountMatchesUpstream": True,
                    "packagePathSignalParity": True,
                    "sourcePathSignals": {"protobufReader": False, "protobufWriter": False, "protobufUtf8": False, "flatbuffers": False, "long": False, "guidTypescript": False, "onnxruntimeCommon": True}
                }
            ]
        },
        "unresolvedBundledDependencies": [
            {"name":"protobufjs","upstreamLockedVersion":"7.2.5","license":"BSD-3-Clause","npmUrl":"https://www.npmjs.com/package/protobufjs/v/7.2.5","runtimeObservation":"Not individually observed as a separate esm.sh browser module; the upstream CPU ESM source map includes protobufjs reader/writer source paths. The transformed esm.sh response has not been byte-compared."}
        ],
        "upstreamBundleEvidence": {
            "packageManifestUrl":"https://unpkg.com/onnxruntime-web@1.18.0/package.json",
            "cpuEsmExport":"./dist/esm/ort.min.js",
            "cpuSourceMapUrl":"https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.min.js.map",
            "cpuSourcePaths":[
                "../../node_modules/protobufjs/src/reader.js",
                "../../node_modules/protobufjs/src/writer.js",
                "../../node_modules/@protobufjs/utf8/index.js"
            ],
            "webgpuEsmExport":"./dist/esm/ort.webgpu.min.js",
            "webgpuSourceMapUrl":"https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.webgpu.min.js.map",
            "webgpuProtobufSourcePaths":[],
            "confirmedBundledPackages":[
                {"name":"protobufjs","version":"7.2.5","license":"BSD-3-Clause","sourcePaths":["../../node_modules/protobufjs/src/reader.js","../../node_modules/protobufjs/src/writer.js"]},
                {"name":"@protobufjs/utf8","version":"1.1.0","license":"BSD-3-Clause","sourcePaths":["../../node_modules/@protobufjs/utf8/index.js"]}
            ],
            "unconfirmedLockPackages":[],
            "scopeNote":"Upstream source-map evidence only; not a byte-for-byte comparison of the esm.sh transformed response observed by BuyTools CI.",
            "runtimeHashNote":"BuyTools CI records SHA-256 hashes for observed esm.sh module response bodies; no runtime Subresource Integrity is claimed."
        },
        "securityReview": {
            "transitiveAdvisories": [
                {"package":"protobufjs","version":"7.2.5","advisoryUrl":"https://github.com/advisories/GHSA-xq3m-2v4x-88gg","affectedRange":"<7.5.5","patchedVersion":"7.5.5","preconditions":"Untrusted schema input.","buytoolsAssessment":"No user-supplied schema path identified."}
            ],
            "transitiveExposureConclusion":"Conditional exposure; no exploit demonstrated.",
        },
    }

    def test_complete_upstream_lock_evidence_is_accepted(self):
        self.assertEqual(missing_upstream_lock_evidence(self.COMPLETE), [])

    def test_missing_esm_sh_response_evidence_is_reported(self):
        manifest = dict(self.COMPLETE)
        manifest.pop("observedEsmShResponseEvidence")
        self.assertIn("Exact esm.sh ONNX Runtime response evidence is missing.", missing_upstream_lock_evidence(manifest))

    def test_same_run_response_hashes_must_match(self):
        manifest = dict(self.COMPLETE)
        evidence = dict(self.COMPLETE["observedEsmShResponseEvidence"])
        modules = [dict(item) for item in evidence["modules"]]
        modules[0]["refetchedResponseSha256"] = "0" * 64
        evidence["modules"] = modules
        manifest["observedEsmShResponseEvidence"] = evidence
        self.assertIn("Same-run Chromium/refetch SHA-256 evidence does not match for CPU ESM.", missing_upstream_lock_evidence(manifest))

    def test_webgpu_map_must_not_claim_protobuf_sources(self):
        manifest = dict(self.COMPLETE)
        evidence = dict(self.COMPLETE["observedEsmShResponseEvidence"])
        modules = [dict(item) for item in evidence["modules"]]
        modules[1]["sourcePathSignals"] = dict(modules[1]["sourcePathSignals"], protobufReader=True)
        evidence["modules"] = modules
        manifest["observedEsmShResponseEvidence"] = evidence
        self.assertIn("WebGPU esm.sh source map must not claim protobufReader.", missing_upstream_lock_evidence(manifest))

    def test_missing_upstream_lockfile_source_is_reported(self):
        manifest = dict(self.COMPLETE)
        manifest["upstreamLockEvidence"] = dict(self.COMPLETE["upstreamLockEvidence"], sourceUrl="")
        self.assertIn("Upstream lockfile source must identify ONNX Runtime v1.18.0 js/web/package-lock.json.", missing_upstream_lock_evidence(manifest))

    def test_unresolved_version_must_match_source_lock(self):
        manifest = dict(self.COMPLETE)
        manifest["unresolvedBundledDependencies"] = [dict(self.COMPLETE["unresolvedBundledDependencies"][0], upstreamLockedVersion="7.2.4")]
        self.assertIn("Upstream locked version mismatch for protobufjs.", missing_upstream_lock_evidence(manifest))

    def test_advisory_requires_exploit_preconditions_and_assessment(self):
        manifest = dict(self.COMPLETE)
        security = dict(self.COMPLETE["securityReview"])
        security["transitiveAdvisories"] = [dict(self.COMPLETE["securityReview"]["transitiveAdvisories"][0], preconditions="")]
        manifest["securityReview"] = security
        self.assertIn("Transitive advisory record is missing preconditions: protobufjs.", missing_upstream_lock_evidence(manifest))

    def test_cpu_source_map_requires_protobuf_reader_and_utf8_sources(self):
        manifest = dict(self.COMPLETE)
        bundle = dict(self.COMPLETE["upstreamBundleEvidence"])
        bundle["cpuSourcePaths"] = [path for path in bundle["cpuSourcePaths"] if "protobufjs/src/reader.js" not in path]
        manifest["upstreamBundleEvidence"] = bundle
        self.assertIn("ONNX Runtime CPU source map must include protobufjs reader code.", missing_upstream_lock_evidence(manifest))

    def test_webgpu_source_map_cannot_claim_protobuf_sources_without_evidence(self):
        manifest = dict(self.COMPLETE)
        bundle = dict(self.COMPLETE["upstreamBundleEvidence"], webgpuProtobufSourcePaths=["../../node_modules/protobufjs/src/reader.js"])
        manifest["upstreamBundleEvidence"] = bundle
        self.assertIn("WebGPU source-map review must not claim protobufjs/@protobufjs source paths.", missing_upstream_lock_evidence(manifest))

    def test_confirmed_bundle_version_must_match_source_lock(self):
        manifest = dict(self.COMPLETE)
        bundle = dict(self.COMPLETE["upstreamBundleEvidence"])
        bundle["confirmedBundledPackages"] = [
            dict(bundle["confirmedBundledPackages"][0], version="7.2.4"),
            bundle["confirmedBundledPackages"][1],
        ]
        manifest["upstreamBundleEvidence"] = bundle
        self.assertIn("Confirmed bundled dependency version/license differs from source-lock evidence: protobufjs.", missing_upstream_lock_evidence(manifest))

    def test_scope_note_must_not_overstate_esm_sh_identity(self):
        manifest = dict(self.COMPLETE)
        bundle = dict(self.COMPLETE["upstreamBundleEvidence"], scopeNote="The upstream map is identical to the transformed response.")
        manifest["upstreamBundleEvidence"] = bundle
        self.assertIn("Bundle source-map scope note must distinguish upstream evidence from the esm.sh transformed response.", missing_upstream_lock_evidence(manifest))

    def test_duplicate_package_records_are_rejected(self):
        manifest = dict(self.COMPLETE)
        evidence = dict(self.COMPLETE["upstreamLockEvidence"])
        evidence["packages"] = evidence["packages"] + [dict(evidence["packages"][0])]
        manifest["upstreamLockEvidence"] = evidence
        self.assertIn("Duplicate upstream lockfile package record: protobufjs.", missing_upstream_lock_evidence(manifest))


class ConfirmedBundledLicenseNoticeTests(unittest.TestCase):
    MANIFEST = {
        "upstreamLockEvidence": {
            "packages": [
                {"name": "protobufjs", "npmUrl": "https://www.npmjs.com/package/protobufjs/v/7.2.5"},
                {"name": "guid-typescript", "npmUrl": "https://www.npmjs.com/package/guid-typescript/v/1.0.9"}
            ]
        },
        "upstreamBundleEvidence": {
            "confirmedBundledPackages": [
                {"name": "protobufjs", "version": "7.2.5", "license": "BSD-3-Clause"},
                {"name": "guid-typescript", "version": "1.0.9", "license": "ISC"}
            ]
        }
    }
    HTML = """
    <section id="onnxruntime-transitive-notices">
      protobufjs — version 7.2.5 BSD-3-Clause
      https://www.npmjs.com/package/protobufjs/v/7.2.5
      Copyright (c) 2016, Daniel Wirtz
      guid-typescript — version 1.0.9 ISC
      https://www.npmjs.com/package/guid-typescript/v/1.0.9
      Copyright (c) Nicolas Silva dos Santos
      https://spdx.org/licenses/BSD-3-Clause.html
      https://spdx.org/licenses/ISC.html
    </section>
    """

    def test_complete_versioned_transitive_notices_are_accepted(self):
        self.assertEqual(missing_confirmed_bundled_license_notices(self.MANIFEST, self.HTML), [])

    def test_missing_exact_package_version_is_reported(self):
        html = self.HTML.replace("guid-typescript — version 1.0.9", "guid-typescript")
        self.assertIn(
            "Public transitive license notice missing exact package/version: guid-typescript@1.0.9",
            missing_confirmed_bundled_license_notices(self.MANIFEST, html),
        )

    def test_missing_copyright_attribution_is_reported(self):
        html = self.HTML.replace("Nicolas Silva dos Santos", "Unknown")
        self.assertTrue(any("missing copyright attribution" in item for item in missing_confirmed_bundled_license_notices(self.MANIFEST, html)))




class SitemapLastmodSyncTests(unittest.TestCase):
    SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://buytools.si/licenses/</loc><lastmod>2026-11-08</lastmod></url>
    </urlset>"""
    PAGE = "<p><strong>Last updated: November 8, 2026</strong></p>"

    def test_matching_visible_date_and_sitemap_lastmod_are_accepted(self):
        self.assertEqual(
            missing_sitemap_lastmod_sync(self.SITEMAP, "https://buytools.si/licenses/", self.PAGE),
            [],
        )

    def test_stale_sitemap_lastmod_is_reported(self):
        stale = self.SITEMAP.replace("2026-11-08", "2026-11-07")
        self.assertEqual(
            missing_sitemap_lastmod_sync(stale, "https://buytools.si/licenses/", self.PAGE),
            ["sitemap lastmod 2026-11-07 does not match visible page date 2026-11-08"],
        )

    def test_missing_sitemap_entry_is_reported(self):
        self.assertEqual(
            missing_sitemap_lastmod_sync(
                self.SITEMAP,
                "https://buytools.si/privacy/",
                self.PAGE,
            ),
            ["page URL is missing from sitemap"],
        )

    def test_missing_visible_date_is_reported(self):
        self.assertEqual(
            missing_sitemap_lastmod_sync(self.SITEMAP, "https://buytools.si/licenses/", "<p>No date.</p>"),
            ["page is missing a visible 'Last updated: Month D, YYYY' date"],
        )

    def test_invalid_sitemap_xml_is_reported(self):
        self.assertEqual(
            missing_sitemap_lastmod_sync("<urlset>", "https://buytools.si/licenses/", self.PAGE),
            ["sitemap XML cannot be parsed"],
        )



class PagesWorkflowLeastPrivilegeTests(unittest.TestCase):
    WORKFLOW = """name: Deploy BuyTools.si to GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions: {}
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: read
    steps:
      - uses: actions/checkout@v5
      - uses: actions/configure-pages@v6
  deploy:
    environment:
      name: github-pages
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    needs: build
    steps:
      - uses: actions/checkout@v5
      - uses: actions/deploy-pages@v5
"""

    def test_minimal_job_scoped_permissions_are_accepted(self):
        self.assertEqual(missing_pages_workflow_least_privilege(self.WORKFLOW), [])

    def test_workflow_level_write_permissions_are_rejected(self):
        unsafe = self.WORKFLOW.replace(
            "permissions: {}",
            "permissions:\n  pages: write\n  id-token: write",
        )
        self.assertIn(
            "workflow-level permissions must be empty so job permissions are explicit",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_build_job_pages_write_is_rejected(self):
        unsafe = self.WORKFLOW.replace("      pages: read", "      pages: write")
        self.assertIn(
            "build job must have only contents:read and pages:read permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_build_job_oidc_write_is_rejected(self):
        unsafe = self.WORKFLOW.replace(
            "      pages: read",
            "      pages: read\n      id-token: write",
        )
        self.assertIn(
            "build job must have only contents:read and pages:read permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_build_job_requires_pages_read(self):
        unsafe = self.WORKFLOW.replace("      pages: read\n", "")
        self.assertIn(
            "build job must have only contents:read and pages:read permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_deploy_job_requires_pages_write(self):
        unsafe = self.WORKFLOW.replace("      pages: write\n", "      pages: read\n")
        self.assertIn(
            "deploy job must have contents:read, pages:write and id-token:write permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_deploy_job_requires_oidc_write(self):
        unsafe = self.WORKFLOW.replace("      id-token: write", "      id-token: read")
        self.assertIn(
            "deploy job must have contents:read, pages:write and id-token:write permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )

    def test_extra_deploy_permission_is_rejected(self):
        unsafe = self.WORKFLOW.replace(
            "      contents: read\n      pages: write",
            "      contents: read\n      actions: write\n      pages: write",
        )
        self.assertIn(
            "deploy job must have contents:read, pages:write and id-token:write permissions",
            missing_pages_workflow_least_privilege(unsafe),
        )



class ImmutableGitHubActionPinTests(unittest.TestCase):
    def test_full_commit_sha_with_version_annotation_is_accepted(self):
        workflow = "steps:\\n  - uses: actions/checkout@" + ("a" * 40) + " # v5\\n"
        self.assertEqual(missing_immutable_action_pins(workflow), [])

    def test_major_version_tag_is_rejected(self):
        errors = missing_immutable_action_pins("steps:\\n  - uses: actions/checkout@v5\\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("must use a full 40-character commit SHA", errors[0])

    def test_short_commit_sha_is_rejected(self):
        errors = missing_immutable_action_pins("steps:\\n  - uses: actions/checkout@abc1234 # v5\\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("must use a full 40-character commit SHA", errors[0])

    def test_missing_upstream_version_annotation_is_rejected(self):
        errors = missing_immutable_action_pins(
            "steps:\\n  - uses: actions/checkout@" + ("a" * 40) + "\\n"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("must include an upstream version annotation", errors[0])

    def test_local_composite_action_is_accepted(self):
        self.assertEqual(
            missing_immutable_action_pins("steps:\\n  - uses: ./.github/actions/test\\n"),
            [],
        )

    def test_docker_action_requires_sha256_digest(self):
        errors = missing_immutable_action_pins("steps:\\n  - uses: docker://alpine:3.20\\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("immutable sha256 digest", errors[0])

    def test_docker_action_with_sha256_digest_is_accepted(self):
        digest = "a" * 64
        self.assertEqual(
            missing_immutable_action_pins("steps:\\n  - uses: docker://alpine:3.20@sha256:" + digest + "\\n"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
