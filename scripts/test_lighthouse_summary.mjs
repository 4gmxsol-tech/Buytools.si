import test from "node:test";
import assert from "node:assert/strict";
import { renderLighthouseMarkdown, summarizeLighthouseReport } from "./lighthouse_summary.mjs";

const sample = {
  finalDisplayedUrl: "http://127.0.0.1:8000/",
  configSettings: { formFactor: "mobile" },
  categories: {
    performance: { score: 0.943 },
    accessibility: { score: 1 },
    "best-practices": { score: 0.91 },
    seo: { score: 0.98 },
  },
  audits: {
    "first-contentful-paint": { displayValue: "1.2 s", numericValue: 1200 },
    "largest-contentful-paint": { displayValue: "2.4 s", numericValue: 2400 },
    "total-blocking-time": { displayValue: "180 ms", numericValue: 180 },
    "cumulative-layout-shift": { displayValue: "0.03", numericValue: 0.03 },
    "speed-index": { displayValue: "1.8 s", numericValue: 1800 },
    "total-byte-weight": { displayValue: "142 KiB", numericValue: 145408 },
  },
};

test("summarizes category scores and key lab metrics", () => {
  const result = summarizeLighthouseReport(sample);
  assert.equal(result.device, "mobile");
  assert.equal(result.scores.Performance, 94);
  assert.equal(result.scores.Accessibility, 100);
  assert.equal(result.scores["Best practices"], 91);
  assert.equal(result.scores.SEO, 98);
  assert.equal(result.metrics.LCP, "2.4 s");
  assert.equal(result.metrics.TBT, "180 ms");
  assert.equal(result.metrics.CLS, "0.03");
  assert.equal(result.metrics["Page weight"], "142 KiB");
});

test("accepts a Lighthouse result nested in a wrapper and tolerates missing audits", () => {
  const result = summarizeLighthouseReport({ lighthouseResult: { finalUrl: "https://example.test/", categories: {}, audits: {} } });
  assert.equal(result.url, "https://example.test/");
  assert.equal(result.scores.Performance, null);
  assert.equal(result.metrics.LCP, null);
});

test("rejects non-report input", () => {
  assert.throws(() => summarizeLighthouseReport(null), /report object is required/i);
});

test("renders a table and explicitly distinguishes TBT from field INP", () => {
  const markdown = renderLighthouseMarkdown([summarizeLighthouseReport(sample)]);
  assert.match(markdown, /\| Performance \| Accessibility \| Best practices \| SEO \| LCP \| TBT \| CLS/);
  assert.match(markdown, /TBT is not INP/);
  assert.match(markdown, /field Core Web Vitals/);
});
