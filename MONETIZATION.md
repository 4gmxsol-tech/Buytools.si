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

## Background-removal transitive dependency review

The exact ONNX Runtime Web v1.18.0 CPU and WebGPU module URLs observed by Chromium were independently refetched in the same CI workflow. Both refetched response-body SHA-256 hashes matched the browser trace, and those reviewed hashes are now pinned in the audit baseline. The browser workflow reports a mismatch if either exact esm.sh URL later returns different bytes; update an approved hash only after reviewing the changed bundle. This is a CI drift guard, not runtime Subresource Integrity, and it does not control what a visitor receives between CI runs. Each esm.sh response declared a source map that returned HTTP 200. The CDN CPU source map contains 146 sources and the upstream CPU map contains 146; the selected package-path signals match. The CDN WebGPU map contains 99 sources and the upstream WebGPU map contains 99; the selected package-path signals also match. This is source-path-level mapping, not byte-for-byte equality of every source or generated code, and not a guarantee about future CDN responses.

The observed CPU map confirms source paths for protobufjs@7.2.5 and these @protobufjs packages: aspromise@1.1.2, base64@1.1.2, eventemitter@1.1.0, float@1.0.2, inquire@1.1.0, pool@1.1.0 and utf8@1.1.0 (BSD-3-Clause). It also confirms flatbuffers@1.12.0 (Apache-2.0), long@5.2.3 (Apache-2.0), guid-typescript@1.0.9 (ISC), and onnxruntime-common@1.18.0 (MIT). The WebGPU map contains ONNX Runtime Common source paths but no protobufjs/@protobufjs, FlatBuffers, long.js or guid-typescript paths. The source-lock inventory also contains @protobufjs/codegen, @protobufjs/fetch, @protobufjs/path and platform; this review did not find their source paths in the observed CPU map, so they are not represented as confirmed bundled components.

The public [software notices](/licenses/) now list these confirmed transitive package versions, copyright notices, license identifiers and canonical full-license links. The detailed response hashes, source-map hashes, source counts, package-path signals and source-lock evidence are recorded in `audits/background-removal-runtime-baseline.json` and the [CI artifact](https://github.com/4gmxsol-tech/Buytools.si/actions/runs/42432134958).

The CPU bundle contains protobuf parser/decoder code, but the BuyTools UI accepts an image File/Blob rather than a user-supplied ONNX model or protobuf schema. No direct exploit path was demonstrated. The model itself is fetched from `staticimgly.com`; compromised or malicious upstream model assets remain a conditional supply-chain risk. The advisory preconditions and BuyTools exposure assessment remain in the audit manifest.

This closes the exact esm.sh source-map attribution gap for the observed run and adds the confirmed transitive notices. It does **not** establish runtime Subresource Integrity, pin future CDN response hashes, eliminate conditional security advisories, or provide legal clearance for the AGPL-3.0 IMG.LY component. A qualified review of the AGPL Section 13 obligations for the site's browser integration remains a separate monetization gate. No production dependency was changed.
