# @deep/theme

Portable, dependency-free theme presets and preference validation for browser or Node consumers. The package has no React or Deep runtime dependency.

```js
import { defaultPreference, resolveTheme, cssVariables } from "@deep/theme";

const theme = resolveTheme(
  defaultPreference,
  matchMedia("(prefers-color-scheme: dark)").matches,
);
document.documentElement.dataset.theme = theme.id;
document.documentElement.dataset.themeDensity = theme.tokens.density;
document.documentElement.style.colorScheme = theme.scheme;
for (const [name, value] of Object.entries(cssVariables(theme))) {
  document.documentElement.style.setProperty(name, value);
}
```

Version 1 preferences use `mode: "system"` or `mode: "preset"`, one of `neon1-dark`, `neon1-light`, `slate-dark`, `sand-light`, `forest-light`, or `matrix-dark`, and optional overrides for `brandAction`, `brandHover`, `brandPress`, `accent`, `focus`, `radius` (0–20 pixels), and `density` (`comfortable` or `compact`). System mode still chooses Neon 1 dark or light from the supplied system-dark flag. Forest Light and Matrix Dark are optional alternatives; they do not change the system choice or the default preference. Invalid, oversized, unknown-key, unsupported-version, or low-contrast values throw an actionable error during parsing. System preferences validate color overrides against both Neon 1 schemes so a later OS theme change remains safe. Color inputs use strict `#RRGGBB` notation.

`cssVariables()` returns semantic `--theme-*` names, the `--on-brand`, `--accent`, and `--chart-1` through `--chart-5` aliases, font stacks, and the legacy variables used by Deep styles, including the original `--neon1` action color `#2f7940`. Status warning, error, and unknown colors remain separate. Preferences contain no layout or application state.

Forest Light uses a soft green-tinted reading surface with near-black body text, a deep green action color, and a separate indigo focus ring. Matrix Dark uses near-black reading surfaces and green action controls; its bright green focus token is for a small focus ring, never body text or large fills. Its teal-green accent `#03a062` maintains at least 4.5:1 contrast on every dark surface. Across palettes, chart slots 1–5 are distinct; teal, blue and red series retain separate labels. Use series labels, point markers or line patterns along with chart colors. Status text, lifecycle, freshness, acceptance, cost qualifications and provenance remain application meanings rather than editable palette attributes.

The package is MIT licensed. This is the unreleased `1.0.0` candidate; keep it bundled with its included license and do not publish it until separately approved. No registry or running Deep service is required. Token names and preference version 1 are the compatibility boundary. Reject unknown preference versions instead of guessing a migration.

Browser adapters must listen for system preference changes while following the system, preserve explicit choices and catch storage failures. Each standalone owns its storage key and CSS mapping. Native controls inherit the resolved root `color-scheme`. Offset focus rings so they sit on the surrounding surface.

The packed [standalone browser example](examples/standalone.html) demonstrates that adapter with native controls, an example-specific storage key and local-only sample data. Serve the extracted package directory with a static HTTP server, then open `/examples/standalone.html`. It imports only this package's module and needs no Deep application or API. Opening it directly with `file://` may block the module import.
