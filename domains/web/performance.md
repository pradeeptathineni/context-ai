# Web performance and delivery

Source-supported guidance: [Web Vitals](https://web.dev/articles/vitals) and [Next static exports](https://nextjs.org/docs/app/guides/static-exports), reviewed 2026-10-05. The good field targets are LCP <=2.5s, INP <=200ms and CLS <=0.1 at the 75th percentile. Local lab scores do not establish deployed field performance; TBT is not INP.

Set a budget from the existing page and intended experience. Measure asset/JavaScript sizes, runtime interaction, layout stability and rendering work; justify increases. Prefer responsive assets, explicit image dimensions, appropriate font loading and minimal client work. Pause decorative animation offscreen/in hidden tabs and respect reduced motion.

Project policy may target mobile Lighthouse performance >=90 and accessibility/best-practices/SEO >=95 under stated conditions. Use repeated runs for noisy scores. Never remove essential content to game a metric. For a small fixture, a measured static asset budget and interaction checks can be the more discriminating recipe.

For S3/CloudFront verify the actual framework's static build: server-only features, images, forms/backend, deep links, case/path handling, trailing slashes, errors, cache policy and asset prefixes. A local build cannot establish AWS deployment. No deployment is authorized by this module.
