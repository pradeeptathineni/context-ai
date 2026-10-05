# React web implementation

Selected advisory source: pinned Vercel React best practices. Detect actual framework/version/runtime from manifests, lockfiles and code first. Read the [review procedure](../../procedures/react-review.md), then search the pinned compiled guide for the relevant headings. Individual rules remain available in the source checkout.

Use existing components and state boundaries. For React/Vite, browser data flow and effects differ from Next server components. Do not force Next adoption. For Next, identify App versus Pages Router and client/server boundaries; verify static export against the installed version before introducing server actions, SSR or image optimization. A frontend must not contain secrets.

Test meaningful runtime states, hydration and browser behavior with the real build. Measure before memoizing or moving work. Keep framework-specific prescriptions advisory when their assumptions do not match the project.
