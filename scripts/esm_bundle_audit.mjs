import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { pathToFileURL } from "node:url";

export function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function headerValue(headers, name) {
  if (headers && typeof headers.get === "function") return headers.get(name);
  const target = name.toLowerCase();
  const entry = Object.entries(headers || {}).find(([key]) => key.toLowerCase() === target);
  return entry ? String(entry[1]) : null;
}

export function findSourceMapReference(body, headers = {}, moduleUrl) {
  const headerReference = headerValue(headers, "sourcemap") || headerValue(headers, "x-sourcemap");
  if (headerReference) {
    return {
      kind: "response-header",
      reference: headerReference.startsWith("data:") ? headerReference : new URL(headerReference, moduleUrl).href
    };
  }

  const match = String(body).match(/(?:\/\/[#@]\s*sourceMappingURL=([^\s]+)|\/\*[#@]\s*sourceMappingURL=([^*]+?)\s*\*\/)/);
  const reference = match?.[1] || match?.[2]?.trim();
  if (!reference) return null;
  return {
    kind: "response-comment",
    reference: reference.startsWith("data:") ? reference : new URL(reference, moduleUrl).href
  };
}

export function extractModuleSpecifiers(source) {
  const found = new Set();
  const patterns = [
    /\b(?:import|export)\s+(?:[^'";]*?\s+from\s*)?["']([^"']+)["']/g,
    /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g
  ];
  for (const pattern of patterns) {
    for (const match of String(source).matchAll(pattern)) found.add(match[1]);
  }
  return [...found].sort();
}

function decodeDataMap(reference) {
  const comma = reference.indexOf(",");
  if (comma < 0) throw new Error("Malformed inline source map data URI.");
  const metadata = reference.slice(0, comma);
  const payload = reference.slice(comma + 1);
  return metadata.includes(";base64")
    ? Buffer.from(payload, "base64").toString("utf8")
    : decodeURIComponent(payload);
}

async function loadSourceMap(reference, fetchImpl) {
  if (reference.startsWith("data:")) {
    const text = decodeDataMap(reference);
    try {
      const map = JSON.parse(text);
      return {
        status: 200,
        responseUrl: "inline-data-uri",
        sha256: sha256(Buffer.from(text)),
        byteLength: Buffer.byteLength(text),
        file: map.file || null,
        sources: Array.isArray(map.sources) ? map.sources : [],
        parseError: null
      };
    } catch (error) {
      return { status: 200, responseUrl: "inline-data-uri", sha256: sha256(Buffer.from(text)), byteLength: Buffer.byteLength(text), file: null, sources: [], parseError: error.message };
    }
  }

  try {
    const response = await fetchImpl(reference, { headers: { accept: "application/json,*/*" } });
    if (!response.ok) return { status: response.status, responseUrl: response.url || reference, sha256: null, byteLength: 0, file: null, sources: [], parseError: null };
    const bytes = Buffer.from(await response.arrayBuffer());
    const text = bytes.toString("utf8");
    try {
      const map = JSON.parse(text);
      return {
        status: response.status,
        responseUrl: response.url || reference,
        sha256: sha256(bytes),
        byteLength: bytes.length,
        file: map.file || null,
        sources: Array.isArray(map.sources) ? map.sources.map(String) : [],
        parseError: null
      };
    } catch (error) {
      return { status: response.status, responseUrl: response.url || reference, sha256: sha256(bytes), byteLength: bytes.length, file: null, sources: [], parseError: error.message };
    }
  } catch (error) {
    return { status: null, responseUrl: reference, sha256: null, byteLength: 0, file: null, sources: [], parseError: error.message };
  }
}

function sourcePathSignals(sources) {
  const normalized = sources.map(source => String(source).replaceAll("\\", "/").toLowerCase());
  const has = fragment => normalized.some(source => source.includes(fragment));
  return {
    protobufReader: has("protobufjs/src/reader.js"),
    protobufWriter: has("protobufjs/src/writer.js"),
    protobufUtf8: has("@protobufjs/utf8/index.js"),
    flatbuffers: has("flatbuffers"),
    long: has("/long/") || has("long/index.js"),
    guidTypescript: has("guid-typescript"),
    onnxruntimeCommon: has("common/lib/")
  };
}

function sidecarCandidate(moduleUrl) {
  const url = new URL(moduleUrl);
  url.pathname += ".map";
  return url.href;
}

export async function auditEsmBundle({ runtimeProvenance, baseline, fetchImpl = fetch }) {
  const runtime = runtimeProvenance.modules?.find(module => module.name === "onnxruntime-web");
  assert.ok(runtime, "Runtime provenance must include onnxruntime-web.");
  const expectedModule = baseline.observedModules?.find(module => module.name === "onnxruntime-web");
  assert.ok(expectedModule?.modulePaths?.length, "Baseline must list expected ONNX Runtime module paths.");

  const requests = (runtime.requests || []).filter(request => {
    const url = new URL(request.url);
    return url.hostname === "esm.sh" && url.pathname.startsWith("/onnxruntime-web@1.18.0/");
  });
  const observedPaths = new Set(requests.map(request => new URL(request.url).pathname));
  const missingPaths = expectedModule.modulePaths.filter(path => !observedPaths.has(path));
  assert.deepEqual(missingPaths, [], "Runtime provenance must include both expected ONNX Runtime ESM entry paths.");
  assert.ok(requests.length >= expectedModule.modulePaths.length, "Expected CPU and WebGPU ONNX Runtime responses.");

  const modules = [];
  for (const request of requests) {
    const response = await fetchImpl(request.url, { headers: { accept: "*/*" } });
    if (!response.ok) throw new Error("Could not refetch observed esm.sh module (" + response.status + "): " + request.url);
    const bytes = Buffer.from(await response.arrayBuffer());
    const body = bytes.toString("utf8");
    const fetchedHash = sha256(bytes);
    const browserHash = request.sha256 || null;
    const reference = findSourceMapReference(body, response.headers, request.url);
    let sourceMap = null;
    let sourceMapAssociation = "not-exposed";

    if (reference) {
      sourceMap = await loadSourceMap(reference.reference, fetchImpl);
      sourceMapAssociation = reference.kind === "response-header" ? "declared-by-response-header" : "declared-by-response-comment";
    } else {
      const candidateUrl = sidecarCandidate(request.url);
      const candidate = await loadSourceMap(candidateUrl, fetchImpl);
      if (candidate.status === 200 && !candidate.parseError) {
        sourceMap = candidate;
        const moduleFile = basename(new URL(request.url).pathname);
        sourceMapAssociation = candidate.file && basename(candidate.file) === moduleFile
          ? "conventional-sidecar-file-match"
          : "unconfirmed-conventional-sidecar";
      } else {
        sourceMap = candidate;
      }
    }

    const headers = {};
    for (const name of ["content-type", "content-length", "etag", "last-modified", "source-map", "sourcemap", "x-sourcemap", "x-esm-path", "x-typescript-types", "cache-control"]) {
      const value = headerValue(response.headers, name);
      if (value !== null) headers[name] = value;
    }

    modules.push({
      url: request.url,
      responseUrl: response.url || request.url,
      status: response.status,
      contentType: headerValue(response.headers, "content-type"),
      responseBodyBytes: bytes.length,
      browserSha256: browserHash,
      refetchedSha256: fetchedHash,
      browserResponseHashMatchesRefetch: Boolean(browserHash && browserHash === fetchedHash),
      responseHeaders: headers,
      staticModuleSpecifiers: extractModuleSpecifiers(body),
      sourceMapReference: reference,
      sourceMapAssociation,
      sourceMap: sourceMap ? {
        status: sourceMap.status,
        responseUrl: sourceMap.responseUrl,
        sha256: sourceMap.sha256,
        byteLength: sourceMap.byteLength,
        file: sourceMap.file,
        sourceCount: sourceMap.sources.length,
        sourcePathSignals: sourcePathSignals(sourceMap.sources),
        sourcePaths: sourceMap.sources,
        parseError: sourceMap.parseError
      } : null
    });
  }

  const upstream = [];
  for (const [name, url] of [
    ["cpu", baseline.upstreamBundleEvidence?.cpuSourceMapUrl],
    ["webgpu", baseline.upstreamBundleEvidence?.webgpuSourceMapUrl]
  ]) {
    if (!url) continue;
    const map = await loadSourceMap(url, fetchImpl);
    upstream.push({
      name,
      url,
      status: map.status,
      sha256: map.sha256,
      byteLength: map.byteLength,
      file: map.file,
      sourceCount: map.sources.length,
      sourcePathSignals: sourcePathSignals(map.sources),
      sourcePaths: map.sources,
      parseError: map.parseError
    });
  }

  const hashMismatches = modules.filter(module => !module.browserResponseHashMatchesRefetch).map(module => module.url);
  const associatedMapsWithProtobuf = modules.filter(module =>
    ["declared-by-response-header", "declared-by-response-comment", "conventional-sidecar-file-match"].includes(module.sourceMapAssociation) &&
    module.sourceMap?.status === 200 &&
    !module.sourceMap?.parseError &&
    (module.sourceMap.sourcePathSignals.protobufReader || module.sourceMap.sourcePathSignals.protobufWriter || module.sourceMap.sourcePathSignals.protobufUtf8)
  );
  const report = {
    schemaVersion: 1,
    capturedAt: new Date().toISOString(),
    sourceCommit: runtimeProvenance.sourceCommit || null,
    workflowRunId: runtimeProvenance.workflowRunId || null,
    baselineFile: runtimeProvenance.baselineFile || "audits/background-removal-runtime-baseline.json",
    scope: "Refetches the exact esm.sh module URLs observed by Chromium, compares response-body SHA-256 values with the browser trace, inspects response-declared or conventional source maps, and compares their source paths with the pinned upstream ONNX Runtime maps. This is audit evidence, not runtime SRI.",
    modules,
    upstreamSourceMaps: upstream,
    summary: {
      observedOnnxRuntimeModuleResponses: modules.length,
      browserHashMatches: modules.length - hashMismatches.length,
      browserHashMismatches: hashMismatches.length,
      sourceMapsDeclaredByResponse: modules.filter(module => module.sourceMapAssociation.startsWith("declared-")).length,
      sourceMapsWithProtobufSources: associatedMapsWithProtobuf.length,
      upstreamCpuMapStatus: upstream.find(item => item.name === "cpu")?.status ?? null,
      upstreamWebgpuMapStatus: upstream.find(item => item.name === "webgpu")?.status ?? null,
      exactTransformedBundleMapping: associatedMapsWithProtobuf.length > 0
        ? "A response-associated esm.sh source map exposes protobuf-related source paths; compare the recorded paths with upstream evidence before treating package attribution as confirmed."
        : "Unresolved: no response-associated esm.sh source map exposed protobuf-related source paths in this run."
    },
    hashMismatches
  };
  return report;
}

async function main() {
  const runtimeProvenance = JSON.parse(await readFile(new URL("../runtime-provenance.json", import.meta.url), "utf8"));
  const baseline = JSON.parse(await readFile(new URL("../audits/background-removal-runtime-baseline.json", import.meta.url), "utf8"));
  const report = await auditEsmBundle({ runtimeProvenance, baseline });
  await writeFile(new URL("../esm-bundle-audit.json", import.meta.url), JSON.stringify(report, null, 2) + "\n");
  console.log("Exact esm.sh ONNX Runtime audit: " + JSON.stringify(report.summary, null, 2));
  if (report.hashMismatches.length) {
    throw new Error("The esm.sh module response differed from the Chromium-captured response hash; exact response identity is unresolved.");
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
