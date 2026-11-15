# BuyTools.si monetization readiness

## Current implementation (verified against Main on 2026-11-15)

Adsterra is integrated into the production build. The Pages workflow runs `scripts/inject_ads.py`, which adds the first-party consent engine `assets/buytools-ads.js` once to eligible HTML pages. The injector excludes the `privacy/`, `terms/` and `licenses/` directories.

The first-party engine creates one labelled advertising slot before the page footer when a footer exists. Its current placement rules are:

- The homepage and pages under `/guides/` use the configured Adsterra native placement.
- Other eligible pages, including tool pages, use one responsive banner placement.
- Banner dimensions are selected by viewport width: 320 × 50 below 520 px, 300 × 250 from 520 px to below 900 px, and 728 × 90 at 900 px or wider.

The ad-delivery scripts are **not** loaded merely because the first-party consent engine is present. The engine shows an advertising-preferences prompt when it has no stored choice. Selecting **Accept advertising** stores `accepted` under `buytools-ad-consent-v1` and mounts the ad slot, which then requests the Adsterra delivery code from `bicea.org`. Selecting **Reject** stores `rejected` and does not mount or request the ad slot. The choice is stored in browser local storage; the current site provides no in-page preference reset, so visitors can clear the saved choice using their browser's site-data controls.

The prompt is a named, non-modal region with an associated description; it is not a modal dialog and does not trap or move keyboard focus. This lightweight site preference gate is not a certification of legal compliance, and it is not a full consent-management platform or an IAB Transparency and Consent Framework implementation. Requirements depend on visitor jurisdictions, the provider's current configuration and the actual ad partners. Obtain qualified privacy/legal review and confirm the provider's requirements before claiming compliance or expanding ad technology.

The privacy policy at `/privacy/` identifies Adsterra, the `bicea.org` delivery host, the advertising preference key, the categories of technical data that the provider and its partners may process, and the distinction between advertising and site analytics. The site policy says no separate site-analytics platform is currently used. This does not mean the advertising provider performs no ad-delivery measurement after a visitor accepts.

No `ads.txt` file is currently present in the repository. Do not create one or publish seller/publisher identifiers unless the approved provider supplies the exact authoritative record. No revenue amount, RPM, approval status or delivery rate is asserted in this repository.

## Operational controls and next steps

1. Keep the ad engine consent-gated: no Adsterra delivery request before an explicit accept choice; a reject choice must continue to leave the ad slot unmounted.
2. Keep ads outside file pickers, upload/download controls, active tool workspaces and primary navigation. Do not add pop-ups, forced redirects or extra placements without a separate review and verified authorization.
3. Re-test the accept and reject paths on mobile and desktop after any change to the engine, provider tags, consent copy or injection rules. Check that the prompt remains keyboard-usable, the privacy link is reachable, and ad containers do not cause layout shifts or obscure controls.
4. Review provider approval, seller records, partner disclosures, consent requirements and geographic restrictions in the provider account before changing the integration. The public code and a successful CI deployment do not establish account approval or legal compliance.
5. Use Search Console for organic search evidence and the provider's own reporting for advertising delivery/revenue when that account data is available. Do not add separate analytics, tracking pixels or another third-party service without explicit authorization.
6. Keep `/privacy/` synchronized with actual runtime behavior and the providers' current terms. Re-test observed network requests; do not infer data handling solely from marketing descriptions.

## Third-party license review gate

The Background Removal feature loads `@imgly/background-removal@1.5.5`. The upstream project identifies this package as AGPL-3.0. AGPL-3.0 permits commercial use subject to its conditions; Section 13 includes source-availability obligations for certain modified versions used over a network. The legal effect of this site's browser integration has not been determined. Do not describe this feature as license-cleared for monetization or modify its integration until a qualified review confirms the applicable obligations, or an appropriate alternative license is obtained from IMG.LY. The public attribution notice is at `/licenses/`; keep it synchronized with the actual package version.

## Background-removal transitive dependency review

The exact ONNX Runtime Web v1.18.0 CPU and WebGPU module URLs observed by Chromium were independently refetched in the same CI workflow. Both refetched response-body SHA-256 hashes matched the browser trace, and those reviewed hashes are now pinned in the audit baseline. The browser workflow reports a mismatch if either exact esm.sh URL later returns different bytes; update an approved hash only after reviewing the changed bundle. This is a CI drift guard, not runtime Subresource Integrity, and it does not control what a visitor receives between CI runs. Each esm.sh response declared a source map that returned HTTP 200. The CDN CPU source map contains 146 sources and the upstream CPU map contains 146; the selected package-path signals match. The CDN WebGPU map contains 99 sources and the upstream WebGPU map contains 99; the selected package-path signals also match. This is source-path-level mapping, not byte-for-byte equality of every source or generated code, and not a guarantee about future CDN responses.

The observed CPU map confirms source paths for protobufjs@7.2.5 and these @protobufjs packages: aspromise@1.1.2, base64@1.1.2, eventemitter@1.1.0, float@1.0.2, inquire@1.1.0, pool@1.1.0 and utf8@1.1.0 (BSD-3-Clause). It also confirms flatbuffers@1.12.0 (Apache-2.0), long@5.2.3 (Apache-2.0), guid-typescript@1.0.9 (ISC), and onnxruntime-common@1.18.0 (MIT). The WebGPU map contains ONNX Runtime Common source paths but no protobufjs/@protobufjs, FlatBuffers, long.js or guid-typescript paths. The source-lock inventory also contains @protobufjs/codegen, @protobufjs/fetch, @protobufjs/path and platform; this review did not find their source paths in the observed CPU map, so they are not represented as confirmed bundled components.

The public [software notices](/licenses/) now list these confirmed transitive package versions, copyright notices, license identifiers and canonical full-license links. The detailed response hashes, source-map hashes, source counts, package-path signals and source-lock evidence are recorded in `audits/background-removal-runtime-baseline.json` and the [CI artifact](https://github.com/4gmxsol-tech/Buytools.si/actions/runs/42432134958).

The CPU bundle contains protobuf parser/decoder code, but the BuyTools UI accepts an image File/Blob rather than a user-supplied ONNX model or protobuf schema. No direct exploit path was demonstrated. The model itself is fetched from `staticimgly.com`; compromised or malicious upstream model assets remain a conditional supply-chain risk. The advisory preconditions and BuyTools exposure assessment remain in the audit manifest.

This closes the exact esm.sh source-map attribution gap for the observed run and adds the confirmed transitive notices. It does **not** establish runtime Subresource Integrity, pin future CDN response hashes, eliminate conditional security advisories, or provide legal clearance for the AGPL-3.0 IMG.LY component. A qualified review of the AGPL Section 13 obligations for the site's browser integration remains a separate monetization gate. No production dependency was changed.
