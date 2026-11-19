# Apple-inspired UI remake — 19 November 2026

## Design language
The user requested a whole-interface Apple-inspired remake, superseding the previous dark theme. Shared roles now define a light canvas, white surfaces, dark text, restrained separators, blue actions and semantic financial colors. System typography, a fixed desktop sidebar, responsive toolbar/navigation and reduced visual noise establish the hierarchy. DESIGN.md is the governing specification.

## Scope
AppShell owns the five-view navigation, portfolio selector, quick search and responsive structure. Overview, Risk Alerts, Liquidity, Stress Testing, Data Feeds, shared cards, reporting components and dialogs were migrated from dark utility colors to shared light-theme roles. Backend code and provider credentials were not changed in this redesign.

## Findings and correction
| Problem | Evidence | Correction | Confidence |
|---|---|---|---|
| Dark utility colors were repeated across dashboard consumers and dialogs | Source imports from App and shared components | Named semantic colors in index.css, applied across the frontend | High |
| Navigation and operational broker setup competed with primary information | Shared header and UpstoxBrokerPanel placement | Sidebar/toolbar shell; broker controls follow analytical content | High |
| Light-theme contrast and mobile widths needed correction | Rendered forms, financial statuses, Risk Alerts filter at 390px | Dark semantic text, readable status colors, bounded select and native dialog widths | High |

## Validation
- npm run build (TypeScript): passed.
- Vite production bundle: passed, 2219 modules transformed. Existing config-loader warning remains; it does not fail the build.
- Desktop: inspected Overview, Risk Alerts, Liquidity, Stress Testing and Data Feeds. Tested their shared navigation; selected scenario data renders in Stress Testing.
- Mobile 390x844: all five main views fit the document viewport after fixing the Risk Alerts portfolio selector. The scrollbar-excluded document width is 375px. Mobile menu opens, navigates and closes on selection.
- Native Export dialog closes with Escape and restores focus to Export. Search focuses its named input; mobile dialog width is about 343px. Order dialog opens with associated field labels. No order was submitted.
- Company logos loaded successfully and three one-month stock sparklines remained mounted with recorded data.
- DESIGN.md CLI lint: zero errors, one warning because the product uses the established `brand` name rather than `primary`. Tailwind export emits all 20 colors and the sans typography token. Previous/current diff reviewed.

## Limits
This is a frontend redesign and targeted browser review, not a new audit of backend calculations, feed freshness, provider authorization or every nested analytics workflow. External provider operations were not reauthorized during this pass. No trades, sign-offs, alert state changes or broker monitoring actions were submitted. Real touch devices and a screen reader were not tested. Existing canvas gesture limitations from the earlier UI review remain.

## Proof
Screenshots are saved in the Codex task outputs folder: apple-inspired-overview.jpg, apple-inspired-holdings.jpg and apple-inspired-mobile.jpg.
