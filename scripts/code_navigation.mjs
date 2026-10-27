// TypeScript LanguageService worker for scripts/code_navigation.py.
//
// One JSON request arrives on stdin and one bounded JSON reply leaves on stdout.
// The only code loaded from outside Node is the host-configured TypeScript file
// named in argv[2]. The service sees only the request's files: every host
// callback answers from that in-memory map under /project and never falls back
// to the real filesystem, the target's tsconfig, plugins or packages.

import { createRequire } from "node:module";
import { posix } from "node:path";

const PROTOCOL = 1;
const ROOT = "/project";
// noLib means this path is never loaded; it only satisfies a required host method
const NO_LIB = "/__context_no_lib__/lib.d.ts";
const MAX_INPUT_BYTES = 64 * 1024 * 1024;
const MAX_RESULTS = 200;
const MAX_SITES = 100;
const MAX_PREPARED = 50;
const MAX_DIAGNOSTICS = 40;
const MAX_STATIC_DIAGNOSTICS = 500;
const MAX_MESSAGE = 200;
const MAX_NAME = 1024;
const MAX_QUERY = 200;
const MATCH_RANK = { exact: 0, prefix: 1, substring: 2, camelCase: 3 };

class WorkerError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }
}

function clip(value, limit = MAX_MESSAGE) {
  const text = String(value);
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

// engine names for whole-file items embed the virtual root; callers see relative paths
function cleanName(value) {
  return clip(String(value ?? "").split(`${ROOT}/`).join(""), MAX_NAME);
}

function resolvePath(name) {
  return typeof name === "string" ? posix.resolve(ROOT, name) : "";
}

function compareText(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function isRelativePath(path) {
  return typeof path === "string" && path.length > 0 && !path.startsWith("/")
    && !path.includes("\0") && !path.includes("\\") && posix.normalize(path) === path
    && !path.split("/").some((part) => part === "" || part === "." || part === "..");
}

function isRelativeSpecifier(specifier) {
  return specifier === "." || specifier === ".." || specifier.startsWith("./") || specifier.startsWith("../");
}

function isCount(value, max) {
  return Number.isInteger(value) && value >= 1 && value <= max;
}

async function readRequest() {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_INPUT_BYTES) throw new WorkerError("invalid_request", "request exceeds the worker input limit");
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new WorkerError("invalid_request", "request is not JSON");
  }
}

function parseRequest(request) {
  if (!request || typeof request !== "object" || request.protocol !== PROTOCOL || !Array.isArray(request.files)) {
    throw new WorkerError("invalid_request", "unsupported request");
  }
  const files = new Map();
  const indexes = new Map();
  request.files.forEach((entry, index) => {
    if (!entry || typeof entry.text !== "string" || !isRelativePath(entry.path)) {
      throw new WorkerError("invalid_request", "request file entry is malformed");
    }
    const name = `${ROOT}/${entry.path}`;
    if (files.has(name)) throw new WorkerError("invalid_request", "request repeats a file");
    files.set(name, { path: entry.path, text: entry.text });
    indexes.set(entry.path, index);
  });
  if (!isCount(request.maxResults, MAX_RESULTS) || !isCount(request.maxSites, MAX_SITES)) {
    throw new WorkerError("invalid_request", "request limits are out of range");
  }
  if (request.operation === "search") {
    if (typeof request.query !== "string" || !request.query || request.query.length > MAX_QUERY) {
      throw new WorkerError("invalid_request", "search query is malformed");
    }
  } else if (request.operation === "inspect") {
    const position = request.position;
    const file = position && typeof position.file === "string" ? files.get(`${ROOT}/${position.file}`) : undefined;
    if (!file || !Number.isInteger(position.offset) || position.offset < 0 || position.offset > file.text.length) {
      throw new WorkerError("invalid_request", "inspect position is malformed");
    }
  } else if (request.operation === "diagnostics") {
    // Syntax-only diagnostics need no selector or project configuration.
  } else {
    throw new WorkerError("invalid_request", "unknown operation");
  }
  return { ...request, files, indexes };
}

function loadTypeScript(path) {
  if (typeof path !== "string" || !posix.isAbsolute(path)) {
    throw new WorkerError("engine_unavailable", "TypeScript path must be absolute");
  }
  let ts;
  try {
    ts = createRequire(import.meta.url)(path);
  } catch (error) {
    throw new WorkerError("engine_unavailable", `could not load TypeScript: ${clip(error?.code ?? error?.name ?? "error", 60)}`);
  }
  if (!ts || typeof ts.version !== "string" || !/^6\.\d+\.\d+/.test(ts.version)) {
    throw new WorkerError("engine_unsupported", `TypeScript 6.x is required; found ${clip(ts?.version, 40)}`);
  }
  const functions = [
    ts.createLanguageService, ts.createDocumentRegistry, ts.ScriptSnapshot?.fromString,
    ts.resolveModuleName, ts.getNameOfDeclaration, ts.forEachChild,
  ];
  const enums = [ts.ModuleResolutionKind?.Bundler, ts.ModuleKind?.ESNext, ts.ScriptTarget?.ESNext, ts.JsxEmit?.Preserve];
  if (functions.some((value) => typeof value !== "function") || enums.some((value) => value === undefined)) {
    throw new WorkerError("engine_unsupported", "TypeScript module lacks the expected LanguageService API");
  }
  return ts;
}

function createNotes() {
  const items = [];
  const seen = new Set();
  let total = 0;
  return {
    add(kind, message, key = `${kind}\0${message}`) {
      if (seen.has(key)) return;
      seen.add(key);
      total += 1;
      if (items.length < MAX_DIAGNOSTICS) items.push({ kind, message: clip(message) });
    },
    result: () => ({ items, total }),
  };
}

function createService(ts, files, notes) {
  const directories = new Map([["/", new Set()]]);
  for (const name of files.keys()) {
    let child = posix.dirname(name);
    if (!directories.has(child)) directories.set(child, new Set());
    while (child !== "/") {
      const parent = posix.dirname(child);
      if (!directories.has(parent)) directories.set(parent, new Set());
      directories.get(parent).add(posix.basename(child));
      child = parent;
    }
  }
  const snapshots = new Map();
  // fixed policy: project tsconfig is never read, so results do not depend on target config
  const options = {
    allowJs: true,
    checkJs: true,
    jsx: ts.JsxEmit.Preserve,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    noEmit: true,
    noLib: true,
    skipLibCheck: true,
    target: ts.ScriptTarget.ESNext,
    types: [],
  };
  const moduleHost = {
    fileExists: (name) => files.has(resolvePath(name)),
    readFile: (name) => files.get(resolvePath(name))?.text,
    directoryExists: (name) => directories.has(resolvePath(name)),
    getDirectories: (name) => [...(directories.get(resolvePath(name)) ?? [])].sort(),
    realpath: (name) => resolvePath(name),
    getCurrentDirectory: () => ROOT,
    useCaseSensitiveFileNames: true,
  };
  const unresolved = (containingFile, specifier, reason) => {
    const from = files.get(resolvePath(containingFile))?.path ?? "?";
    notes.add("unresolved_module", `${from} imports ${JSON.stringify(clip(specifier, 120))}: ${reason}`);
  };
  const host = {
    getCompilationSettings: () => options,
    getScriptFileNames: () => [...files.keys()],
    getScriptVersion: () => "1",
    getScriptSnapshot: (name) => {
      const key = resolvePath(name);
      const file = files.get(key);
      if (!file) return undefined;
      if (!snapshots.has(key)) snapshots.set(key, ts.ScriptSnapshot.fromString(file.text));
      return snapshots.get(key);
    },
    getCurrentDirectory: () => ROOT,
    getDefaultLibFileName: () => NO_LIB,
    fileExists: moduleHost.fileExists,
    readFile: moduleHost.readFile,
    directoryExists: moduleHost.directoryExists,
    getDirectories: moduleHost.getDirectories,
    readDirectory: () => [],
    realpath: moduleHost.realpath,
    useCaseSensitiveFileNames: () => true,
    // only relative specifiers resolve, and only to captured files; aliases and packages stay explicit
    resolveModuleNameLiterals: (literals, containingFile, redirectedReference, compilerOptions) => literals.map((literal) => {
      const specifier = literal.text;
      if (isRelativeSpecifier(specifier)) {
        const result = ts.resolveModuleName(specifier, containingFile, compilerOptions, moduleHost, undefined, redirectedReference);
        const target = result.resolvedModule && resolvePath(result.resolvedModule.resolvedFileName);
        if (target && files.has(target)) return result;
        unresolved(containingFile, specifier, "no captured file matches this relative import");
      } else {
        unresolved(containingFile, specifier, "non-relative imports are not resolved without project config or packages");
      }
      return { resolvedModule: undefined };
    }),
  };
  return ts.createLanguageService(host, ts.createDocumentRegistry(true, ROOT));
}

function spanOf(context, fileName, textSpan) {
  const file = context.request.files.get(resolvePath(fileName));
  if (!file || !textSpan) {
    context.notes.add("outside_snapshot", "the engine returned a location outside the captured files; it was omitted");
    return undefined;
  }
  return { file: file.path, start: textSpan.start, length: textSpan.length };
}

function spanKey(span) {
  return `${span.file}\0${span.start}\0${span.length}`;
}

function compareSpans(indexes, left, right) {
  return indexes.get(left.file) - indexes.get(right.file) || left.start - right.start || left.length - right.length;
}

function limit(rows, compare, max) {
  const sorted = [...rows].sort(compare);
  return { items: sorted.slice(0, max), total: sorted.length };
}

// navigate-to spans cover whole declarations; selectors need the name token
function nameSpan(ts, sourceFile, span) {
  const start = span.start;
  const end = span.start + span.length;
  let found;
  const visit = (node) => {
    if (found || node.pos > start || node.end < end) return;
    if (node.end === end && node.getStart(sourceFile) === start) {
      const name = ts.getNameOfDeclaration(node);
      if (name) {
        found = name;
        return;
      }
    }
    ts.forEachChild(node, visit);
  };
  ts.forEachChild(sourceFile, visit);
  if (!found) return span;
  const nameStart = found.getStart(sourceFile);
  return { file: span.file, start: nameStart, length: found.end - nameStart };
}

function search(context) {
  const { ts, service, program, request } = context;
  const rows = new Map();
  for (const item of service.getNavigateToItems(request.query, undefined, undefined, false, false)) {
    const declared = spanOf(context, item.fileName, item.textSpan);
    if (!declared) continue;
    const sourceFile = program.getSourceFile(`${ROOT}/${declared.file}`);
    const span = sourceFile ? nameSpan(ts, sourceFile, declared) : declared;
    const matchKind = Object.prototype.hasOwnProperty.call(MATCH_RANK, item.matchKind) ? item.matchKind : "camelCase";
    const symbol = {
      name: cleanName(item.name),
      kind: String(item.kind ?? ""),
      container: cleanName(item.containerName ?? ""),
      matchKind,
      span,
    };
    const key = `${spanKey(span)}\0${symbol.name}\0${symbol.kind}`;
    if (!rows.has(key)) rows.set(key, symbol);
  }
  const ordered = limit(rows.values(), (left, right) => MATCH_RANK[left.matchKind] - MATCH_RANK[right.matchKind]
    || compareText(left.name, right.name) || compareSpans(request.indexes, left.span, right.span)
    || compareText(left.kind, right.kind), request.maxResults);
  return { symbols: ordered.items, total: ordered.total };
}

function addCall(context, calls, item, fromSpans, siteFile) {
  const span = spanOf(context, item.file, item.selectionSpan);
  if (!span) return;
  const name = cleanName(item.name);
  const kind = String(item.kind ?? "");
  const key = `${spanKey(span)}\0${name}\0${kind}`;
  if (!calls.has(key)) calls.set(key, { name, kind, span, sites: new Map() });
  const sites = calls.get(key).sites;
  for (const textSpan of fromSpans ?? []) {
    const site = spanOf(context, siteFile, textSpan);
    if (site) sites.set(spanKey(site), site);
  }
}

function finishCalls(context, calls) {
  const { indexes, maxResults, maxSites } = context.request;
  const rows = [...calls.values()].map((call) => {
    const sites = [...call.sites.values()].sort((left, right) => compareSpans(indexes, left, right));
    return { name: call.name, kind: call.kind, span: call.span, sites: sites.slice(0, maxSites), siteTotal: sites.length };
  });
  return limit(rows, (left, right) => compareSpans(indexes, left.span, right.span)
    || compareText(left.name, right.name) || compareText(left.kind, right.kind), maxResults);
}

function inspect(context) {
  const { service, request } = context;
  const fileName = `${ROOT}/${request.position.file}`;
  const position = request.position.offset;
  const bySpan = (left, right) => compareSpans(request.indexes, left.span, right.span);

  const definitions = new Map();
  for (const definition of service.getDefinitionAtPosition(fileName, position) ?? []) {
    const span = spanOf(context, definition.fileName, definition.textSpan);
    if (!span) continue;
    const row = { name: cleanName(definition.name), kind: String(definition.kind ?? ""), span };
    definitions.set(`${spanKey(span)}\0${row.name}\0${row.kind}`, row);
  }

  // findReferences groups renamed imports separately; flattening keeps the engine's alias links
  const references = new Map();
  for (const group of service.findReferences(fileName, position) ?? []) {
    for (const entry of group.references) {
      const span = spanOf(context, entry.fileName, entry.textSpan);
      if (!span) continue;
      const previous = references.get(spanKey(span));
      references.set(spanKey(span), {
        span,
        isDefinition: Boolean(entry.isDefinition) || Boolean(previous?.isDefinition),
        isWriteAccess: Boolean(entry.isWriteAccess) || Boolean(previous?.isWriteAccess),
      });
    }
  }

  const prepared = service.prepareCallHierarchy(fileName, position);
  const items = prepared === undefined ? [] : Array.isArray(prepared) ? prepared : [prepared];
  const preparedSpans = new Map();
  const incoming = new Map();
  const outgoing = new Map();
  for (const item of items) {
    const span = spanOf(context, item.file, item.selectionSpan);
    if (span) preparedSpans.set(spanKey(span), span);
    const at = item.selectionSpan.start;
    for (const call of service.provideCallHierarchyIncomingCalls(item.file, at)) {
      addCall(context, incoming, call.from, call.fromSpans, call.from.file);
    }
    for (const call of service.provideCallHierarchyOutgoingCalls(item.file, at)) {
      addCall(context, outgoing, call.to, call.fromSpans, item.file);
    }
  }

  return {
    definitions: limit(definitions.values(), (left, right) => bySpan(left, right)
      || compareText(left.name, right.name) || compareText(left.kind, right.kind), request.maxResults),
    references: limit(references.values(), bySpan, request.maxResults),
    incoming: finishCalls(context, incoming),
    outgoing: finishCalls(context, outgoing),
    prepared: [...preparedSpans.values()].sort((left, right) => compareSpans(request.indexes, left, right)).slice(0, MAX_PREPARED),
  };
}

function run(ts, request) {
  const notes = createNotes();
  const service = createService(ts, request.files, notes);
  try {
    const program = service.getProgram();
    if (!program) throw new WorkerError("engine_failed", "TypeScript did not create a program");
    const syntaxFiles = [];
    let syntaxTotal = 0;
    for (const file of request.files.values()) {
      const sourceFile = program.getSourceFile(`${ROOT}/${file.path}`);
      if (!sourceFile) {
        notes.add("source_not_loaded", `${file.path} was not loaded by TypeScript`);
        if (request.operation === "diagnostics") syntaxFiles.push({ path: file.path, total: 0, diagnostics: [], loaded: false });
        continue;
      }
      const diagnostics = program.getSyntacticDiagnostics(sourceFile);
      if (diagnostics.length) notes.add("syntax", `${file.path}: ${diagnostics.length} syntax diagnostic(s); results in this file may be incomplete`);
      if (request.operation === "diagnostics") {
        const rows = [];
        for (const diagnostic of diagnostics) {
          syntaxTotal += 1;
          if (syntaxTotal <= MAX_STATIC_DIAGNOSTICS) {
            const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ").replace(/[\r\n\t ]+/g, " ").trim();
            const category = diagnostic.category;
            const severity = category === ts.DiagnosticCategory.Error ? "error"
              : category === ts.DiagnosticCategory.Warning ? "warning"
                : category === ts.DiagnosticCategory.Suggestion ? "suggestion" : "info";
            rows.push({
              code: `TS${diagnostic.code}`,
              severity,
              message: clip(message),
              start: Number.isInteger(diagnostic.start) ? diagnostic.start : null,
              length: Number.isInteger(diagnostic.length) ? diagnostic.length : null,
            });
          }
        }
        syntaxFiles.push({ path: file.path, total: diagnostics.length, diagnostics: rows, loaded: true });
      }
    }
    const context = { ts, service, program, request, notes };
    const result = request.operation === "search" ? search(context)
      : request.operation === "inspect" ? inspect(context)
        : { files: syntaxFiles, diagnosticTotal: syntaxTotal, omittedDiagnostics: Math.max(0, syntaxTotal - MAX_STATIC_DIAGNOSTICS) };
    const { items, total } = notes.result();
    return { diagnostics: items, diagnosticTotal: total, result };
  } finally {
    service.dispose();
  }
}

async function main() {
  let reply;
  try {
    const request = parseRequest(await readRequest());
    const ts = loadTypeScript(process.argv[2]);
    reply = { ok: true, protocol: PROTOCOL, engine: { name: "typescript", version: ts.version }, ...run(ts, request) };
  } catch (error) {
    const kind = error instanceof WorkerError ? error.kind : "engine_failed";
    reply = { ok: false, protocol: PROTOCOL, error: { kind, message: clip(error?.message ?? error) } };
    process.exitCode = 1;
  }
  // no process.exit: macOS pipes are asynchronous and a forced exit can truncate the reply
  process.stdout.write(JSON.stringify(reply));
}

main();
