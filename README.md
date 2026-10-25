# BuyTools.si

Free, browser-based utilities for everyday PDF, image, text, developer and productivity tasks.

## Current prototype
- Responsive landing page with searchable tool directory and category filters
- Image conversion (PNG/JPEG/WebP), resizing and JPEG compression
- Images-to-PDF and text-to-PDF prototypes
- Word counter, case converter, whitespace cleaner
- JSON formatter/minifier, Base64 encoder/decoder
- QR code generation
- SEO basics: page title, description, canonical URL, Open Graph metadata, and structured data

## Run locally
Open `index.html` in a modern browser, or serve the repository with any static web server.

## Roadmap
1. Integrate and test real AI background removal.
2. Add reliable PDF merge, split, compress and image export workflows.
3. Add automated tests, accessibility checks, sitemap and Search Console verification.
4. Review privacy, third-party dependencies, and deployment settings before production promotion.

## Privacy
Image conversion and text utilities are designed to process files locally in the browser. The QR generator currently uses a third-party QR image endpoint, so its input is sent to that provider. Do not submit sensitive information to the QR tool.

## Deployment
This is a static site and can be deployed using GitHub Pages or another static hosting provider. Configure the custom domain and HTTPS in the repository's Pages settings.