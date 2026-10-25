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
- Five focused tool landing pages and three practical SEO guides
- About, privacy and terms pages
- XML sitemap, robots.txt, custom 404 page, favicon, and GitHub Pages deployment workflow
- Automated static checks for page metadata, canonical URLs and sitemap targets

## Run locally
Open `index.html` in a modern browser, or serve the repository with any static web server. Some features dynamically load third-party libraries or services and therefore require an internet connection.

## SEO and quality
The sitemap is at `/sitemap.xml`. Run the dependency-free static checks with:

```bash
python scripts/check_site.py
```

The check validates sitemap XML, URL-to-file mapping, unique sitemap entries, titles, descriptions, language attributes, viewport metadata and canonical URL uniqueness. It does not replace browser testing, Search Console review, accessibility audits or Core Web Vitals measurement.

## Monetization
Read [MONETIZATION.md](MONETIZATION.md) before enabling ads or affiliate links. No advertising publisher script or ads.txt entry is configured by default. Use only the exact code and seller record supplied by an approved provider.

## Privacy
Many image and text tools are designed to process data in the browser. The QR generator sends its input to a third-party QR service, and the background-removal feature loads a third-party library/model. See the [Privacy Policy](https://buytools.si/privacy/) for more detail.

## Deployment
The site is static and deploys through GitHub Pages. Configure the custom domain and HTTPS in repository Pages settings. Do not report a deployment as successful until the relevant GitHub Actions run and live site are verified.
