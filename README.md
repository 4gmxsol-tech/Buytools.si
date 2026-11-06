# BuyTools.si

BuyTools.si is a responsive collection of free browser-based utilities for image conversion and compression, PDF creation, text cleanup, developer workflows and everyday conversions.

## Current site features
- Searchable tool directory with category filters and persistent dark/light theme preference
- Image conversion, single-image compression and resizing, plus batch image compression and batch resizing with ZIP downloads
- Images-to-PDF and text-to-PDF tools
- Browser-based background-removal prototype (loads a third-party AI model)
- Word counter, case converter, whitespace cleaner
- JSON formatter/minifier, Base64 encoder/decoder, URL encoder/decoder
- QR code generator, password generator, unit converter, color converter, percentage calculator, Unix timestamp converter, UUID generator and text hash generator
- PDF merge and page extraction, CSV ↔ JSON conversion, CSV table viewer/sorter with search and filtered export, regex tester, Markdown preview, text comparison and URL slug generator
- Color contrast checker, HTML entity encoder, JSON-to-TypeScript starter generator, lorem ipsum generator, random number generator, and date difference calculator
- Dedicated SEO landing pages for PDF merge/split, CSV/JSON conversion and CSV viewing, regex testing, Markdown preview, color contrast, UUIDs, JSON-to-TypeScript, percentage, timestamps and date differences
- Dedicated landing pages for all 22 tools and three practical SEO guides
- About, privacy, terms and third-party license-notice pages
- XML sitemap, robots.txt, custom 404 page, favicon, and GitHub Pages deployment workflow
- Automated quality checks for metadata, exact canonicals, sitemap coverage, internal links, tool renderer mappings and inline JavaScript syntax

## Run locally
Open `index.html` in a modern browser, or serve the repository with any static web server. Some features dynamically load third-party libraries or services and therefore require an internet connection.

## SEO and quality
The sitemap is at `/sitemap.xml`. Run the structural and SEO checks (Python 3 + Node.js) with:

```bash
python scripts/check_site.py
```

The check validates sitemap XML and full page coverage, exact canonical and Open Graph URLs, titles, descriptions, language and viewport metadata, static internal links, duplicate IDs, tool catalogue-to-renderer mappings, robots.txt and inline JavaScript syntax. It does not replace browser testing, Search Console review, accessibility audits or Core Web Vitals measurement.

## Browser smoke tests

GitHub Actions also runs Playwright with Chromium against a local static server. The browser suite exercises tool discovery, JSON validation, CSV conversion edge cases, TypeScript generation, CSV filtering and download, image compression/resizing, text-to-PDF, theme switching and a narrow mobile viewport.

To run it locally, install Node.js 24+, install Playwright and Chromium, start a static server on port 8000, then run:

```bash
npm install --no-save --no-package-lock playwright@1.56.1
npx playwright install chromium
python3 -m http.server 8000
# In another terminal:
node scripts/browser_smoke.mjs
```

After each production deployment, the Pages workflow fetches every URL in `sitemap.xml` and verifies HTTP 200, a page title and the expected canonical URL.

## Monetization
Read [MONETIZATION.md](MONETIZATION.md) before enabling ads or affiliate links. No advertising publisher script or ads.txt entry is configured by default. Use only the exact code and seller record supplied by an approved provider.

## Privacy
Many image and text tools are designed to process data in the browser. The QR generator sends its input to a third-party QR service, and the background-removal feature loads a third-party library/model. See the [Privacy Policy](https://buytools.si/privacy/) for more detail.

## Deployment
The site is static and deploys through GitHub Pages. Configure the custom domain and HTTPS in repository Pages settings. Do not report a deployment as successful until the relevant GitHub Actions run and live site are verified.
