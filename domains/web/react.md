# React web implementation

Selected advisory source: pinned Vercel React best practices. Detect actual framework/version/runtime from manifests, lockfiles and code first. Read only relevant [rule files](../../sourced/vercel/react/rules/async-parallel.md); the [capability registry](../../capabilities.yaml) identifies all preserved rules.

Use existing components and state boundaries. For React/Vite, browser data flow and effects differ from Next server components. Do not force Next adoption. For Next, identify App versus Pages Router and client/server boundaries; verify static export against the installed version before introducing server actions, SSR or image optimization. A frontend must not contain secrets.

Test meaningful runtime states, hydration and browser behavior with the real build. Measure before memoizing or moving work. Keep framework-specific prescriptions advisory when their assumptions do not match the project.
