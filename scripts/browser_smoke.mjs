import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", error => pageErrors.push(error.message));

try {
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "load" });
  await page.locator('[data-tool]').first().waitFor();
  const toolCount = await page.locator('[data-tool]').count();
  assert.ok(toolCount >= 38, `Expected at least 38 tools, found ${toolCount}`);

  // Search and discoverability.
  await page.locator("#search").fill("CSV Viewer");
  assert.equal(await page.locator('[data-tool]').count(), 1);
  assert.equal(await page.locator('[data-tool="csv-viewer"]').count(), 1);
  await page.locator("#search").fill("");

  // JSON formatter: valid and invalid input.
  await page.locator('[data-tool="json"]').click();
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

  // Theme toggle and narrow-screen layout.
  await page.locator("#closeWork").click();
  await page.locator("#themeToggle").click();
  assert.equal(await page.locator("body").evaluate(el => el.classList.contains("light-theme")), true);
  const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert.ok(dimensions.scrollWidth <= dimensions.width + 2, `Unexpected horizontal page overflow: ${JSON.stringify(dimensions)}`);

  assert.deepEqual(pageErrors, [], "Browser console reported uncaught page errors");
  console.log(`Browser smoke tests passed: ${toolCount} tool cards; JSON, CSV, TypeScript, CSV viewer, download, theme and mobile layout.`);
} finally {
  await browser.close();
}
