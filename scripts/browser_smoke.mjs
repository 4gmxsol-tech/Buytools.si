import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { createRequire } from "node:module";

const runtimeBaseline = JSON.parse(await readFile(new URL("../audits/background-removal-runtime-baseline.json", import.meta.url), "utf8"));
const require = createRequire(import.meta.url);
const axe = require("axe-core");
import { PDFDocument } from "pdf-lib";
import JSZip from "jszip";

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
const page = await context.newPage();
const pageErrors = [];
const thirdPartyRequests = [];
const thirdPartyRequestDetails = [];
const responseHashPromises = [];
page.on("pageerror", error => pageErrors.push(error.message));
page.on("request", request => {
  const requestUrl = new URL(request.url());
  if (
    ["http:", "https:"].includes(requestUrl.protocol) &&
    requestUrl.hostname !== "127.0.0.1" &&
    requestUrl.hostname !== "localhost"
  ) {
    thirdPartyRequests.push(requestUrl);
    const postData = request.postDataBuffer();
    thirdPartyRequestDetails.push({
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType(),
      requestBodyBytes: postData ? postData.length : 0,
      status: null,
      contentType: null,
      contentLengthBytes: null,
      responseBodyBytes: null,
      sha256: null,
      hashError: null,
      hashQueued: false
    });
  }
});
page.on("response", response => {
  const detail = [...thirdPartyRequestDetails].reverse().find(item => item.url === response.url() && item.status === null);
  if (!detail) return;
  const headers = response.headers();
  const contentLength = headers["content-length"];
  detail.status = response.status();
  detail.contentType = headers["content-type"] || null;
  detail.contentLengthBytes = contentLength !== undefined && Number.isFinite(Number(contentLength))
    ? Number(contentLength)
    : null;
});
page.on("requestfinished", request => {
  const detail = [...thirdPartyRequestDetails].reverse().find(item =>
    item.url === request.url() && item.status !== null && !item.hashQueued
  );
  if (!detail || detail.status !== 200) return;
  const requestUrl = new URL(request.url());
  const isObservedModule = requestUrl.hostname === "esm.sh" &&
    runtimeBaseline.observedModules.some(module =>
      module.pathPrefix && requestUrl.pathname.startsWith(module.pathPrefix)
    );
  const isModelAsset = requestUrl.hostname === runtimeBaseline.assetOrigin.host;
  if (!isObservedModule && !isModelAsset) return;
  detail.hashQueued = true;
  responseHashPromises.push(request.response().then(response => response.body()).then(body => {
    detail.responseBodyBytes = body.length;
    if (body.length === 0 && (detail.contentType || "").includes("application/wasm")) {
      detail.hashError = "Playwright exposed no response body for the streamed WebAssembly response; no digest is claimed.";
      return;
    }
    if (body.length === 0) {
      detail.hashError = "Playwright exposed an empty response body.";
      return;
    }
    detail.sha256 = createHash("sha256").update(body).digest("hex");
  }).catch(error => {
    detail.hashError = error.message;
  }));
});

try {
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  assert.equal(thirdPartyRequests.length, 0, "Initial page load must not contact third-party hosts before a tool is used");

  // Public third-party license notice: attribution and license links must be reachable without third-party requests.
  await page.goto("http://127.0.0.1:8000/licenses/", { waitUntil: "load" });
  assert.match(await page.locator("h1").innerText(), /Open-source software notices/i);
  assert.match(await page.locator("body").innerText(), /@imgly\/background-removal/);
  assert.match(await page.locator("body").innerText(), /AGPL-3\.0/);
  assert.match(await page.locator("body").innerText(), /https:\/\/esm\.sh\/@imgly\/background-removal@1\.5\.5/);
  const licenseBodyText = await page.locator("body").innerText();
  for (const packageDetail of [
    "pdf-lib — version 1.17.1",
    "JSZip — version 3.10.2",
    "MIT or GPL-3.0",
    "jsPDF — version 4.2.1",
    "MIT option for this integration"
  ]) {
    assert.ok(licenseBodyText.includes(packageDetail), "License notice must identify each pinned direct browser package and its license: " + packageDetail);
  }
  for (const licenseUrl of [
    "https://github.com/Hopding/pdf-lib/blob/v1.17.1/LICENSE.md",
    "https://github.com/Stuk/jszip/blob/v3.10.2/LICENSE.markdown",
    "https://github.com/parallax/jsPDF/blob/v4.2.1/LICENSE"
  ]) {
    assert.equal(await page.locator('a[href="' + licenseUrl + '"]').count(), 1, "Versioned upstream license link must be present: " + licenseUrl);
  }
  assert.equal(await page.locator('a[href="https://github.com/imgly/background-removal-js"]').count(), 1);
  assert.equal(await page.locator('a[href="https://www.gnu.org/licenses/agpl-3.0.html"]').count(), 1);
  await page.addScriptTag({ content: axe.source });
  const licenseAxe = await page.evaluate(async () => axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } }));
  assert.equal(licenseAxe.violations.filter(v => ["serious", "critical"].includes(v.impact)).length, 0, "License notice must have no serious or critical accessibility violations");
  assert.equal(thirdPartyRequests.length, 0, "Reading license notices must not contact third-party hosts");
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  const homepageLicenseLink = page.locator('footer .footerlinks a[href="/licenses/"]');
  assert.equal(await homepageLicenseLink.count(), 1, "Homepage legal footer should expose one crawlable license-notice link");
  assert.ok(await homepageLicenseLink.isVisible(), "Homepage license-notice link should be visible");
  await homepageLicenseLink.click();
  await page.waitForURL("**/licenses/");
  assert.match(await page.locator("h1").innerText(), /Open-source software notices/i);
  assert.equal(thirdPartyRequests.length, 0, "Following the homepage license link must remain first-party only");
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });

  // Crawlable homepage directory and reciprocal CSV tool-page navigation.
  const csvViewerDirectoryLink = page.locator('a[href="/tools/csv-viewer/"]');
  assert.equal(await csvViewerDirectoryLink.count(), 1, "Homepage should expose one crawlable CSV Viewer link");
  await csvViewerDirectoryLink.click();
  await page.waitForURL("**/tools/csv-viewer/");
  assert.match(await page.locator("h1").innerText(), /CSV Viewer/i);
  const csvConverterGuideLink = page.locator('a[href="/tools/csv-json-converter/"]');
  assert.equal(await csvConverterGuideLink.count(), 1, "CSV Viewer should link to the dedicated CSV/JSON guide");
  await csvConverterGuideLink.click();
  await page.waitForURL("**/tools/csv-json-converter/");
  assert.match(await page.locator("h1").innerText(), /CSV to JSON Converter/i);

  const csvJsonFormattingGuideLink = page.locator('a[href="/guides/format-json-online/"]');
  assert.equal(await csvJsonFormattingGuideLink.count(), 1, "CSV/JSON converter should link to the JSON formatting guide");
  await csvJsonFormattingGuideLink.click();
  await page.waitForURL("**/guides/format-json-online/");
  assert.match(await page.locator("h1").innerText(), /Format a JSON File and Check JSON Syntax Online/i);

  await page.goto("http://127.0.0.1:8000/tools/json-to-typescript/", { waitUntil: "load" });
  const jsonTypeGuideLink = page.locator('a[href="/guides/format-json-online/"]');
  assert.equal(await jsonTypeGuideLink.count(), 1, "JSON to TypeScript should link to the JSON formatting guide");
  await jsonTypeGuideLink.click();
  await page.waitForURL("**/guides/format-json-online/");
  assert.match(await page.locator("h1").innerText(), /Format a JSON File and Check JSON Syntax Online/i);

  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });
  async function auditAccessibility(label) {
    const result = await page.evaluate(async () => axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }
    }));
    const serious = result.violations.filter(v => ["serious", "critical"].includes(v.impact));
    console.log("Accessibility " + label + ": " + result.passes.length + " rules passed, " + result.violations.length + " violation types; " + serious.length + " serious/critical.");
    if (serious.length) console.error(JSON.stringify(serious.map(v => ({ id: v.id, impact: v.impact, description: v.description, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })), null, 2));
    assert.equal(serious.length, 0, "Serious/critical accessibility violations on " + label);
  }
  await page.locator('[data-tool]').first().waitFor();
  await auditAccessibility("homepage");

  // Image-size guide: answer the observed no-quality-loss query accurately and expose both relevant workflows.
  await page.goto("http://127.0.0.1:8000/guides/reduce-image-size/", { waitUntil: "load" });
  assert.match(await page.title(), /Reduce Image File Size Without Losing Quality/i);
  assert.match(await page.locator("h1").innerText(), /Reduce Image File Size Without Losing Quality/i);
  const imageQuickAnswer = page.locator("#quick-answer");
  const imageQuickAnswerText = await imageQuickAnswer.innerText();
  assert.match(imageQuickAnswerText, /Lossless optimization can reduce file size without changing decoded pixels/i);
  assert.match(imageQuickAnswerText, /Resizing: changes pixel dimensions/i);
  assert.match(imageQuickAnswerText, /Lossy compression: discards image information/i);
  assert.equal(await imageQuickAnswer.locator('a[href="/tools/image-compressor/"]').count(), 1);
  assert.equal(await imageQuickAnswer.locator('a[href="/tools/image-resizer/"]').count(), 1);
  assert.match(imageQuickAnswerText, /starts at 75% quality and ranges from 20% to 95%/i);
  assert.match(imageQuickAnswerText, /browser's JPEG encoder/i);
  await page.addScriptTag({ content: axe.source });
  await auditAccessibility("image-size guide");
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });

  const toolCount = await page.locator('[data-tool]').count();
  assert.ok(toolCount >= 38, `Expected at least 38 tools, found ${toolCount}`);

  // Offscreen tool cards should skip initial rendering work but remain in the DOM and render on demand.
  const lastToolCard = page.locator('[data-tool]').last();
  const cardRendering = await lastToolCard.evaluate(card => ({
    contentVisibility: getComputedStyle(card).contentVisibility,
    intrinsicSize: getComputedStyle(card).containIntrinsicSize
  }));
  assert.equal(cardRendering.contentVisibility, "auto", "Tool cards should defer offscreen rendering");
  assert.match(cardRendering.intrinsicSize, /190px/, "Deferred cards should reserve their existing minimum height");
  await lastToolCard.scrollIntoViewIfNeeded();
  assert.ok(await lastToolCard.isVisible(), "A deferred tool card must remain visible when brought into view");
  const renderedCard = await lastToolCard.evaluate(card => ({
    height: card.getBoundingClientRect().height,
    text: card.textContent || ""
  }));
  assert.ok(renderedCard.height >= 190, "A deferred tool card must recover its reserved layout size when brought into view");
  assert.match(renderedCard.text, /Open tool/i, "Deferred card content must remain in the DOM");

  // Search and discoverability: the semantic form must match the SearchAction q URL.
  assert.equal(await page.locator("#toolSearch").getAttribute("role"), "search");
  assert.equal(await page.locator("#toolSearch").getAttribute("method"), "get");
  assert.equal(await page.locator("#search").getAttribute("type"), "search");
  assert.equal(await page.locator("#search").getAttribute("name"), "q");
  await page.goto("http://127.0.0.1:8000/?q=CSV%20Viewer", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });
  assert.equal(await page.locator("#search").inputValue(), "CSV Viewer", "SearchAction deep links must prefill the search input");
  assert.equal(await page.locator('[data-tool]').count(), 1, "SearchAction deep links must render filtered results");
  assert.equal(await page.locator('[data-tool="csv-viewer"]').count(), 1);
  await page.locator("#search").fill("JSON syntax");
  assert.equal(await page.locator('[data-tool="json"]').count(), 1, "Searching for JSON syntax must discover the JSON Formatter");
  await page.locator("#search").fill("JSON Schema");
  assert.equal(await page.locator('[data-tool="json"]').count(), 0, "The syntax-only formatter must not be presented as a JSON Schema validator");
  await page.locator("#search").fill("JSON Formatter");
  assert.equal(await page.locator('[data-tool]').count(), 1, "Typing must filter matching tools immediately");
  await page.locator("#searchBtn").click();
  assert.equal(new URL(page.url()).searchParams.get("q"), "JSON Formatter", "Search button submission must create a shareable q URL");
  assert.equal(await page.locator('[data-tool]').count(), 1);
  await page.locator("#search").fill("CSV Viewer");
  await page.locator("#search").press("Enter");
  assert.equal(new URL(page.url()).searchParams.get("q"), "CSV Viewer", "Enter must submit the semantic search form");
  await page.locator("#search").fill("");
  await page.locator("#searchBtn").click();
  assert.equal(new URL(page.url()).searchParams.has("q"), false, "Submitting an empty search must remove the stale q parameter");

  // Word Counter: count visible grapheme clusters, whitespace and singular labels.
  await page.locator('[data-tool="word-counter"]').click();
  await auditAccessibility("Word Counter tool");
  await page.locator("#text").fill("A 😀\nCafe!");
  const wordCounterResult = await page.locator("#result").innerText();
  assert.match(wordCounterResult, /3 words/);
  assert.match(wordCounterResult, /7 characters \(excluding whitespace\)/);
  assert.match(wordCounterResult, /9 characters including spaces and line breaks/);
  assert.match(wordCounterResult, /1 sentence/);

  await page.locator("#text").fill("e\u0301");
  const combiningMarkResult = await page.locator("#result").innerText();
  assert.match(combiningMarkResult, /1 word/);
  assert.match(combiningMarkResult, /1 character \(excluding whitespace\)/);
  assert.match(combiningMarkResult, /1 character including spaces and line breaks/);

  await page.locator("#text").fill("👩‍👩‍👧‍👦");
  const joinedEmojiResult = await page.locator("#result").innerText();
  assert.match(joinedEmojiResult, /1 character \(excluding whitespace\)/);
  assert.match(joinedEmojiResult, /1 character including spaces and line breaks/);

  await page.locator("#text").fill("🇸🇩");
  const flagResult = await page.locator("#result").innerText();
  assert.match(flagResult, /1 character \(excluding whitespace\)/);
  assert.match(flagResult, /1 character including spaces and line breaks/);

  await page.locator("#text").fill("Hello");
  assert.match(await page.locator("#result").innerText(), /1 word · 5 characters/);
  await page.locator("#text").fill("");
  assert.match(await page.locator("#result").innerText(), /0 words · 0 characters \(excluding whitespace\) · 0 characters including spaces and line breaks · 0 sentences/);
  await page.locator("#closeWork").click();

  // Line tools: results must contain real line breaks, not literal backslash sequences.
  await page.locator('[data-tool="duplicate-lines"]').click();
  await page.locator("#text").fill("beta\nalpha\nbeta");
  await page.locator("#run").click();
  const deduplicatedText = await page.locator("#output").inputValue();
  assert.equal(deduplicatedText, "beta\nalpha");
  assert.doesNotMatch(deduplicatedText, /\\n/, "Duplicate-line output must not contain literal backslash-n text");
  assert.match(await page.locator("#lineSummary").innerText(), /Kept 2 of 3 lines/);
  await page.locator("#closeWork").click();

  await page.locator('[data-tool="sort-lines"]').click();
  await page.locator("#text").fill("zebra\nApple\nbanana");
  await page.locator("#run").click();
  assert.equal(await page.locator("#output").inputValue(), "Apple\nbanana\nzebra");
  await page.locator("#sortOrder").selectOption("reverse");
  await page.locator("#run").click();
  assert.equal(await page.locator("#output").inputValue(), "banana\nApple\nzebra");
  await page.locator("#closeWork").click();

  // JSON formatter: valid and invalid input.
  await page.locator('[data-tool="json"]').click();
  await auditAccessibility("JSON formatter tool");
  await page.locator("#text").fill('{"hello":"world","count":2}');
  const unformattedJson = await page.locator("#text").inputValue();
  await page.locator('[data-json="validate"]').click();
  assert.equal(await page.locator("#text").inputValue(), unformattedJson, "Validate must not rewrite the source JSON");
  assert.match(await page.locator("#result").innerText(), /Valid JSON/);
  await page.locator('[data-json="pretty"]').click();
  assert.match(await page.locator("#text").inputValue(), /\n  "hello": "world"/);
  assert.match(await page.locator("#result").innerText(), /Valid JSON/);
  await page.locator("#text").fill('{"broken":');
  await page.locator('[data-json="validate"]').click();
  assert.match(await page.locator("#result").innerText(), /Invalid JSON/);

  // Homepage JSON file import: local read, exact 5 MiB boundary and oversize rejection.
  const jsonFileBytes = 5 * 1024 * 1024;
  const maxSizeJsonBuffer = Buffer.from('{"data":"' + "a".repeat(jsonFileBytes - 11) + '"}');
  assert.equal(maxSizeJsonBuffer.length, jsonFileBytes);
  const thirdPartyBeforeJsonImport = thirdPartyRequests.length;
  await page.locator("#jsonFile").setInputFiles({ name: "sample.json", mimeType: "application/json", buffer: Buffer.from('{"fromFile":true,"count":2}') });
  await page.waitForFunction(() => document.querySelector("#text")?.value.includes('"fromFile"'));
  assert.match(await page.locator("#result").innerText(), /Loaded sample\.json/);
  assert.equal(thirdPartyRequests.length, thirdPartyBeforeJsonImport, "Local JSON file selection must not create third-party requests");
  await page.locator('[data-json="pretty"]').click();
  assert.match(await page.locator("#text").inputValue(), /\n  "fromFile": true/);
  const utf8BomJson = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from('{"bom":true}')]);
  await page.locator("#jsonFile").setInputFiles({ name: "bom.json", mimeType: "application/json", buffer: utf8BomJson });
  await page.waitForFunction(() => document.querySelector("#text")?.value.includes('"bom"'));
  assert.equal(await page.locator("#text").inputValue(), '{"bom":true}', "UTF-8 BOM should be removed during decoding");
  const invalidUtf8Json = Buffer.from([0x7b, 0x22, 0x76, 0x22, 0x3a, 0x22, 0xff, 0x22, 0x7d]);
  const thirdPartyBeforeInvalidUtf8 = thirdPartyRequests.length;
  await page.locator("#jsonFile").setInputFiles({ name: "invalid-utf8.json", mimeType: "application/json", buffer: invalidUtf8Json });
  await page.waitForFunction(() => /Could not read this file.*UTF-8/.test(document.querySelector("#result")?.textContent || ""));
  assert.match(await page.locator("#result").innerText(), /Could not read this file.*UTF-8/);
  assert.equal(await page.locator("#text").inputValue(), "", "Malformed UTF-8 must not be imported with replacement characters");
  assert.equal(thirdPartyRequests.length, thirdPartyBeforeInvalidUtf8, "Invalid local JSON must not create third-party requests");
  await page.locator("#jsonFile").setInputFiles({ name: "max-size.json", mimeType: "application/json", buffer: maxSizeJsonBuffer });
  await page.waitForFunction(() => document.querySelector("#text")?.value.length === 5 * 1024 * 1024);
  assert.match(await page.locator("#result").innerText(), /Loaded max-size\.json/);
  const oversizedJsonBuffer = Buffer.alloc(jsonFileBytes + 1, 0x20);
  await page.locator("#jsonFile").setInputFiles({ name: "too-large.json", mimeType: "application/json", buffer: oversizedJsonBuffer });
  assert.match(await page.locator("#result").innerText(), /5 MiB/);
  assert.equal(await page.locator("#text").inputValue(), "", "Oversize JSON selection must clear previous input instead of leaving stale data");

  // The canonical standalone formatter must offer the same local-file behavior.
  await page.locator("#closeWork").click();
  await page.goto("http://127.0.0.1:8000/tools/json-formatter/", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });
  await auditAccessibility("standalone JSON formatter");
  const thirdPartyBeforeStandaloneJsonImport = thirdPartyRequests.length;
  await page.locator("#jsonFile").setInputFiles({ name: "standalone.json", mimeType: "application/json", buffer: Buffer.from('{"standalone":true}') });
  await page.waitForFunction(() => document.querySelector("#jsonInput")?.value.includes('"standalone"'));
  assert.match(await page.locator("#status").innerText(), /Loaded standalone\.json/);
  assert.equal(thirdPartyRequests.length, thirdPartyBeforeStandaloneJsonImport, "Standalone local JSON import must not contact third-party hosts");
  await page.locator("#formatBtn").click();
  assert.match(await page.locator("#jsonOutput").inputValue(), /\n  "standalone": true/);
  await page.locator("#jsonFile").setInputFiles({ name: "bom.json", mimeType: "application/json", buffer: utf8BomJson });
  await page.waitForFunction(() => document.querySelector("#jsonInput")?.value.includes('"bom"'));
  assert.equal(await page.locator("#jsonInput").inputValue(), '{"bom":true}', "Standalone formatter should strip a UTF-8 BOM");
  const thirdPartyBeforeStandaloneInvalidUtf8 = thirdPartyRequests.length;
  await page.locator("#jsonFile").setInputFiles({ name: "invalid-utf8.json", mimeType: "application/json", buffer: invalidUtf8Json });
  await page.waitForFunction(() => /Could not read this file.*UTF-8/.test(document.querySelector("#status")?.textContent || ""));
  assert.match(await page.locator("#status").innerText(), /Could not read this file.*UTF-8/);
  assert.equal(await page.locator("#jsonInput").inputValue(), "", "Standalone formatter must reject malformed UTF-8");
  assert.equal(thirdPartyRequests.length, thirdPartyBeforeStandaloneInvalidUtf8, "Invalid local JSON must not contact third-party hosts");
  await page.locator("#jsonFile").setInputFiles({ name: "too-large.json", mimeType: "application/json", buffer: oversizedJsonBuffer });
  assert.match(await page.locator("#status").innerText(), /5 MiB/);
  assert.equal(await page.locator("#jsonInput").inputValue(), "", "Oversize standalone JSON selection must clear previous input");

  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  await page.addScriptTag({ content: axe.source });

  // CSV converter: BOM, normal conversion, duplicate-header guard and CSV quoting.
  await page.locator('[data-tool="csv-json"]').click();
  await page.locator("#text").fill('\uFEFFname,age\nAda,36');
  await page.locator('[data-csv="tojson"]').click();
  const converted = JSON.parse(await page.locator("#text").inputValue());
  assert.equal(converted[0].name, "Ada");
  assert.equal(converted[0].age, "36");
  await page.locator("#text").fill('name,name\nAda,Grace');
  await page.locator('[data-csv="tojson"]').click();
  assert.match(await page.locator("#result").innerText(), /header names must be unique/i);
  await page.locator("#text").fill(JSON.stringify([{ name: "Ada, Lovelace", note: 'said "hello"' }]));
  await page.locator('[data-csv="tocsv"]').click();
  assert.match(await page.locator("#text").inputValue(), /"Ada, Lovelace"/);
  assert.match(await page.locator("#text").inputValue(), /"said ""hello"""/);
  await page.locator("#text").fill(JSON.stringify([{ formula: "=1+1", expression: "-1+1", negative: -5, plusNumeric: "+5", fullWidth: "＝1+1", total: "@SUM(A1:A2)", tabbed: "\tplain", spacedFormula: "  =2+2", newlineFormula: "\n=3+3", ideographicSpaceFormula: "　＝4+4", spacedNegative: " -5" }]));
  await page.locator('[data-csv="tocsv"]').click();
  const safeConvertedCsv = await page.locator("#text").inputValue();
  assert.ok(safeConvertedCsv.includes("'=1+1"), "JSON-to-CSV must neutralize equals-prefixed formulas");
  assert.ok(safeConvertedCsv.includes("'-1+1"), "JSON-to-CSV must neutralize expression-like negative values");
  assert.ok(safeConvertedCsv.includes("'@SUM(A1:A2)"), "JSON-to-CSV must neutralize at-sign formulas");
  assert.ok(safeConvertedCsv.includes(",-5,"), "Plain negative numeric values should remain numeric");
  assert.ok(safeConvertedCsv.includes("'\tplain"), "JSON-to-CSV must neutralize cells beginning with a tab");
  assert.ok(safeConvertedCsv.includes("'+5"), "JSON-to-CSV must neutralize plus-prefixed numeric-looking text");
  assert.ok(safeConvertedCsv.includes("'＝1+1"), "JSON-to-CSV must neutralize full-width formula markers");
  assert.ok(safeConvertedCsv.includes("'  =2+2"), "JSON-to-CSV must neutralize formulas after leading spaces");
  assert.ok(safeConvertedCsv.includes("'\n=3+3"), "JSON-to-CSV must neutralize formulas after a leading line break");
  assert.ok(safeConvertedCsv.includes("'　＝4+4"), "JSON-to-CSV must neutralize full-width formulas after Unicode whitespace");
  assert.ok(safeConvertedCsv.includes(" -5"), "Whitespace-prefixed negative numeric values should remain unchanged");
  assert.ok(!safeConvertedCsv.includes("' -5"), "Safe negative numeric values should not be unnecessarily prefixed");


  // QR generator: verify the disclosed third-party request occurs only after an explicit action and encodes the input safely.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="qr"]').click();
  const qrPrivacyNotice = page.locator("#qrPrivacyNotice");
  assert.ok(await qrPrivacyNotice.isVisible(), "QR generator must show its third-party data disclosure before use");
  const qrNoticeText = await qrPrivacyNotice.innerText();
  assert.match(qrNoticeText, /sent to QRServer/i);
  assert.match(qrNoticeText, /do not enter passwords.*confidential information/i);
  assert.equal(await page.locator("#text").getAttribute("aria-describedby"), "qrPrivacyNotice");
  await auditAccessibility("QR Generator tool");
  assert.equal(thirdPartyRequests.filter(url => url.hostname === "api.qrserver.com").length, 0, "QR input must not be sent before the user requests generation");
  await page.route("https://api.qrserver.com/**", route => route.fulfill({
    status: 200,
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#fff"/></svg>'
  }));
  const qrInput = "https://example.com/?a=1&b=two words";
  await page.locator("#text").fill(qrInput);
  const [qrRequest] = await Promise.all([
    page.waitForRequest(request => request.url().startsWith("https://api.qrserver.com/v1/create-qr-code/")),
    page.locator("#run").click()
  ]);
  assert.equal(new URL(qrRequest.url()).searchParams.get("data"), qrInput, "QR input must be URL-encoded into the disclosed data parameter");
  assert.equal(thirdPartyRequests.filter(url => url.hostname === "api.qrserver.com").length, 1, "QR service should be called once after generation is requested");
  // Repeated generation must replace the previous preview rather than accumulate images.
  await page.locator("#run").click();
  await page.waitForFunction(() => document.querySelectorAll(".preview").length === 1);
  assert.equal(await page.locator(".preview").count(), 1, "QR regeneration must leave exactly one preview");
  await page.locator("#text").fill("updated QR content");
  assert.equal(await page.locator(".preview").count(), 0, "Changing QR input must clear the previous preview");

  await page.unroute("https://api.qrserver.com/**");
  // A failed provider request must produce an accessible error state and remove the broken preview.
  await page.route("https://api.qrserver.com/**", route => route.fulfill({
    status: 503,
    contentType: "text/plain",
    body: "temporarily unavailable"
  }));
  await page.locator("#run").click();
  await page.waitForFunction(() => document.querySelector("#result")?.textContent.includes("could not be generated"));
  assert.equal(await page.locator(".preview").count(), 0, "Failed QR requests must not leave a broken preview");
  assert.equal(await page.locator("#result").getAttribute("role"), "status");
  assert.equal(await page.locator("#result").getAttribute("aria-live"), "polite");
  await page.unroute("https://api.qrserver.com/**");

  // JSON to TypeScript: reserved interface name and mixed array union.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="json-ts"]').click();
  await page.locator("#interfaceName").fill("class");
  await page.locator("#text").fill('{"field1":["alpha",2]}');
  await page.locator("#run").click();
  const ts = await page.locator("#result").innerText();
  assert.match(ts, /interface classModel/);
  assert.match(ts, /field1: \(string \| number\)\[\]/);
  assert.doesNotMatch(ts, /"field1"/);

  // Password generator: reject out-of-range 32-bit samples instead of introducing modulo bias.
  const rejectionSampling = await page.evaluate(() => {
    const sequence = [0xffffffff, 4294967294, 0, 1];
    let batches = 0;
    const output = secureRandomString(3, "abc", values => {
      batches += 1;
      for (let i = 0; i < values.length; i += 1) values[i] = sequence.shift();
    });
    return { output, batches, remaining: sequence.length };
  });
  assert.deepEqual(rejectionSampling, { output: "cab", batches: 2, remaining: 0 });

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="password"]').click();
  await auditAccessibility("Password Generator tool");
  await page.locator("#plen").fill("32");
  await page.locator("#run").click();
  const generatedPassword = await page.locator("#text").inputValue();
  assert.equal(generatedPassword.length, 32, "Password generator must respect the selected length");
  assert.ok([...generatedPassword].every(character => "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*()-_=+[]{}?".includes(character)), "Password must use only the selected character set");

  // If browser cryptographic randomness fails, the UI must clear any previous output and fail closed.
  await page.locator("#text").evaluate(element => { element.value = "stale-password-must-not-remain"; });
  const passwordFailureState = await page.evaluate(() => {
    window.secureRandomString = () => { throw new Error("simulated secure randomness failure"); };
    document.querySelector("#run").click();
    return {
      value: document.querySelector("#text").value,
      message: document.querySelector("#result").textContent
    };
  });
  assert.equal(passwordFailureState.value, "", "A failed secure generation must not leave stale password text visible");
  assert.match(passwordFailureState.message, /Could not generate a secure password in this browser/i);

  // CSV viewer: parse, filter and export with spreadsheet formula-injection safeguards.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="csv-viewer"]').click();
  assert.match(await page.locator("#csvSafetyNote").innerText(), /leading apostrophe/i);
  await auditAccessibility("CSV Viewer tool");
  const csvFixture = [
    "sku,product,category,stock,formula,spacedFormula,tabbed,plusNumeric,fullWidth,lineBreak",
    "A-104,Desk lamp,Home,-5,-5,plain,plain,-5,plain,plain",
    "B-208,USB cable,Electronics,0,=1+1,  =2+2,\tplain,+5,＝1+1,\"\n=3+3\"",
    "C-311,Notebook,Stationery,42,@SUM(A1:A2),safe,safe,3,safe,safe",
    "D-412,Marker,Electronics,12,-1+1,safe,safe,4,safe,safe",
    "E-513,Folder,Office,4,+SUM(A1:A2),safe,safe,5,safe,safe"
  ].join("\n");
  await page.locator("#text").fill(csvFixture);
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 5);
  await page.locator("#csvFilter").fill("Electronics");
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2);
  await page.locator("#csvFilter").fill("");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#csvExport").click()
  ]);
  const stream = await download.createReadStream();
  let csvOutput = "";
  for await (const chunk of stream) csvOutput += chunk.toString("utf8");
  assert.equal(csvOutput.charCodeAt(0), 0xFEFF, "CSV Viewer export should start with a UTF-8 BOM");
  assert.ok(csvOutput.includes("\r\n"), "CSV Viewer export should use real CRLF record separators");
  assert.ok(!csvOutput.includes("\\r\\n"), "CSV Viewer export must not contain literal backslash-r/backslash-n text");
  assert.match(csvOutput, /USB cable/);
  assert.match(csvOutput, /Desk lamp/);
  assert.ok(csvOutput.includes("'=1+1"), "CSV Viewer must neutralize equals-prefixed formulas");
  assert.ok(csvOutput.includes("'  =2+2"), "CSV Viewer must neutralize formulas after leading whitespace");
  assert.ok(csvOutput.includes("'@SUM(A1:A2)"), "CSV Viewer must neutralize at-sign formulas");
  assert.ok(csvOutput.includes("'-1+1"), "CSV Viewer must neutralize expression-like negative values");
  assert.ok(csvOutput.includes("'+SUM(A1:A2)"), "CSV Viewer must neutralize plus-prefixed formulas");
  assert.ok(csvOutput.includes("Home,-5,-5,plain"), "Plain negative numeric values should remain unchanged");
  assert.ok(csvOutput.includes("'\tplain"), "CSV Viewer must neutralize cells beginning with a tab");
  assert.ok(csvOutput.includes("'+5"), "CSV Viewer must neutralize plus-prefixed numeric-looking text");
  assert.ok(csvOutput.includes("'＝1+1"), "CSV Viewer must neutralize full-width formula markers");
  assert.ok(csvOutput.includes("'\n=3+3"), "CSV Viewer must neutralize formula values after a leading line feed");
  assert.ok(!csvOutput.includes(",=1+1,"), "Unescaped formula-leading values must not remain in exported CSV");

  // CSV Viewer: support common semicolon and tab delimiters without splitting quoted values.
  assert.equal(await page.locator("#csvDelimiter").inputValue(), ",", "Comma should remain the default field separator");
  const semicolonFixture = 'name;note;city\nAda;"Works; with data";London\nLinus;Engineering;Helsinki';
  await page.locator("#text").fill(semicolonFixture);
  await page.locator("#csvDelimiter").selectOption(";");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "Semicolon-delimited rows should parse");
  assert.equal(await page.locator("#csvTable tbody tr").first().locator("td").nth(1).innerText(), "Works; with data", "A semicolon inside a quoted field must remain cell content");

  const tabFixture = 'name\tnote\tcity\nAda\t"Works\twith data"\tLondon\nLinus\tEngineering\tHelsinki';
  await page.locator("#text").fill(tabFixture);
  await page.locator("#csvDelimiter").selectOption("\t");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "Tab-delimited rows should parse");
  assert.equal(await page.locator("#csvTable tbody tr").first().locator("td").nth(1).textContent(), "Works\twith data", "A tab inside a quoted field must remain cell content");

  // CSV Viewer: support legacy CR-only record separators without splitting quoted cell content.
  const crOnlyFixture = 'name,note,city\rAda,"line one\rline two",London\rLinus,Engineering,Helsinki';
  await page.locator("#text").fill(crOnlyFixture);
  await page.locator("#csvDelimiter").selectOption(",");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "CR-only record separators should create separate CSV rows");
  const crOnlyNote = await page.locator("#csvTable tbody tr").first().locator("td").nth(1).textContent();
  assert.ok(crOnlyNote.includes("line one") && crOnlyNote.includes("line two"), "CR-only line breaks inside quoted fields must remain cell content");
  assert.equal(await page.locator("#csvTable tbody tr").nth(1).locator("td").nth(2).textContent(), "Helsinki");

  // Reject malformed quote placement instead of silently dropping or merging cell text.
  const emptyQuotedFixture = 'name,note\nAda,""\nLinus,Engineering';
  await page.locator("#text").fill(emptyQuotedFixture);
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "An empty quoted field must remain a valid cell");
  assert.equal(await page.locator("#csvTable tbody tr").first().locator("td").nth(1).textContent(), "", "An empty quoted cell must not disappear");

  const emptyQuotedHeaderFixture = '""\nvalue';
  await page.locator("#text").fill(emptyQuotedHeaderFixture);
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 1, "A leading empty quoted header must remain a field");
  assert.match(await page.locator("#csvTable thead button").first().innerText(), /^Column 1/, "An empty quoted header should receive the documented fallback label");
  assert.equal(await page.locator("#csvTable tbody tr").first().locator("td").first().textContent(), "value");

  const malformedCsvFixtures = [
    { csv: 'name,note\nAda,"quoted"suffix', error: "Unexpected character after a closing quote" },
    { csv: 'name,note\nAda,un"escaped', error: "Unexpected quote in an unquoted CSV field" }
  ];
  for (const fixture of malformedCsvFixtures) {
    await page.locator("#text").fill(fixture.csv);
    await page.locator("#run").click();
    assert.ok((await page.locator("#result").innerText()).includes(fixture.error), "Malformed CSV must show a clear quote-syntax error");
    assert.equal(await page.locator("#csvTools").evaluate(el => el.classList.contains("hidden")), true, "Malformed CSV must not leave a stale preview visible");
  }
  await page.locator("#csvDelimiter").selectOption(",");

  // CSV Viewer: load a local file in-browser, then enforce the documented size limit.
  const csvFileText = "sku,product\nA-104,Desk lamp\nB-208,USB cable";
  const externalRequestsBeforeCsvFile = thirdPartyRequests.length;
  const csvFileInput = page.locator("#csvFile");
  assert.equal(await csvFileInput.count(), 1, "CSV Viewer should expose a labeled local file picker");
  await csvFileInput.setInputFiles({ name: "inventory.csv", mimeType: "text/csv", buffer: Buffer.from(csvFileText) });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("Loaded inventory.csv"));
  assert.match(await page.locator("#csvFileStatus").innerText(), /Loaded inventory\.csv.*locally/i);
  assert.equal(await page.locator("#text").inputValue(), csvFileText);
  assert.equal(thirdPartyRequests.length, externalRequestsBeforeCsvFile, "Reading a local CSV file must not create third-party requests");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "A selected local CSV should preview its data rows");

  // Excel and other exporters commonly produce UTF-16 CSV files with a byte-order mark.
  const utf16leFile = Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(csvFileText, "utf16le")]);
  await csvFileInput.setInputFiles({ name: "inventory-utf16le.csv", mimeType: "text/csv", buffer: utf16leFile });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("Loaded inventory-utf16le.csv"));
  assert.equal(await page.locator("#text").inputValue(), csvFileText, "UTF-16LE BOM CSV files should decode without null characters");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "UTF-16LE CSV rows should parse correctly");

  const utf16beBody = Buffer.from(csvFileText, "utf16le");
  for (let i = 0; i < utf16beBody.length; i += 2) {
    const firstByte = utf16beBody[i];
    utf16beBody[i] = utf16beBody[i + 1];
    utf16beBody[i + 1] = firstByte;
  }
  const utf16beFile = Buffer.concat([Buffer.from([0xfe, 0xff]), utf16beBody]);
  await csvFileInput.setInputFiles({ name: "inventory-utf16be.csv", mimeType: "text/csv", buffer: utf16beFile });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("Loaded inventory-utf16be.csv"));
  assert.equal(await page.locator("#text").inputValue(), csvFileText, "UTF-16BE BOM CSV files should decode without null characters");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 2, "UTF-16BE CSV rows should parse correctly");
  assert.equal(thirdPartyRequests.length, externalRequestsBeforeCsvFile, "UTF-16 CSV decoding must remain local");

  const utf8BomCsv = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from(csvFileText, "utf8")]);
  await csvFileInput.setInputFiles({ name: "inventory-utf8-bom.csv", mimeType: "text/csv", buffer: utf8BomCsv });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("Loaded inventory-utf8-bom.csv"));
  assert.equal(await page.locator("#text").inputValue(), csvFileText, "UTF-8 BOM CSV files should decode without retaining the BOM");

  const previousCsvText = await page.locator("#text").inputValue();
  const invalidUtf8Csv = Buffer.from([0x73, 0x6b, 0x75, 0x2c, 0x70, 0x72, 0x6f, 0x64, 0x75, 0x63, 0x74, 0x0a, 0x41, 0x2d, 0x31, 0x30, 0x34, 0x2c, 0xff]);
  await csvFileInput.setInputFiles({ name: "invalid-utf8.csv", mimeType: "text/csv", buffer: invalidUtf8Csv });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("invalid text encoding"));
  assert.equal(await page.locator("#text").inputValue(), previousCsvText, "Malformed UTF-8 must not silently replace the current CSV text");
  assert.equal(await page.locator("#csvTools").isVisible(), false, "Malformed UTF-8 must hide stale previews");
  assert.equal(await page.locator("#csvExport").isDisabled(), true, "Malformed UTF-8 must disable stale exports");

  const invalidUtf16Le = Buffer.from([0xff, 0xfe, 0x00, 0xd8]);
  await csvFileInput.setInputFiles({ name: "invalid-utf16le.csv", mimeType: "text/csv", buffer: invalidUtf16Le });
  await page.waitForFunction(() => document.querySelector("#csvFileStatus")?.textContent?.includes("invalid text encoding"));
  assert.equal(await page.locator("#text").inputValue(), previousCsvText, "Malformed UTF-16 must not silently replace the current CSV text");
  assert.equal(thirdPartyRequests.length, externalRequestsBeforeCsvFile, "Strict CSV decoding must remain local");
  await csvFileInput.setInputFiles({ name: "too-large.csv", mimeType: "text/csv", buffer: Buffer.alloc(5 * 1024 * 1024 + 1, 0x61) });
  assert.match(await page.locator("#csvFileStatus").innerText(), /exceeds the 5 MiB limit/i);
  assert.equal(await page.locator("#csvTools").isVisible(), false, "An oversized selection must hide any stale preview");
  assert.equal(await page.locator("#csvExport").isDisabled(), true, "An oversized selection must disable stale exports");
  assert.equal(await page.locator("#text").inputValue(), previousCsvText, "Rejecting an oversized file must not replace the current CSV text");

  // Browser-native image compression and resizing.
  const pngDataUrl = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 16;
    canvas.height = 8;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#336699";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/png");
  });
  const pngBuffer = Buffer.from(pngDataUrl.split(",")[1], "base64");

  // Track preview object URLs to ensure replacing files and closing a tool releases them.
  await page.evaluate(() => {
    const createObjectURL = URL.createObjectURL.bind(URL);
    const revokeObjectURL = URL.revokeObjectURL.bind(URL);
    window.__buytoolsObjectUrlAudit = { created: [], revoked: [] };
    URL.createObjectURL = blob => {
      const url = createObjectURL(blob);
      window.__buytoolsObjectUrlAudit.created.push(url);
      return url;
    };
    URL.revokeObjectURL = url => {
      window.__buytoolsObjectUrlAudit.revoked.push(url);
      return revokeObjectURL(url);
    };
  });
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="image-compress"]').click();
  const qualityControl = page.locator("#quality");
  assert.equal(await qualityControl.getAttribute("min"), ".2", "Image compressor quality minimum must match the guide");
  assert.equal(await qualityControl.getAttribute("max"), ".95", "Image compressor quality maximum must match the guide");
  assert.equal(await qualityControl.getAttribute("step"), ".05", "Image compressor quality step must remain explicit");
  assert.equal(await qualityControl.inputValue(), "0.75", "Image compressor must retain its documented 75% default");
  assert.equal(await page.locator("#qval").innerText(), "75%", "Visible quality value must match the slider default");
  const filePicker = page.locator("#fileInput");
  await filePicker.focus();
  const filePickerA11y = await filePicker.evaluate(input => ({
    visibleToKeyboard: getComputedStyle(input).display !== "none" && input.tabIndex >= 0,
    hasAssociatedLabel: input.labels?.length === 1 && /Choose file/i.test(input.labels[0].textContent || ""),
    focusIndicator: getComputedStyle(input.parentElement).outlineStyle === "solid"
  }));
  assert.deepEqual(filePickerA11y, {
    visibleToKeyboard: true,
    hasAssociatedLabel: true,
    focusIndicator: true
  }, "Image file picker must remain keyboard reachable, labeled, and visibly focused");
  await filePicker.setInputFiles({ name: "preview-first.png", mimeType: "image/png", buffer: pngBuffer });
  await page.waitForFunction(() => document.querySelector("#preview")?.naturalWidth === 16);
  const firstPreviewUrl = await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.at(-1));
  await page.locator("#fileInput").setInputFiles({ name: "preview-second.png", mimeType: "image/png", buffer: pngBuffer });
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), firstPreviewUrl);
  const secondPreviewUrl = await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.at(-1));
  await page.locator("#closeWork").click();
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), secondPreviewUrl);
  assert.deepEqual(
    await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.slice(0, 2).every(url => window.__buytoolsObjectUrlAudit.revoked.includes(url))),
    true,
    "Replacing a selected image and closing the workspace must revoke both preview object URLs"
  );

  await page.locator('[data-tool="image-compress"]').click();
  await page.locator("#fileInput").setInputFiles({ name: "sample.png", mimeType: "image/png", buffer: pngBuffer });
  await page.locator("#run").click();
  await page.locator("#result a").waitFor();
  const compressedResultUrl = await page.locator("#result a").evaluate(anchor => anchor.href);
  const [compressedDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#result a").click()
  ]);
  assert.match(compressedDownload.suggestedFilename(), /\.jpg$/i);
  const compressedStream = await compressedDownload.createReadStream();
  let compressedBytes = 0;
  for await (const chunk of compressedStream) compressedBytes += chunk.length;
  assert.ok(compressedBytes > 0, "Image compressor produced an empty file");

  // A canvas allocation failure must still close the decoded ImageBitmap.
  await page.evaluate(() => {
    window.__buytoolsBitmapCloseCount = 0;
    const originalCreateImageBitmap = window.createImageBitmap;
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    window.__buytoolsRestoreCanvasFailure = () => {
      window.createImageBitmap = originalCreateImageBitmap;
      HTMLCanvasElement.prototype.getContext = originalGetContext;
    };
    window.createImageBitmap = async () => ({
      width: 16,
      height: 8,
      close() { window.__buytoolsBitmapCloseCount += 1; }
    });
    HTMLCanvasElement.prototype.getContext = function (...args) {
      if (this.width === 16 && this.height === 8) return null;
      return originalGetContext.apply(this, args);
    };
  });
  await page.locator("#run").click();
  await page.getByText(/Could not process file: Your browser could not allocate a canvas/i).waitFor();
  const singleBitmapCloseCount = await page.evaluate(() => window.__buytoolsBitmapCloseCount);
  await page.evaluate(() => window.__buytoolsRestoreCanvasFailure());
  assert.equal(singleBitmapCloseCount, 1, "Single-image canvas failure must close its ImageBitmap");

  await page.locator("#closeWork").click();
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), compressedResultUrl);
  await page.locator('[data-tool="image-resize"]').click();
  await page.locator("#fileInput").setInputFiles({ name: "sample.png", mimeType: "image/png", buffer: pngBuffer });
  await page.waitForFunction(() => document.querySelector("#preview")?.naturalWidth === 16);
  const resizePreviewUrl = await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.at(-1));
  const urlsBeforeDimensionLookup = await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.length);
  await page.locator("#width").fill("40");
  await page.waitForFunction(() => document.querySelector("#height")?.value === "20");
  assert.equal(
    await page.evaluate(() => window.__buytoolsObjectUrlAudit.created.length),
    urlsBeforeDimensionLookup,
    "Aspect-ratio dimension lookup must not allocate another object URL"
  );
  await page.locator("#width").fill("32");
  await page.locator("#height").fill("32");
  await page.locator("#run").click();
  await page.locator("#result a").waitFor();
  const resizedResultUrl = await page.locator("#result a").evaluate(anchor => anchor.href);
  const [resizedDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#result a").click()
  ]);
  assert.match(resizedDownload.suggestedFilename(), /resized\.png$/i);

  // Batch image fixtures: transparent PNG + portrait JPEG with distinct dimensions.
  const batchFixtureData = await page.evaluate(() => {
    const png = document.createElement("canvas");
    png.width = 16;
    png.height = 8;
    const pngContext = png.getContext("2d");
    pngContext.fillStyle = "#ff0000";
    pngContext.fillRect(0, 0, 8, 8);
    const jpeg = document.createElement("canvas");
    jpeg.width = 8;
    jpeg.height = 16;
    const jpegContext = jpeg.getContext("2d");
    jpegContext.fillStyle = "#2563eb";
    jpegContext.fillRect(0, 0, 8, 16);
    return {
      png: png.toDataURL("image/png"),
      jpeg: jpeg.toDataURL("image/jpeg", 0.9)
    };
  });
  const batchPngBuffer = Buffer.from(batchFixtureData.png.split(",")[1], "base64");
  const batchJpegBuffer = Buffer.from(batchFixtureData.jpeg.split(",")[1], "base64");
  const batchFiles = [
    { name: "transparent-source.png", mimeType: "image/png", buffer: batchPngBuffer },
    { name: "portrait-source.jpg", mimeType: "image/jpeg", buffer: batchJpegBuffer }
  ];
  async function readDownloadBuffer(download) {
    const stream = await download.createReadStream();
    let bytes = Buffer.alloc(0);
    for await (const chunk of stream) bytes = Buffer.concat([bytes, chunk]);
    return bytes;
  }
  async function inspectImageBuffer(buffer, mimeType) {
    return page.evaluate(async ({ base64, type }) => {
      const blob = await fetch("data:" + type + ";base64," + base64).then(response => response.blob());
      const bitmap = await createImageBitmap(blob);
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      context.drawImage(bitmap, 0, 0);
      const pixel = Array.from(context.getImageData(bitmap.width - 1, bitmap.height - 1, 1, 1).data);
      const dimensions = { width: bitmap.width, height: bitmap.height, pixel };
      bitmap.close();
      return dimensions;
    }, { base64: buffer.toString("base64"), type: mimeType });
  }

  const sourcePortraitInfo = await inspectImageBuffer(batchJpegBuffer, "image/jpeg");
  assert.deepEqual([sourcePortraitInfo.width, sourcePortraitInfo.height], [8, 16], "Portrait fixture must start at 8×16 pixels");

  // Batch image compressor: validate ZIP contents, JPEG output and transparent-pixel fill.
  await page.locator("#closeWork").click();
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), resizePreviewUrl);
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), resizedResultUrl);
  await page.locator('[data-tool="batch-compress"]').click();
  await auditAccessibility("batch image compressor");
  const largeBatchFixture = Buffer.alloc(26 * 1024 * 1024, 0);
  const jsZipRequestsBeforeBatchWarnings = thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/jszip@3.10.2")).length;
  await page.locator("#fileInput").setInputFiles({
    name: "large-batch-image.png",
    mimeType: "image/png",
    buffer: largeBatchFixture
  });
  let batchCompressorWarningMessage = "";
  page.once("dialog", async dialog => {
    batchCompressorWarningMessage = dialog.message();
    await dialog.dismiss();
  });
  await page.locator("#run").click();
  await page.getByText(/Batch image processing cancelled/i).waitFor();
  assert.match(batchCompressorWarningMessage, /25 MiB batch-image warning threshold/i);
  assert.equal(
    thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/jszip@3.10.2")).length,
    jsZipRequestsBeforeBatchWarnings,
    "Cancelling a large batch-compression selection must happen before the JSZip CDN is requested"
  );

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="batch-resize"]').click();
  await auditAccessibility("batch image resizer large-batch warning");
  await page.locator("#fileInput").setInputFiles({
    name: "large-batch-image.png",
    mimeType: "image/png",
    buffer: largeBatchFixture
  });
  let batchResizerWarningMessage = "";
  page.once("dialog", async dialog => {
    batchResizerWarningMessage = dialog.message();
    await dialog.dismiss();
  });
  await page.locator("#run").click();
  await page.getByText(/Batch image processing cancelled/i).waitFor();
  assert.match(batchResizerWarningMessage, /25 MiB batch-image warning threshold/i);
  assert.equal(
    thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/jszip@3.10.2")).length,
    jsZipRequestsBeforeBatchWarnings,
    "Cancelling a large batch-resize selection must happen before the JSZip CDN is requested"
  );

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="batch-compress"]').click();
  await page.locator("#fileInput").setInputFiles(batchFiles);
  const [batchCompressDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.getByText(/Finished 2 image\(s\)/).waitFor();
  assert.match(batchCompressDownload.suggestedFilename(), /compressed-images\.zip$/i);
  assert.ok(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/jszip@3.10.2")), "ZIP library should load on demand when batch compression is run");
  const compressedZip = await JSZip.loadAsync(await readDownloadBuffer(batchCompressDownload));
  const compressedNames = Object.keys(compressedZip.files).filter(name => !compressedZip.files[name].dir).sort();
  assert.deepEqual(compressedNames, ["001-transparent-source.jpg", "002-portrait-source.jpg"]);
  const compressedJpeg = await compressedZip.file("001-transparent-source.jpg").async("nodebuffer");
  assert.equal(compressedJpeg.readUInt16BE(0), 0xffd8, "Batch compressor should emit valid JPEG files");
  const compressedImageInfo = await inspectImageBuffer(compressedJpeg, "image/jpeg");
  assert.deepEqual([compressedImageInfo.width, compressedImageInfo.height], [16, 8]);
  assert.ok(
    compressedImageInfo.pixel[0] > 235 && compressedImageInfo.pixel[1] > 235 && compressedImageInfo.pixel[2] > 235,
    "Transparent PNG pixels should be filled with white in JPEG output"
  );
  const secondCompressed = await compressedZip.file("002-portrait-source.jpg").async("nodebuffer");
  const secondCompressedInfo = await inspectImageBuffer(secondCompressed, "image/jpeg");
  assert.deepEqual([secondCompressedInfo.width, secondCompressedInfo.height], [8, 16]);

  // A batch canvas failure must close the current ImageBitmap and release its canvas.
  await page.evaluate(() => {
    window.__buytoolsBitmapCloseCount = 0;
    const originalCreateImageBitmap = window.createImageBitmap;
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    window.__buytoolsRestoreCanvasFailure = () => {
      window.createImageBitmap = originalCreateImageBitmap;
      HTMLCanvasElement.prototype.getContext = originalGetContext;
    };
    window.createImageBitmap = async () => ({
      width: 16,
      height: 8,
      close() { window.__buytoolsBitmapCloseCount += 1; }
    });
    HTMLCanvasElement.prototype.getContext = function (...args) {
      if (this.width === 16 && this.height === 8) return null;
      return originalGetContext.apply(this, args);
    };
  });
  await page.locator("#run").click();
  await page.getByText(/Could not process the image batch: Your browser could not allocate a canvas/i).waitFor();
  const batchBitmapCloseCount = await page.evaluate(() => window.__buytoolsBitmapCloseCount);
  await page.evaluate(() => window.__buytoolsRestoreCanvasFailure());
  assert.equal(batchBitmapCloseCount, 1, "Batch-image canvas failure must close its ImageBitmap");

  // Batch image resizer: inspect both ZIP entries and preserve aspect ratios.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="batch-resize"]').click();
  await auditAccessibility("batch image resizer");
  await page.locator("#fileInput").setInputFiles(batchFiles);
  await page.locator("#width").fill("32");
  await page.locator("#height").fill("32");
  await page.locator("#keep").check();
  assert.equal(await page.locator("#width").inputValue(), "32", "Batch resize width control should retain the requested bound");
  assert.equal(await page.locator("#height").inputValue(), "32", "Batch resize height control should retain the requested bound");
  assert.equal(await page.locator("#keep").isChecked(), true, "Batch resize should preserve aspect ratio");
  const [batchResizeDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.getByText(/Finished 2 image\(s\)/).waitFor();
  assert.match(batchResizeDownload.suggestedFilename(), /resized-images\.zip$/i);
  const resizedZip = await JSZip.loadAsync(await readDownloadBuffer(batchResizeDownload));
  const resizedNames = Object.keys(resizedZip.files).filter(name => !resizedZip.files[name].dir).sort();
  assert.deepEqual(resizedNames, ["001-transparent-source.png", "002-portrait-source.png"]);
  const resizedFirst = await resizedZip.file("001-transparent-source.png").async("nodebuffer");
  const resizedFirstInfo = await inspectImageBuffer(resizedFirst, "image/png");
  assert.deepEqual([resizedFirstInfo.width, resizedFirstInfo.height], [32, 16]);
  const resizedSecond = await resizedZip.file("002-portrait-source.png").async("nodebuffer");
  const resizedSecondInfo = await inspectImageBuffer(resizedSecond, "image/png");
  assert.deepEqual([resizedSecondInfo.width, resizedSecondInfo.height], [16, 32]);

  // Reject batches above the documented 100-file safety limit before loading ZIP code.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="batch-compress"]').click();
  await page.locator("#fileInput").setInputFiles(Array.from({ length: 101 }, (_, index) => ({
    name: `limit-fixture-${index + 1}.png`,
    mimeType: "image/png",
    buffer: batchPngBuffer
  })));
  await page.locator("#run").click();
  await page.getByText(/100 images or fewer/i).waitFor();

  // Images to PDF: cancel large selections before the jsPDF CDN request, then verify binary image handling.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-images"]').click();
  await auditAccessibility("images to PDF tool");
  await page.locator("#run").click();
  await page.getByText("Choose a file first.").waitFor();
  const largeImageFixture = Buffer.alloc(26 * 1024 * 1024, 0);
  const jsPdfRequestsBeforeLargeImageWarning = thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/jspdf@4.2.1")).length;
  await page.locator("#fileInput").setInputFiles({
    name: "large-image.png",
    mimeType: "image/png",
    buffer: largeImageFixture
  });
  let imagesPdfWarningMessage = "";
  page.once("dialog", async dialog => {
    imagesPdfWarningMessage = dialog.message();
    await dialog.dismiss();
  });
  await page.locator("#run").click();
  await page.getByText(/Images-to-PDF conversion cancelled/i).waitFor();
  assert.match(imagesPdfWarningMessage, /25 MiB large-image warning threshold/i);
  assert.equal(
    thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/jspdf@4.2.1")).length,
    jsPdfRequestsBeforeLargeImageWarning,
    "Cancelling a large Images-to-PDF selection must happen before the jsPDF CDN is requested"
  );

  await page.locator("#fileInput").setInputFiles(batchFiles);
  await page.evaluate(() => {
    const originalReadAsDataURL = FileReader.prototype.readAsDataURL;
    window.__buytoolsRestoreImagePdfReader = () => {
      FileReader.prototype.readAsDataURL = originalReadAsDataURL;
    };
    FileReader.prototype.readAsDataURL = function () {
      throw new Error("Images-to-PDF should pass binary image bytes instead of using a base64 data URL");
    };
  });
  const [imagesPdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.evaluate(() => window.__buytoolsRestoreImagePdfReader());
  await page.getByText(/Created a PDF with 2 image\(s\)\./).waitFor();
  assert.equal(imagesPdfDownload.suggestedFilename(), "buytools-images.pdf");
  assert.ok(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/jspdf@4.2.1")), "Patched jsPDF 4.2.1 should load on demand when Images to PDF is run");
  assert.equal(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/jspdf@2.5.2")), false, "Vulnerable jsPDF 2.5.2 must never be requested");
  const imagesPdfBytes = await readDownloadBuffer(imagesPdfDownload);
  assert.ok(imagesPdfBytes.length > 500, "Images-to-PDF output should not be empty");
  const imagesPdf = await PDFDocument.load(imagesPdfBytes);
  assert.equal(imagesPdf.getPageCount(), 2, "Images-to-PDF should create one page per selected image");
  const imagePdfSizes = imagesPdf.getPages().map(pdfPage => pdfPage.getSize());
  assert.ok(imagePdfSizes[0].width > imagePdfSizes[0].height, "First PDF page should preserve the landscape image orientation");
  assert.ok(imagePdfSizes[1].height > imagePdfSizes[1].width, "Second PDF page should preserve the portrait image orientation");
  assert.ok(Math.abs(imagePdfSizes[0].width / imagePdfSizes[0].height - 2) < 0.03, "First PDF page should preserve the first image aspect ratio");
  assert.ok(Math.abs(imagePdfSizes[1].width / imagePdfSizes[1].height - 0.5) < 0.03, "Second PDF page should preserve the second image aspect ratio");

  // Text-to-PDF: validate the generated PDF signature and trailer.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="text-pdf"]').click();
  await page.locator("#text").fill("BuyTools browser smoke test\nPDF generation works.");
  const [pdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  assert.match(pdfDownload.suggestedFilename(), /\.pdf$/i);
  const pdfStream = await pdfDownload.createReadStream();
  let pdfBytes = Buffer.alloc(0);
  for await (const chunk of pdfStream) pdfBytes = Buffer.concat([pdfBytes, chunk]);
  assert.ok(pdfBytes.toString("utf8").startsWith("%PDF-1.4"), "Text-to-PDF output has no PDF header");
  assert.ok(pdfBytes.toString("utf8").includes("%%EOF"), "Text-to-PDF output has no EOF marker");

  // Generate valid PDF fixtures with distinct page dimensions.
  const pdfFixtures = [];
  for (const [width, height] of [[120, 180], [220, 280], [320, 380]]) {
    const doc = await PDFDocument.create();
    doc.addPage([width, height]);
    pdfFixtures.push(Buffer.from(await doc.save()));
  }

  // Large PDF selections require an explicit memory warning before the PDF CDN is loaded.
  const oversizedPdfBuffer = Buffer.alloc(26 * 1024 * 1024, 0x20);
  oversizedPdfBuffer.write("%PDF-1.4", 0, "ascii");
  const pdfLibraryRequestsBeforeWarning = thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/pdf-lib@1.17.1")).length;
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-merge"]').click();
  await page.locator("#fileInput").setInputFiles([
    { name: "large-part-1.pdf", mimeType: "application/pdf", buffer: oversizedPdfBuffer.subarray(0, 13 * 1024 * 1024) },
    { name: "large-part-2.pdf", mimeType: "application/pdf", buffer: oversizedPdfBuffer.subarray(13 * 1024 * 1024) }
  ]);
  assert.equal(await page.locator("#result").getAttribute("role"), "status", "PDF operation feedback should be announced as a status message");
  let mergeWarningMessage = "";
  page.once("dialog", async dialog => { mergeWarningMessage = dialog.message(); await dialog.dismiss(); });
  await page.locator("#run").click();
  await page.getByText(/PDF processing cancelled/i).waitFor();
  assert.match(mergeWarningMessage, /25 MiB large-file warning threshold/i);
  assert.equal(thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/pdf-lib@1.17.1")).length, pdfLibraryRequestsBeforeWarning, "Cancelling a large PDF merge must happen before the PDF CDN is loaded");

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-split"]').click();
  await page.locator("#fileInput").setInputFiles({ name: "large-document.pdf", mimeType: "application/pdf", buffer: oversizedPdfBuffer });
  let splitWarningMessage = "";
  page.once("dialog", async dialog => { splitWarningMessage = dialog.message(); await dialog.dismiss(); });
  await page.locator("#run").click();
  await page.getByText(/PDF processing cancelled/i).waitFor();
  assert.match(splitWarningMessage, /25 MiB large-file warning threshold/i);
  assert.equal(thirdPartyRequests.filter(url => url.href.startsWith("https://esm.sh/pdf-lib@1.17.1")).length, pdfLibraryRequestsBeforeWarning, "Cancelling a large PDF split must happen before the PDF CDN is loaded");

  // Merge three PDFs and verify the downloaded document structurally.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-merge"]').click();
  await page.locator("#fileInput").setInputFiles(pdfFixtures.map((buffer, index) => ({
    name: `fixture-${index + 1}.pdf`,
    mimeType: "application/pdf",
    buffer
  })));
  const [mergedDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.getByText(/Merged 3 PDF files/).waitFor();
  assert.match(mergedDownload.suggestedFilename(), /merged\.pdf$/i);
  const mergedStream = await mergedDownload.createReadStream();
  let mergedBytes = Buffer.alloc(0);
  for await (const chunk of mergedStream) mergedBytes = Buffer.concat([mergedBytes, chunk]);
  assert.ok(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/pdf-lib@1.17.1")), "PDF library should load on demand when a PDF operation is run");
  const mergedDoc = await PDFDocument.load(mergedBytes);
  assert.equal(mergedDoc.getPageCount(), 3, "PDF merger should preserve all three input pages");
  assert.deepEqual(mergedDoc.getPages().map(p => p.getSize()), [
    { width: 120, height: 180 },
    { width: 220, height: 280 },
    { width: 320, height: 380 }
  ], "PDF merger should preserve input order and page dimensions");

  // Split selected ranges and verify output page count and order.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-split"]').click();
  await auditAccessibility("PDF splitter tool");
  await page.locator("#fileInput").setInputFiles({
    name: "three-pages.pdf",
    mimeType: "application/pdf",
    buffer: mergedBytes
  });
  await page.locator("#pages").fill("1, 3");
  const [splitDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.locator("#result").getByText("Extracted 2 page(s)").waitFor();
  assert.match(splitDownload.suggestedFilename(), /pages\.pdf$/i);
  const splitStream = await splitDownload.createReadStream();
  let splitBytes = Buffer.alloc(0);
  for await (const chunk of splitStream) splitBytes = Buffer.concat([splitBytes, chunk]);
  const splitDoc = await PDFDocument.load(splitBytes);
  assert.equal(splitDoc.getPageCount(), 2);
  assert.deepEqual(splitDoc.getPages().map(p => p.getSize()), [
    { width: 120, height: 180 },
    { width: 320, height: 380 }
  ], "PDF splitter should return the requested pages in ascending order");

  // Reject out-of-range and malformed page selectors.
  await page.locator("#pages").fill("1, 4");
  await page.locator("#run").click();
  await page.getByText(/outside this PDF/i).waitFor();
  await page.locator("#pages").fill("1, nope");
  await page.locator("#run").click();
  await page.getByText(/Invalid page range/i).waitFor();

  // Theme toggle and narrow-screen layout.
  await page.locator("#closeWork").click();
  await page.locator("#themeToggle").click();
  assert.equal(await page.locator("body").evaluate(el => el.classList.contains("light-theme")), true);
  await page.waitForFunction(() => getComputedStyle(document.body).color === "rgb(23, 32, 51)", null, { timeout: 3000 });
  const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert.ok(dimensions.scrollWidth <= dimensions.width + 2, `Unexpected horizontal page overflow: ${JSON.stringify(dimensions)}`);

  // Background removal: exercise the existing disclosed AI workflow with a synthetic image,
  // record third-party response sizes where exposed, and verify no image payload is uploaded.
  assert.equal(thirdPartyRequests.some(url => url.hostname === "staticimgly.com"), false, "Background-removal model assets must not load until that feature is explicitly run");
  await page.locator('[data-tool="background"]').click();
  const backgroundModelSelector = page.locator("#backgroundModel");
  assert.equal(await backgroundModelSelector.inputValue(), "isnet_fp16", "Standard model should remain the default");
  assert.deepEqual(
    await backgroundModelSelector.locator("option").evaluateAll(options => options.map(option => option.value)),
    ["isnet_fp16", "isnet_quint8"],
    "Background removal should offer the standard and smaller quantized models"
  );
  const lightThemeColors = await page.evaluate(() => ({
    body: getComputedStyle(document.body).color,
    dropHeading: getComputedStyle(document.querySelector("#drop > strong")).color,
    filePicker: getComputedStyle(document.querySelector("#drop .filepick")).color,
    directoryHeading: getComputedStyle(document.querySelector(".tool-directory .feature b")).color
  }));
  assert.deepEqual(lightThemeColors, {
    body: "rgb(23, 32, 51)",
    dropHeading: "rgb(23, 32, 51)",
    filePicker: "rgb(23, 32, 51)",
    directoryHeading: "rgb(23, 32, 51)"
  }, "Light-theme foregrounds should use readable dark text on pale surfaces");
  await auditAccessibility("background removal tool in light theme");
  const backgroundFixtureData = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    context.fillStyle = "#2457a6";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#f8f8f8";
    context.beginPath();
    context.arc(64, 64, 30, 0, Math.PI * 2);
    context.fill();
    return canvas.toDataURL("image/png");
  });
  const backgroundFixture = Buffer.from(backgroundFixtureData.split(",")[1], "base64");
  await page.locator("#fileInput").setInputFiles({
    name: "synthetic-background-audit.png",
    mimeType: "image/png",
    buffer: backgroundFixture
  });
  const backgroundInputPreviewUrl = await page.locator("#preview").evaluate(image => image.src);
  const requestsBeforeDecline = thirdPartyRequestDetails.length;
  const declineDialogPromise = page.waitForEvent("dialog");
  const declineClickPromise = page.locator("#run").click();
  const declineDialog = await declineDialogPromise;
  assert.match(declineDialog.message(), /at least 90\.2 MiB/i, "Consent dialog should disclose the measured cold-cache transfer lower bound");
  await declineDialog.dismiss();
  await declineClickPromise;
  await page.getByText(/Background removal cancelled\. No AI model assets were requested\./i).waitFor();
  assert.equal(
    thirdPartyRequestDetails.length,
    requestsBeforeDecline,
    "Declining background-removal consent must not request the IMG.LY library or model assets"
  );

  const backgroundAuditStart = thirdPartyRequestDetails.length;
  await page.evaluate(() => {
    const status = document.querySelector("#result");
    window.__backgroundProgressMessages = [];
    const observer = new MutationObserver(() => window.__backgroundProgressMessages.push(status.textContent || ""));
    observer.observe(status, { childList: true, subtree: true, characterData: true });
    window.__backgroundProgressObserver = observer;
  });
  const backgroundDownloadPromise = page.waitForEvent("download", { timeout: 240000 });
  const acceptDialogPromise = page.waitForEvent("dialog");
  const backgroundClickPromise = page.locator("#run").click();
  const acceptDialog = await acceptDialogPromise;
  assert.match(acceptDialog.message(), /IMG\.LY/i, "Consent dialog should identify the third-party model provider");
  assert.match(acceptDialog.message(), /processed in this browser/i, "Consent dialog should clarify the local image-processing workflow");
  await acceptDialog.accept();
  const backgroundStartedAt = Date.now();
  await backgroundClickPromise;
  const backgroundDownload = await backgroundDownloadPromise;
  await page.getByText(/Background removal complete/i).waitFor({ timeout: 240000 });
  const backgroundPreviewUrl = await page.locator("#preview").evaluate(image => image.src);
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), backgroundInputPreviewUrl);
  const backgroundDurationMs = Date.now() - backgroundStartedAt;
  const backgroundOutput = await readDownloadBuffer(backgroundDownload);
  assert.ok(backgroundOutput.length > 8, "Background removal returned an empty file");
  assert.equal(
    backgroundOutput.subarray(0, 8).toString("hex"),
    "89504e470d0a1a0a",
    "Background removal should produce a valid PNG"
  );

  const progressEvidence = await page.evaluate(() => {
    window.__backgroundProgressObserver?.disconnect();
    const status = document.querySelector("#result");
    return {
      role: status?.getAttribute("role"),
      ariaLive: status?.getAttribute("aria-live"),
      messages: window.__backgroundProgressMessages || []
    };
  });
  assert.equal(progressEvidence.role, "status", "Background-removal progress should be exposed as a status message");
  assert.equal(progressEvidence.ariaLive, "polite", "Progress updates should be announced politely to assistive technology");
  assert.ok(
    progressEvidence.messages.some(message => /Downloading AI asset isnet_fp16:.*MB.*MB/i.test(message)),
    "Model-asset progress should display human-readable transferred-byte totals"
  );
  assert.ok(
    progressEvidence.messages.some(message => /Decoding image:/i.test(message)),
    "The progress UI should identify local image decoding"
  );
  assert.ok(
    progressEvidence.messages.some(message => /Running local AI inference:/i.test(message)),
    "The progress UI should distinguish local inference from network downloads"
  );
  assert.ok(
    progressEvidence.messages.some(message => /Encoding transparent PNG:/i.test(message)),
    "The progress UI should identify local output encoding"
  );
  assert.ok(
    progressEvidence.messages.some(message => /Preparing the transparent PNG/i.test(message)),
    "The progress UI should identify the post-inference output-preparation stage"
  );
  assert.equal(
    progressEvidence.messages.some(message => /Downloading AI asset compute:/i.test(message)),
    false,
    "Local compute stages must not be mislabeled as asset downloads"
  );
  assert.equal(
    progressEvidence.messages.some(message => /^Processing image:/i.test(message)),
    false,
    "Download progress must not be mislabeled as image inference"
  );

  const defaultCircleMetrics = await page.evaluate(async () => {
    const image = document.querySelector("#preview");
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const alpha = [];
    let alphaTotal = 0;
    let nonTransparent = 0;
    for (let i = 3; i < pixels.length; i += 4) {
      const value = pixels[i];
      alpha.push(value);
      alphaTotal += value;
      if (value > 0) nonTransparent++;
    }
    window.__buytoolsDefaultMasks = { circle: alpha };
    return {
      width: canvas.width,
      height: canvas.height,
      sizeBytes: null,
      nonTransparentRatio: Number((nonTransparent / alpha.length).toFixed(4)),
      meanAlpha: Number((alphaTotal / (alpha.length * 255)).toFixed(4))
    };
  });
  defaultCircleMetrics.sizeBytes = backgroundOutput.length;

  const backgroundRequests = thirdPartyRequestDetails.slice(backgroundAuditStart);
  const backgroundRelevantRequests = backgroundRequests.filter(detail => {
    const hostname = new URL(detail.url).hostname;
    return hostname === "esm.sh" || hostname === "staticimgly.com";
  });
  assert.ok(
    backgroundRelevantRequests.some(detail => new URL(detail.url).hostname === "esm.sh" && detail.url.includes("@imgly/background-removal@1.5.5")),
    "Background removal should load the pinned IMG.LY library on demand"
  );
  assert.ok(
    backgroundRelevantRequests.some(detail => new URL(detail.url).hostname === "staticimgly.com"),
    "Background removal should fetch its disclosed model/WASM assets on demand"
  );
  assert.deepEqual(
    backgroundRequests.filter(detail => detail.method !== "GET" || detail.requestBodyBytes > 0).map(detail => ({
      host: new URL(detail.url).hostname,
      method: detail.method,
      requestBodyBytes: detail.requestBodyBytes
    })),
    [],
    "Background-removal activation must not upload the selected image in an external request body"
  );
  const failedBackgroundResponses = backgroundRelevantRequests.filter(detail => ![200, 206, 304].includes(detail.status));
  assert.deepEqual(
    failedBackgroundResponses.map(detail => ({ url: detail.url, status: detail.status })),
    [],
    "All observed background-removal library/model requests should complete successfully"
  );
  for (const module of runtimeBaseline.observedModules.filter(item => item.modulePaths?.length)) {
    for (const modulePath of module.modulePaths) {
      assert.ok(
        backgroundRelevantRequests.some(detail => new URL(detail.url).pathname === modulePath),
        `Expected runtime module path was not observed: ${module.name}@${module.resolvedVersion} ${modulePath}`
      );
    }
  }
  const backgroundResourceTiming = await page.evaluate(() => performance.getEntriesByType("resource")
    .filter(entry => entry.name.startsWith("http://") || entry.name.startsWith("https://"))
    .filter(entry => {
      const hostname = new URL(entry.name).hostname;
      return hostname === "esm.sh" || hostname === "staticimgly.com";
    })
    .map(entry => ({
      host: new URL(entry.name).hostname,
      path: new URL(entry.name).pathname,
      durationMs: Math.round(entry.duration),
      transferSizeBytes: entry.transferSize || null,
      encodedBodyBytes: entry.encodedBodySize || null,
      decodedBodyBytes: entry.decodedBodySize || null
    })));
  const defaultModelRequests = backgroundRelevantRequests.filter(detail => new URL(detail.url).hostname === "staticimgly.com");
  const defaultKnownBytes = defaultModelRequests
    .filter(detail => detail.contentLengthBytes !== null)
    .reduce((sum, detail) => sum + detail.contentLengthBytes, 0);

  // A second synthetic fixture exercises a person-like silhouette. Both model variants
  // are compared on the same inputs; alpha-mask agreement is diagnostic, not a real-photo
  // quality score or grounds for changing the production default.
  const silhouetteFixtureData = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext("2d");
    context.fillStyle = "#dbeafe";
    context.fillRect(0, 0, 128, 128);
    context.fillStyle = "#172554";
    context.beginPath();
    context.arc(64, 25, 14, 0, Math.PI * 2);
    context.fill();
    context.fillRect(48, 42, 32, 43);
    context.lineCap = "round";
    context.lineWidth = 13;
    context.beginPath();
    context.moveTo(50, 51);
    context.lineTo(31, 77);
    context.moveTo(78, 51);
    context.lineTo(97, 77);
    context.stroke();
    context.lineWidth = 16;
    context.beginPath();
    context.moveTo(56, 82);
    context.lineTo(48, 115);
    context.moveTo(72, 82);
    context.lineTo(80, 115);
    context.stroke();
    return canvas.toDataURL("image/png");
  });

  const defaultSilhouetteMetrics = await page.evaluate(async dataUrl => {
    const mod = await import("https://esm.sh/@imgly/background-removal@1.5.5");
    const blob = await (await fetch(dataUrl)).blob();
    const started = performance.now();
    const result = await mod.removeBackground(blob, { model: "isnet_fp16" });
    const durationMs = Math.round(performance.now() - started);
    const signature = Array.from(new Uint8Array(await result.slice(0, 8).arrayBuffer()))
      .map(value => value.toString(16).padStart(2, "0")).join("");
    const bitmap = await createImageBitmap(result);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(bitmap, 0, 0);
    bitmap.close?.();
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const alpha = [];
    let alphaTotal = 0;
    let nonTransparent = 0;
    for (let i = 3; i < pixels.length; i += 4) {
      const value = pixels[i];
      alpha.push(value);
      alphaTotal += value;
      if (value > 0) nonTransparent++;
    }
    window.__buytoolsDefaultMasks.silhouette = alpha;
    return {
      width: canvas.width,
      height: canvas.height,
      sizeBytes: result.size,
      durationMs,
      pngSignatureValid: signature === "89504e470d0a1a0a",
      nonTransparentRatio: Number((nonTransparent / alpha.length).toFixed(4)),
      meanAlpha: Number((alphaTotal / (alpha.length * 255)).toFixed(4))
    };
  }, silhouetteFixtureData);

  const quantizedAuditStart = thirdPartyRequestDetails.length;
  const quantizedResults = await page.evaluate(async ({ circleDataUrl, silhouetteDataUrl }) => {
    const mod = await import("https://esm.sh/@imgly/background-removal@1.5.5");
    const fixtures = { circle: circleDataUrl, silhouette: silhouetteDataUrl };
    const results = {};
    for (const [name, dataUrl] of Object.entries(fixtures)) {
      const blob = await (await fetch(dataUrl)).blob();
      const started = performance.now();
      const result = await mod.removeBackground(blob, { model: "isnet_quint8" });
      const durationMs = Math.round(performance.now() - started);
      const signature = Array.from(new Uint8Array(await result.slice(0, 8).arrayBuffer()))
        .map(value => value.toString(16).padStart(2, "0")).join("");
      const bitmap = await createImageBitmap(result);
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      context.drawImage(bitmap, 0, 0);
      bitmap.close?.();
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      const alpha = [];
      let alphaTotal = 0;
      let nonTransparent = 0;
      for (let i = 3; i < pixels.length; i += 4) {
        const value = pixels[i];
        alpha.push(value);
        alphaTotal += value;
        if (value > 0) nonTransparent++;
      }
      const reference = window.__buytoolsDefaultMasks[name] || [];
      let absoluteDifference = 0;
      let intersection = 0;
      let union = 0;
      for (let i = 0; i < Math.min(alpha.length, reference.length); i++) {
        absoluteDifference += Math.abs(alpha[i] - reference[i]);
        const candidateForeground = alpha[i] >= 128;
        const referenceForeground = reference[i] >= 128;
        if (candidateForeground && referenceForeground) intersection++;
        if (candidateForeground || referenceForeground) union++;
      }
      results[name] = {
        width: canvas.width,
        height: canvas.height,
        sizeBytes: result.size,
        durationMs,
        pngSignatureValid: signature === "89504e470d0a1a0a",
        nonTransparentRatio: Number((nonTransparent / alpha.length).toFixed(4)),
        meanAlpha: Number((alphaTotal / (alpha.length * 255)).toFixed(4)),
        meanAbsoluteAlphaDifference: reference.length === alpha.length
          ? Number((absoluteDifference / (alpha.length * 255)).toFixed(4))
          : null,
        binaryMaskIoU: reference.length === alpha.length && union > 0
          ? Number((intersection / union).toFixed(4))
          : null
      };
    }
    return results;
  }, { circleDataUrl: backgroundFixtureData, silhouetteDataUrl: silhouetteFixtureData });

  for (const [fixtureName, metrics] of Object.entries(quantizedResults)) {
    assert.equal(metrics.pngSignatureValid, true, "Quantized model should produce a valid PNG for " + fixtureName);
    assert.equal(metrics.width, 128, "Quantized output width should match the fixture for " + fixtureName);
    assert.equal(metrics.height, 128, "Quantized output height should match the fixture for " + fixtureName);
    assert.ok(metrics.sizeBytes > 8, "Quantized output should not be empty for " + fixtureName);
    assert.notEqual(metrics.meanAbsoluteAlphaDifference, null, "Model comparison should include alpha-mask differences for " + fixtureName);
  }
  assert.equal(defaultSilhouetteMetrics.pngSignatureValid, true, "Default model should produce a valid PNG for the silhouette fixture");
  assert.equal(defaultSilhouetteMetrics.width, 128);
  assert.equal(defaultSilhouetteMetrics.height, 128);

  const quantizedRequests = thirdPartyRequestDetails.slice(quantizedAuditStart);
  const quantizedModelRequests = quantizedRequests.filter(detail => new URL(detail.url).hostname === "staticimgly.com");
  assert.ok(quantizedModelRequests.length > 0, "Quantized model should load its model assets on demand");
  assert.deepEqual(
    quantizedRequests.filter(detail => detail.method !== "GET" || detail.requestBodyBytes > 0).map(detail => ({
      host: new URL(detail.url).hostname,
      method: detail.method,
      requestBodyBytes: detail.requestBodyBytes
    })),
    [],
    "Quantized model benchmark must not upload either synthetic input"
  );
  const failedQuantizedResponses = quantizedModelRequests.filter(detail => ![200, 206, 304].includes(detail.status));
  assert.deepEqual(
    failedQuantizedResponses.map(detail => ({ url: detail.url, status: detail.status })),
    [],
    "All quantized model asset requests should complete successfully"
  );
  const quantizedKnownBytes = quantizedModelRequests
    .filter(detail => detail.contentLengthBytes !== null)
    .reduce((sum, detail) => sum + detail.contentLengthBytes, 0);
  assert.ok(quantizedKnownBytes > 0, "Quantized model benchmark should capture at least one Content-Length value");
  assert.ok(
    defaultKnownBytes > quantizedKnownBytes,
    `Expected the quantized model's known transfer lower bound (${quantizedKnownBytes}) to be below the default model's (${defaultKnownBytes})`
  );

  console.log("Background-removal default-model audit: " + JSON.stringify({
    outputBytes: backgroundOutput.length,
    durationMs: backgroundDurationMs,
    progressMessages: progressEvidence.messages.filter(message => /Downloading AI asset|Decoding image|Running local AI inference|Encoding transparent PNG|Preparing the transparent PNG/i.test(message)),
    lightThemeStatusRole: progressEvidence.role,
    externalRequestCount: backgroundRelevantRequests.length,
    modelAssetRequests: defaultModelRequests.length,
    contentLengthKnownResponses: defaultModelRequests.filter(detail => detail.contentLengthBytes !== null).length,
    summedContentLengthBytes: defaultKnownBytes,
    outputMetrics: { circle: defaultCircleMetrics, silhouette: defaultSilhouetteMetrics },
    requests: backgroundRelevantRequests.map(detail => ({
      host: new URL(detail.url).hostname,
      path: new URL(detail.url).pathname,
      method: detail.method,
      status: detail.status,
      contentType: detail.contentType,
      contentLengthBytes: detail.contentLengthBytes,
      requestBodyBytes: detail.requestBodyBytes
    })),
    resourceTiming: backgroundResourceTiming
  }, null, 2));
  console.log("Background-removal model comparison (synthetic fixtures; alpha-mask agreement is diagnostic, not a real-photo quality score): " + JSON.stringify({
    defaultModel: { name: "isnet_fp16", knownTransferLowerBoundBytes: defaultKnownBytes },
    quantizedModel: {
      name: "isnet_quint8",
      assetRequests: quantizedModelRequests.length,
      contentLengthKnownResponses: quantizedModelRequests.filter(detail => detail.contentLengthBytes !== null).length,
      knownTransferLowerBoundBytes: quantizedKnownBytes,
      outputMetrics: quantizedResults
    },
    knownTransferReductionPercent: Number(((1 - quantizedKnownBytes / defaultKnownBytes) * 100).toFixed(1))
  }, null, 2));

  // The smaller model has a separate session consent gate; declining it must not reuse
  // acceptance of the standard model. Then exercise the smaller model through the UI.
  await backgroundModelSelector.selectOption("isnet_quint8");
  const smallerRequestsBeforeDecline = thirdPartyRequestDetails.length;
  const smallerDeclineDialogPromise = page.waitForEvent("dialog");
  const smallerDeclineClickPromise = page.locator("#run").click();
  const smallerDeclineDialog = await smallerDeclineDialogPromise;
  assert.match(smallerDeclineDialog.message(), /at least 48\.4 MiB/i, "Smaller-model consent should disclose its measured lower bound");
  await smallerDeclineDialog.dismiss();
  await smallerDeclineClickPromise;
  await page.getByText(/Background removal cancelled\. No AI model assets were requested\./i).waitFor();
  assert.equal(
    thirdPartyRequestDetails.length,
    smallerRequestsBeforeDecline,
    "Declining smaller-model consent must not request the IMG.LY library or model assets"
  );

  const smallerDownloadPromise = page.waitForEvent("download", { timeout: 240000 });
  const smallerAcceptDialogPromise = page.waitForEvent("dialog");
  const smallerClickPromise = page.locator("#run").click();
  const smallerAcceptDialog = await smallerAcceptDialogPromise;
  assert.match(smallerAcceptDialog.message(), /smaller quantized model/i, "The consent dialog should identify the selected model");
  await smallerAcceptDialog.accept();
  await smallerClickPromise;
  const smallerDownload = await smallerDownloadPromise;
  await page.getByText(/Background removal complete with the smaller quantized model/i).waitFor({ timeout: 240000 });
  const smallerOutput = await readDownloadBuffer(smallerDownload);
  assert.ok(smallerOutput.length > 8, "Smaller-model background removal returned an empty file");
  assert.equal(
    smallerOutput.subarray(0, 8).toString("hex"),
    "89504e470d0a1a0a",
    "Smaller-model background removal should produce a valid PNG"
  );
  const smallerPreviewUrl = await page.locator("#preview").evaluate(image => image.src);
  const smallerUiRequests = thirdPartyRequestDetails.slice(smallerRequestsBeforeDecline);
  assert.deepEqual(
    smallerUiRequests.filter(detail => detail.method !== "GET" || detail.requestBodyBytes > 0).map(detail => ({
      host: new URL(detail.url).hostname,
      method: detail.method,
      requestBodyBytes: detail.requestBodyBytes
    })),
    [],
    "Smaller-model UI processing must not upload the selected image"
  );

  await page.locator("#closeWork").click();
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), backgroundPreviewUrl);
  await page.waitForFunction(url => window.__buytoolsObjectUrlAudit.revoked.includes(url), smallerPreviewUrl);

  await Promise.all(responseHashPromises);
  const expectedRuntimeModules = runtimeBaseline.observedModules.filter(item => item.modulePaths?.length);
  for (const module of expectedRuntimeModules) {
    for (const modulePath of module.modulePaths) {
      const response = backgroundRelevantRequests.find(detail => new URL(detail.url).pathname === modulePath);
      assert.ok(
        response && response.status === 200 && /^[0-9a-f]{64}$/.test(response.sha256 || "") && response.responseBodyBytes > 0,
        `Runtime module response must have a captured SHA-256: ${module.name}@${module.resolvedVersion} ${modulePath}`
      );
    }
  }
  const allModelAssetRequests = [...defaultModelRequests, ...quantizedModelRequests];
  const wasmAssetRequests = allModelAssetRequests.filter(detail => (detail.contentType || "").includes("application/wasm"));
  const unhashedModelAssets = allModelAssetRequests.filter(detail =>
    !new URL(detail.url).pathname.startsWith(runtimeBaseline.assetOrigin.pathPrefix) ||
    detail.status !== 200 ||
    detail.requestBodyBytes !== 0 ||
    (!(detail.contentType || "").includes("application/wasm") &&
      (!/^[0-9a-f]{64}$/.test(detail.sha256 || "") || !(detail.responseBodyBytes > 0)))
  );
  assert.ok(wasmAssetRequests.length > 0, "The background-removal WASM resource should be observed");
  assert.ok(
    wasmAssetRequests.every(detail => detail.status === 200 && detail.requestBodyBytes === 0),
    "Streamed WASM responses should succeed without an external request body"
  );
  if (unhashedModelAssets.length) {
    console.error("Model/WASM response hash capture failures: " + JSON.stringify(unhashedModelAssets.map(detail => ({
      url: detail.url,
      status: detail.status,
      responseBodyBytes: detail.responseBodyBytes,
      sha256: detail.sha256,
      hashError: detail.hashError
    })), null, 2));
  }
  assert.deepEqual(
    unhashedModelAssets.map(detail => detail.url),
    [],
    "Every observed model/WASM response must have a successful status, the versioned origin path and a SHA-256 response hash"
  );
  assert.ok(
    allModelAssetRequests.some(detail => new URL(detail.url).pathname === runtimeBaseline.assetOrigin.manifestPath),
    "The versioned model resource manifest should be observed"
  );

  const evidence = detail => ({
    url: detail.url,
    method: detail.method,
    status: detail.status,
    contentType: detail.contentType,
    contentLengthBytes: detail.contentLengthBytes,
    responseBodyBytes: detail.responseBodyBytes,
    sha256: detail.sha256,
    hashError: detail.hashError
  });
  const runtimeProvenance = {
    schemaVersion: 1,
    capturedAt: new Date().toISOString(),
    sourceCommit: process.env.GITHUB_SHA || null,
    workflowRunId: process.env.GITHUB_RUN_ID || null,
    baselineFile: "audits/background-removal-runtime-baseline.json",
    modules: runtimeBaseline.observedModules.map(module => ({
      name: module.name,
      requestedRange: module.requestedRange,
      resolvedVersion: module.resolvedVersion,
      license: module.license,
      role: module.role,
      bundled: module.modulePaths.length === 0,
      requests: module.pathPrefix
        ? backgroundRelevantRequests
            .filter(detail => new URL(detail.url).hostname === "esm.sh" && new URL(detail.url).pathname.startsWith(module.pathPrefix))
            .map(evidence)
        : []
    })),
    assets: {
      origin: runtimeBaseline.assetOrigin,
      standardModel: {
        name: runtimeBaseline.assetOrigin.models.standard,
        requestCount: defaultModelRequests.length,
        knownContentLengthResponses: defaultModelRequests.filter(detail => detail.contentLengthBytes !== null).length,
        knownTransferLowerBoundBytes: defaultKnownBytes,
        requests: defaultModelRequests.map(evidence)
      },
      quantizedModel: {
        name: runtimeBaseline.assetOrigin.models.quantized,
        requestCount: quantizedModelRequests.length,
        knownContentLengthResponses: quantizedModelRequests.filter(detail => detail.contentLengthBytes !== null).length,
        knownTransferLowerBoundBytes: quantizedKnownBytes,
        requests: quantizedModelRequests.map(evidence)
      }
    },
    integrity: {
      algorithm: "SHA-256",
      scope: "response-body audit snapshot",
      streamedWasmResponsesWithoutExposedBody: wasmAssetRequests.filter(detail => !detail.sha256).length,
      wasmHashLimitation: "Playwright exposed zero response-body bytes for the streamed application/wasm response; no empty-body digest is recorded.",
      runtimeSubresourceIntegrityEnforced: false
    }
  };
  await writeFile(new URL("../runtime-provenance.json", import.meta.url), JSON.stringify(runtimeProvenance, null, 2) + "\n");

  assert.deepEqual(pageErrors, [], "Browser console reported uncaught page errors");
  const externalHosts = [...new Set(thirdPartyRequests.map(url => url.hostname))].sort();
  console.log("On-demand third-party request hosts observed: " + externalHosts.join(", "));
  console.log("Background-removal runtime SHA-256 snapshot: " + JSON.stringify({
    sourceCommit: runtimeProvenance.sourceCommit,
    workflowRunId: runtimeProvenance.workflowRunId,
    moduleResponseCount: runtimeProvenance.modules.reduce((sum, module) => sum + module.requests.length, 0),
    hashedModuleResponses: runtimeProvenance.modules.reduce((sum, module) => sum + module.requests.filter(item => item.sha256).length, 0),
    modelAssetResponseCount: allModelAssetRequests.length,
    hashedModelAssetResponses: allModelAssetRequests.filter(item => item.sha256).length,
    artifact: "runtime-provenance.json"
  }, null, 2));
  console.log(`Browser smoke tests passed: ${toolCount} tool cards; initial first-party-only page load; on-demand QR, PDF, ZIP and image-to-PDF requests; homepage directory navigation, JSON, CSV, TypeScript, CSV Viewer, image compression/resizing, batch image ZIP compression/resizing, Images-to-PDF, text-to-PDF, PDF merge/split, stage-aware background-removal progress, per-model consent, standard and smaller quantized-model UI workflows, synthetic model benchmark, downloads, theme, 390px mobile layout and axe audits.`);
} finally {
  await browser.close();
}
