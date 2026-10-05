# Web accessibility

Specification: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), reviewed 2026-10-05. Verification method: [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing). Automated scans cover only some failures; passing axe does not establish WCAG conformance.

Use semantic landmarks, logical headings, labels, accessible names and meaningful links/buttons. Test keyboard access and visible focus, contrast, target size, error explanation and reading order. For the supported experience, assess applicable AA criteria including reflow and zoom. Check 320px or a documented minimum, phone/tablet/desktop, long text and non-hover controls. Reduced motion must leave content and controls usable. Avoid flashing hazards.

Include an axe scan and an agent/manual interaction checklist with actual results and gaps. A contrast or keyboard defect is actionable even if the page looks attractive. Record assistive-technology testing as unavailable if none occurred.
