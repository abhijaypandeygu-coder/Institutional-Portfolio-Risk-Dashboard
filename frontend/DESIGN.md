---
version: alpha
name: FinSight Portfolio Workspace
description: Apple-inspired light financial workspace with a persistent sidebar, quiet surfaces, system typography and blue actions.
colors:
  canvas: "#f5f5f7"
  surface: "#ffffff"
  subtle: "#f0f0f2"
  hover: "#e9e9ed"
  line: "#e5e5ea"
  line-strong: "#d2d2d7"
  ink: "#1d1d1f"
  secondary: "#48484a"
  muted: "#6e6e73"
  brand: "#0066cc"
  brand-hover: "#0055b3"
  brand-soft: "#eaf2ff"
  positive: "#18743b"
  positive-soft: "#eaf5ed"
  negative: "#b4232c"
  negative-soft: "#fff0f1"
  warning: "#8a5100"
  warning-soft: "#fff6e7"
  info: "#6941a5"
  info-soft: "#f3edfb"
typography:
  sans:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
omitted:
  - section: spacing
    reason: Use the existing Tailwind scale rather than a bespoke token scale.
  - section: rounded
    reason: Use Tailwind radius utilities; do not infer a new named radius scale.
  - section: components
    reason: Shared components consume the named semantic color roles directly.
---

## Overview

FinSight is an Apple-inspired portfolio and risk workspace. The user's instruction on 19 November 2026 supersedes the previous dark slate-and-emerald direction. This is an independent web interface, not an Apple product or an exact recreation of a native Apple app.

The implementation authority is src/index.css, AppShell.tsx and the live dashboard consumers. These named roles replace dark-theme utility colors across the frontend. Preserve data connections, calculations, unavailable states and broker account separation.

## Colors

Use canvas for the page background and surface for cards and dialogs. Subtle and hover provide quiet control states; line and line-strong separate content without heavy shadows. Ink, secondary and muted establish text hierarchy. Brand is the blue action and selection color, with brand-hover and brand-soft states. Positive, negative and warning colors always accompany a sign, label or status. Do not use pale dark-theme text on light surfaces.

## Typography

Use the system sans stack. On Apple platforms it resolves to the platform font; on Windows use Segoe UI. Page headings are prominent semibold text; card headings are smaller semibold text; dense financial captions remain readable. Use tabular figures for prices, quantities, basis points and percentages. Do not add decorative tracking or mix font families for metadata.

## Layout

The desktop shell has a fixed 224px sidebar and a flexible workspace. At widths below 1024px, use the native navigation disclosure in the toolbar. Keep portfolio selection and search in the shared toolbar. The main content uses responsive margins, white analytical panels, and local overflow for wide tables. Primary analytical content precedes broker settings. Page navigation resets the scroll position.

## Elevation & Depth

Use tonal layers, fine separators and restrained borders. Reserve stronger elevation for dialogs and the mobile navigation popover. Avoid gradients, glow effects and large backdrop blurs.

## Shapes

Use restrained rounded controls and rounded cards from the Tailwind defaults. Keep control shape and padding consistent across Overview, Risk Alerts, Liquidity, Stress Testing and Data Feeds.

## Components

AppShell owns navigation, portfolio selection, search access and the responsive structure. Existing dashboard components retain their APIs. Export, order and search use the shared native modal surface for focus containment, Escape and focus restoration. Inputs need labels, errors need nearby text, and scenario choices must be keyboard-operable.

Stock identities use local company marks with monogram fallback. The holdings sparklines use adjusted daily closes and state unavailable history explicitly. Portfolio NAV, cash-flow-adjusted performance and benchmark history remain separately sourced and labeled. Benchmark normalization starts from the first observation, not the final NAV. TWR/MWR require complete archived performance records. Broker account panels remain separate from the selected local portfolio.

The development component canvas follows the same light theme and mounts only synthetic preview data. No additional theme selector is introduced.

## Do's and Don'ts

- Give financial content priority over decorative chrome.
- Use blue consistently for navigation selection and main actions; use green/red for financial direction.
- Keep charts, tables, forms, dialogs and provider diagnostics legible on light backgrounds.
- Preserve explicit loading, error and unavailable states; do not invent financial data for visual effect.
- Keep visible keyboard focus, native dialog behavior and reduced-motion support.
- Do not introduce continuous decorative animation or layout animation.
- Keep this private dashboard noindex until a public deployment is intentionally configured.

Design references: [Apple Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [Typography](https://developer.apple.com/design/human-interface-guidelines/typography), and [Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars). These inform hierarchy and navigation; exact web tokens are product implementation decisions.
