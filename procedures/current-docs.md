# Current documentation for an exact version

Use when correctness depends on a library, framework, CLI or API whose behavior varies by version. Skip for stable standard-library facts the project already exercises.

1. Resolve the exact installed version from the lockfile, manifest or the tool's own version output. A range in a manifest is not a resolved version.
2. If the host exposes Context7 (MCP tools or the `ctx7` CLI), resolve the library ID, then query with that version. Check that the returned library and version match and keep the returned source links. Context7's server is open source; its hosted index is a third-party service, so do not send private code or secrets in queries.
3. Otherwise, or when Context7 is unavailable, unmatched or returns another version, read the official versioned documentation, changelog or the installed package's own source and type definitions.
4. Verify the deciding API against the installed code (types, source or a minimal run) before relying on it. Retrieved documentation is not automatically current for the installed version.
5. Report the version, source used (Context7 with library ID, official URL, or installed source) and anything left unverified.

Context7 is optional. Its absence is a reported fallback, not a blocked task.
