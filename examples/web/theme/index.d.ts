export type Scheme = "dark" | "light";
export type Density = "comfortable" | "compact";
export interface ThemeTokens {
  surfaceCanvas: string;
  surfacePanel: string;
  surfaceRaised: string;
  surfaceInset: string;
  textPrimary: string;
  textMuted: string;
  textFaint: string;
  border: string;
  borderStrong: string;
  brandAction: string;
  brandHover: string;
  brandPress: string;
  onBrand: string;
  accent: string;
  focus: string;
  statusWarning: string;
  statusError: string;
  statusUnknown: string;
  chart1: string;
  chart2: string;
  chart3: string;
  chart4: string;
  chart5: string;
  radius: number;
  density: Density;
}
export interface ThemePreset {
  id: string;
  label: string;
  scheme: Scheme;
  tokens: ThemeTokens;
}
export interface ThemePreference {
  version: 1;
  mode: "system" | "preset";
  preset:
    | "neon1-dark"
    | "neon1-light"
    | "slate-dark"
    | "sand-light"
    | "forest-light"
    | "matrix-dark";
  overrides: Partial<
    Pick<
      ThemeTokens,
      | "brandAction"
      | "brandHover"
      | "brandPress"
      | "accent"
      | "focus"
      | "radius"
      | "density"
    >
  >;
}
export interface ResolvedTheme {
  id: string;
  label: string;
  scheme: Scheme;
  tokens: ThemeTokens;
}
export const presets: ThemePreset[];
export const defaultPreference: Readonly<ThemePreference>;
export function parsePreference(input: unknown): ThemePreference;
export function resolveTheme(
  preference?: unknown,
  darkSystem?: boolean,
): ResolvedTheme;
export function contrastRatio(foreground: string, background: string): number;
export function cssVariables(theme: ResolvedTheme): Record<string, string>;
