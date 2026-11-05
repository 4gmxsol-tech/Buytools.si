#!/usr/bin/env node
/**
 * Convert Lighthouse JSON reports into a compact, honest CI summary.
 * These are lab measurements; this script never infers field Core Web Vitals.
 */
import { appendFileSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const CATEGORIES = [
  ["performance", "Performance"],
  ["accessibility", "Accessibility"],
  ["best-practices", "Best practices"],
  ["seo", "SEO"],
];

const METRICS = [
  ["first-contentful-paint", "FCP"],
  ["largest-contentful-paint", "LCP"],
  ["total-blocking-time", "TBT"],
  ["cumulative-layout-shift", "CLS"],
  ["speed-index", "Speed index"],
  ["total-byte-weight", "Page weight"],
];

export function summarizeLighthouseReport(input) {
  const report = input?.lighthouseResult ?? input;
  if (!report || typeof report !== "object") {
    throw new TypeError("A Lighthouse report object is required.");
  }

  const scores = Object.fromEntries(CATEGORIES.map(([id, label]) => {
    const score = report.categories?.[id]?.score;
    return [label, Number.isFinite(score) ? Math.round(score * 100) : null];
  }));

  const metrics = Object.fromEntries(METRICS.map(([id, label]) => {
    const audit = report.audits?.[id];
    const value = typeof audit?.displayValue === "string"
      ? audit.displayValue
      : Number.isFinite(audit?.numericValue)
        ? String(audit.numericValue)
        : null;
    return [label, value];
  }));

  return {
    url: report.finalDisplayedUrl ?? report.finalUrl ?? report.requestedUrl ?? "Unknown URL",
    device: report.configSettings?.formFactor ?? "unknown",
    scores,
    metrics,
  };
}

export function renderLighthouseMarkdown(summaries) {
  if (!Array.isArray(summaries)) {
    throw new TypeError("Expected an array of Lighthouse summaries.");
  }

  const cell = value => value === null || value === undefined ? "—" : String(value).replaceAll("|", "\\|");
  const rows = summaries.map(item => [
    item.url,
    item.device,
    item.scores.Performance,
    item.scores.Accessibility,
    item.scores["Best practices"],
    item.scores.SEO,
    item.metrics.LCP,
    item.metrics.TBT,
    item.metrics.CLS,
    item.metrics["Page weight"],
  ]);

  return [
    "## Lighthouse lab baseline",
    "",
    "| URL | Device | Performance | Accessibility | Best practices | SEO | LCP | TBT | CLS | Page weight |",
    "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ...rows.map(row => `| ${row.map(cell).join(" | ")} |`),
    "",
    "> These are individual Lighthouse lab runs. TBT is not INP, and lab metrics do not establish field Core Web Vitals. Use Search Console / CrUX field data when available.",
    "",
  ].join("\n");
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const paths = process.argv.slice(2);
  if (paths.length === 0) {
    console.error("Usage: node scripts/lighthouse_summary.mjs <report.json> [report.json ...]");
    process.exitCode = 2;
  } else {
    try {
      const summaries = paths.map(path => summarizeLighthouseReport(JSON.parse(readFileSync(path, "utf8"))));
      const markdown = renderLighthouseMarkdown(summaries);
      process.stdout.write(markdown);
      if (process.env.GITHUB_STEP_SUMMARY) {
        appendFileSync(process.env.GITHUB_STEP_SUMMARY, markdown);
      }
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    }
  }
}
