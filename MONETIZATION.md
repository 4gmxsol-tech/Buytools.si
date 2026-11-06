# BuyTools.si monetization readiness

## Current state
No advertising network is wired into the site by this change. Do not publish a fake publisher ID, fake ads.txt record, or unverified ad script. Add the actual provider code only after the account is approved and the official snippet is available.

## Recommended revenue sequence
1. Build search traffic around genuinely useful tools and focused guides; review Search Console queries and landing-page performance.
2. Improve completion rate and repeat use before adding intrusive placements.
3. Start with one responsive display placement after the tool directory or between editorial sections. Keep ads away from file-picker buttons, download links, and form controls.
4. Test on narrow mobile screens and desktop. Avoid forced redirects, deceptive download buttons, excessive pop-ups, and ad density that harms usability.
5. If affiliate links are introduced, use relevant products only and disclose the commercial relationship next to the recommendation.
6. Publish accurate privacy and terms information before enabling ad technology. Name the real advertising provider, describe its cookie/data practices, and add a consent mechanism when required for the audience and jurisdiction.
7. Add ads.txt only with the exact line supplied by the approved advertising provider. Never guess the publisher ID or seller record.

## Third-party license review gate

The Background Removal feature loads `@imgly/background-removal@1.5.5`. The upstream project identifies this package as AGPL-3.0. AGPL-3.0 permits commercial use subject to its conditions; Section 13 includes source-availability obligations for certain modified versions used over a network. The legal effect of this site's browser integration has not been determined. Do not describe this feature as license-cleared for monetization or modify its integration until a qualified review confirms the applicable obligations, or an appropriate alternative license is obtained from IMG.LY. The public attribution notice is at `/licenses/`; keep it synchronized with the actual package version.

## Suggested placement plan
- Primary placement: after the searchable tool grid, not inside the active tool workspace.
- Optional second placement: after a substantial how-to guide, only if the page has enough content and the ad does not interrupt the instructions.
- Do not load ad scripts on every tool action or insert ads between upload and download controls.

## Measure before scaling
Track impressions, viewability, page RPM, revenue per session, tool completion, search clicks, Core Web Vitals and bounce/engagement indicators where legally permitted. Compare pages and devices before adding another placement. Revenue and traffic are not guaranteed; ad networks may reject sites that lack sufficient original content, clear policies, or quality traffic.
