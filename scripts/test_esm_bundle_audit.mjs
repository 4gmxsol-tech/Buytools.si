import assert from "node:assert/strict";
import test from "node:test";
import {
  auditEsmBundle,
  extractModuleSpecifiers,
  findSourceMapReference,
  sha256
} from "./esm_bundle_audit.mjs";

test("finds source maps declared by response headers", () => {
  const reference = findSourceMapReference("", { "SourceMap": "../maps/ort.map" }, "https://esm.sh/ort.mjs");
  assert.deepEqual(reference, {
    kind: "response-header",
    reference: "https://esm.sh/maps/ort.map"
  });
});

test("finds source maps declared by JavaScript comments", () => {
  const reference = findSourceMapReference("export {};\\n//# sourceMappingURL=ort.mjs.map", {}, "https://esm.sh/ort.mjs");
  assert.deepEqual(reference, {
    kind: "response-comment",
    reference: "https://esm.sh/ort.mjs.map"
  });
});

test("does not invent a declared source map when none is exposed", () => {
  assert.equal(findSourceMapReference("export const value = 1;", {}, "https://esm.sh/ort.mjs"), null);
});

test("extracts static and dynamic module specifiers", () => {
  const source = `
    import runtime from "./runtime.mjs";
    export { helper } from "../shared/helper.mjs";
    const lazy = await import("./lazy.mjs");
  `;
  assert.deepEqual(extractModuleSpecifiers(source), ["../shared/helper.mjs", "./lazy.mjs", "./runtime.mjs"]);
});

test("maps the exact esm.sh response hash and source-map paths", async () => {
  const moduleUrl = "https://esm.sh/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs";
  const mapUrl = "https://esm.sh/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs.map";
  const moduleBody = 'import "./runtime-common.mjs";\\n//# sourceMappingURL=onnxruntime-web.mjs.map';
  const moduleBytes = Buffer.from(moduleBody);
  const esmMap = JSON.stringify({
    file: "onnxruntime-web.mjs",
    sources: [
      "../../node_modules/protobufjs/src/reader.js",
      "../../node_modules/protobufjs/src/writer.js",
      "../../node_modules/@protobufjs/utf8/index.js"
    ]
  });
  const cpuMap = JSON.stringify({ sources: ["../../node_modules/protobufjs/src/reader.js"] });
  const webgpuMap = JSON.stringify({ sources: [] });
  const responses = new Map([
    [moduleUrl, new Response(moduleBytes, { status: 200, headers: { "content-type": "application/javascript" } })],
    [mapUrl, new Response(esmMap, { status: 200, headers: { "content-type": "application/json" } })],
    ["https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.min.js.map", new Response(cpuMap, { status: 200 })],
    ["https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.webgpu.min.js.map", new Response(webgpuMap, { status: 200 })]
  ]);
  const fetchImpl = async url => responses.get(String(url)) || new Response("not found", { status: 404 });
  const runtimeProvenance = {
    sourceCommit: "test",
    modules: [{
      name: "onnxruntime-web",
      requests: [{
        url: moduleUrl,
        status: 200,
        sha256: sha256(moduleBytes)
      }]
    }]
  };
  const baseline = {
    observedModules: [{
      name: "onnxruntime-web",
      modulePaths: ["/onnxruntime-web@1.18.0/es2022/onnxruntime-web.mjs"]
    }],
    upstreamBundleEvidence: {
      cpuSourceMapUrl: "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.min.js.map",
      webgpuSourceMapUrl: "https://unpkg.com/onnxruntime-web@1.18.0/dist/esm/ort.webgpu.min.js.map"
    }
  };
  const report = await auditEsmBundle({ runtimeProvenance, baseline, fetchImpl });
  assert.equal(report.summary.browserHashMatches, 1);
  assert.equal(report.modules[0].sourceMapAssociation, "declared-by-response-comment");
  assert.equal(report.modules[0].sourceMap.sourcePathSignals.protobufReader, true);
  assert.equal(report.modules[0].sourceMap.sourcePathSignals.protobufWriter, true);
  assert.equal(report.modules[0].sourceMap.sourcePathSignals.protobufUtf8, true);
  assert.deepEqual(report.modules[0].staticModuleSpecifiers, ["./runtime-common.mjs"]);
  assert.equal(report.upstreamSourceMaps.find(item => item.name === "cpu").sourcePathSignals.protobufReader, true);
});
