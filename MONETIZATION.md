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

The upstream [ONNX Runtime Web v1.18.0 package lockfile](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.18.0/js/web/package-lock.json) resolves the remaining source dependency records, including protobufjs@7.2.5 and @protobufjs/utf8@1.1.0. The audit manifest records their exact versions, npm tarball integrity values and package license identifiers. guid-typescript@1.0.9 is ISC; FlatBuffers and long.js are Apache-2.0; ONNX Runtime Common and platform.js are MIT; protobufjs and its @protobufjs/* helpers are BSD-3-Clause.

The upstream ONNX Runtime Web v1.18.0 package manifest maps the browser ESM root export to `./dist/esm/ort.min.js` and the `./webgpu` export to `./dist/esm/ort.webgpu.min.js`. Its CPU ESM source map lists protobufjs reader/writer code and `@protobufjs` helper modules, including `@protobufjs/utf8`; it also lists FlatBuffers, long.js, guid-typescript and ONNX Runtime common source. The inspected WebGPU source map contains no `node_modules/protobufjs/` or `node_modules/@protobufjs/` source paths. The exact versions and SPDX license identifiers are recorded in `audits/background-removal-runtime-baseline.json`.

This is upstream source-map evidence for the package's published ESM exports. BuyTools CI records SHA-256 hashes for the observed esm.sh module responses, but this audit has not compared those transformed response bytes with the upstream UNPKG files; no byte-for-byte identity or runtime Subresource Integrity is claimed. The inspected source map does not list separate source paths for `@protobufjs/codegen`, `@protobufjs/fetch`, `@protobufjs/path` or `platform`, so their inclusion in this CPU bundle is not established by this review.

The CPU bundle contains protobuf parser/decoder code used by the ONNX Runtime model path. The BuyTools UI accepts an image File/Blob rather than a user-supplied ONNX model or protobuf schema, and no direct exploit path was demonstrated. The model itself is fetched from `staticimgly.com`; a compromised or malicious upstream model asset remains a conditional supply-chain input risk. The advisory preconditions and affected versions are recorded in the audit manifest and should not be described as a confirmed remote exploit in BuyTools.

The public software-notice page currently identifies direct runtime-observed modules but does not yet contain complete versioned copyright/license notices for every source-mapped transitive package. Treat this as an unresolved attribution and monetization gate. No production dependency was changed. The next steps are to verify the exact esm.sh transformation and add complete notices for the confirmed bundled components before evaluating a patched ONNX Runtime/protobuf chain. This review is not legal clearance or a claim that the feature is vulnerability-free.