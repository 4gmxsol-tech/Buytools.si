import assert from "node:assert/strict";
import { chromium } from "playwright";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axe = require("axe-core");
import { PDFDocument } from "pdf-lib";
import JSZip from "jszip";

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
const page = await context.newPage();
const pageErrors = [];
const thirdPartyRequests = [];
page.on("pageerror", error => pageErrors.push(error.message));
page.on("request", request => {
  const requestUrl = new URL(request.url());
  if (
    ["http:", "https:"].includes(requestUrl.protocol) &&
    requestUrl.hostname !== "127.0.0.1" &&
    requestUrl.hostname !== "localhost"
  ) {
    thirdPartyRequests.push(requestUrl);
  }
});

try {
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  assert.equal(thirdPartyRequests.length, 0, "Initial page load must not contact third-party hosts before a tool is used");

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
  const toolCount = await page.locator('[data-tool]').count();
  assert.ok(toolCount >= 38, `Expected at least 38 tools, found ${toolCount}`);

  // Search and discoverability.
  await page.locator("#search").fill("CSV Viewer");
  assert.equal(await page.locator('[data-tool]').count(), 1);
  assert.equal(await page.locator('[data-tool="csv-viewer"]').count(), 1);
  await page.locator("#search").fill("");

  // JSON formatter: valid and invalid input.
  await page.locator('[data-tool="json"]').click();
  await auditAccessibility("JSON formatter tool");
  await page.locator("#text").fill('{"hello":"world","count":2}');
  await page.locator('[data-json="pretty"]').click();
  assert.match(await page.locator("#text").inputValue(), /\n  "hello": "world"/);
  assert.match(await page.locator("#result").innerText(), /Valid JSON/);
  await page.locator("#text").fill('{"broken":');
  await page.locator('[data-json="pretty"]').click();
  assert.match(await page.locator("#result").innerText(), /Invalid JSON/);

  // CSV converter: BOM, normal conversion, duplicate-header guard and CSV quoting.
  await page.locator("#closeWork").click();
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


  // QR generator: verify the disclosed third-party request occurs only after an explicit action and encodes the input safely.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="qr"]').click();
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

  // CSV viewer: parse, filter and download the filtered result.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="csv-viewer"]').click();
  await page.locator("#text").fill("sku,product,category,stock\nA-104,Desk lamp,Home,18\nB-208,USB cable,Electronics,0\nC-311,Notebook,Stationery,42");
  await page.locator("#run").click();
  assert.equal(await page.locator("#csvTable tbody tr").count(), 3);
  await page.locator("#csvFilter").fill("Electronics");
  assert.equal(await page.locator("#csvTable tbody tr").count(), 1);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#csvExport").click()
  ]);
  const stream = await download.createReadStream();
  let csvOutput = "";
  for await (const chunk of stream) csvOutput += chunk.toString("utf8");
  assert.match(csvOutput, /USB cable/);
  assert.doesNotMatch(csvOutput, /Desk lamp/);

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

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="image-compress"]').click();
  await page.locator("#fileInput").setInputFiles({ name: "sample.png", mimeType: "image/png", buffer: pngBuffer });
  await page.locator("#run").click();
  await page.locator("#result a").waitFor();
  const [compressedDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#result a").click()
  ]);
  assert.match(compressedDownload.suggestedFilename(), /\.jpg$/i);
  const compressedStream = await compressedDownload.createReadStream();
  let compressedBytes = 0;
  for await (const chunk of compressedStream) compressedBytes += chunk.length;
  assert.ok(compressedBytes > 0, "Image compressor produced an empty file");

  await page.locator("#closeWork").click();
  await page.locator('[data-tool="image-resize"]').click();
  await page.locator("#fileInput").setInputFiles({ name: "sample.png", mimeType: "image/png", buffer: pngBuffer });
  await page.locator("#width").fill("32");
  await page.locator("#height").fill("32");
  await page.locator("#run").click();
  await page.locator("#result a").waitFor();
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
  await page.locator('[data-tool="batch-compress"]').click();
  await auditAccessibility("batch image compressor");
  await page.locator("#fileInput").setInputFiles(batchFiles);
  const [batchCompressDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.getByText(/Finished 2 image\(s\)/).waitFor();
  assert.match(batchCompressDownload.suggestedFilename(), /compressed-images\.zip$/i);
  assert.ok(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/jszip@3.10.1")), "ZIP library should load on demand when batch compression is run");
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

  // Images to PDF: generate two pages from PNG/JPEG and verify page order/orientation.
  await page.locator("#closeWork").click();
  await page.locator('[data-tool="pdf-images"]').click();
  await auditAccessibility("images to PDF tool");
  await page.locator("#run").click();
  await page.getByText("Choose a file first.").waitFor();
  await page.locator("#fileInput").setInputFiles(batchFiles);
  const [imagesPdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#run").click()
  ]);
  await page.getByText(/Created a PDF with 2 image\(s\)\./).waitFor();
  assert.equal(imagesPdfDownload.suggestedFilename(), "buytools-images.pdf");
  assert.ok(thirdPartyRequests.some(url => url.href.startsWith("https://esm.sh/jspdf@2.5.2")), "jsPDF should load on demand when Images to PDF is run");
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
  const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert.ok(dimensions.scrollWidth <= dimensions.width + 2, `Unexpected horizontal page overflow: ${JSON.stringify(dimensions)}`);

  assert.equal(thirdPartyRequests.some(url => url.hostname === "staticimgly.com"), false, "Background-removal model assets must not load until that feature is explicitly run");
  assert.deepEqual(pageErrors, [], "Browser console reported uncaught page errors");
  const externalHosts = [...new Set(thirdPartyRequests.map(url => url.hostname))].sort();
  console.log("On-demand third-party request hosts observed: " + externalHosts.join(", "));
  console.log(`Browser smoke tests passed: ${toolCount} tool cards; initial first-party-only page load; on-demand QR, PDF, ZIP and image-to-PDF requests; homepage directory navigation, JSON, CSV, TypeScript, CSV Viewer, image compression/resizing, batch image ZIP compression/resizing, Images-to-PDF, text-to-PDF, PDF merge/split, downloads, theme, 390px mobile layout and axe audits.`);
} finally {
  await browser.close();
}
