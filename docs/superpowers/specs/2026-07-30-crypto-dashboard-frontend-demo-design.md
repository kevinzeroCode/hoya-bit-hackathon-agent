# HOYA BIT Static Frontend Demo Design

**Date:** 2026-07-30  
**Status:** Approved for specification review

## Purpose

Create a simple, presentation-ready frontend mockup that demonstrates how a
professional cryptocurrency research dashboard could look. The mockup is for a
short classroom presentation and does not need working analysis, live prices,
external APIs, or backend services.

## Deliverable

The demo will live in a self-contained `frontend-demo/` directory:

- `index.html` contains the page structure and all visible copy.
- `styles.css` contains the design tokens, layout, chart styling, responsive
  behavior, and interaction states.

The page must open directly from `index.html` without installing dependencies,
running a build process, or starting a local server. No JavaScript is required.

## Visual Direction

Use a professional research-terminal aesthetic rather than a neon or gaming
style:

- Deep navy background with slightly lighter panels.
- Off-white primary text and muted blue-gray secondary text.
- Cyan as the main interface accent.
- Green and amber used sparingly for market state and risk communication.
- Clear typography, restrained borders, subtle shadows, and moderate
  information density.
- No decorative crypto coins, glowing gradients, glassmorphism, or excessive
  animation.

The interface language is Traditional Chinese, with familiar market terms such
as BTC, USD, Volume, Evidence, and AI retained where that improves clarity.

## Page Structure

The single page contains:

1. **Header**
   - HOYA BIT wordmark.
   - Product label: `AI Crypto Market Intelligence`.
   - Visible `OFFLINE DEMO` status badge.
   - Data timestamp so the mock data cannot be mistaken for a live quote.

2. **Market summary**
   - BTC/USD pair label.
   - Mock current price and percentage change.
   - Three supporting metrics: 24-hour high, 24-hour low, and volume.

3. **Market chart**
   - A polished static line/area chart built with inline SVG.
   - Time labels, value labels, grid lines, and a highlighted latest data point.
   - A concise caption stating that the values are presentation data.

4. **AI research summary**
   - A direct market observation.
   - Three short evidence-backed observations.
   - A medium-confidence indicator.
   - A clear research-only disclaimer.

5. **Risk panel**
   - Volatility, momentum reversal, and data-timeliness risks.
   - Amber styling to distinguish caution from positive or negative price
     movement.

6. **Evidence sources**
   - Three mock source rows showing source type, description, reliability, and
     timestamp.
   - Each source is visibly labeled as demo content.

7. **Footer**
   - `僅供研究與課堂展示，不構成投資建議`.
   - Static demo version label.

## Responsive Behavior

- Desktop widths use a two-column dashboard with the chart occupying the wider
  column.
- Tablet widths collapse secondary panels below the chart while preserving
  hierarchy.
- Mobile widths use one column, smaller type, and horizontally scrollable metric
  groups only when necessary.
- The page must remain readable at 375 px, 768 px, and 1440 px viewport widths.

## Accessibility

- Text and important controls must meet WCAG AA contrast expectations.
- Price direction must use both text/symbols and color, never color alone.
- Semantic HTML headings and landmarks must preserve reading order.
- The static chart includes an accessible text alternative summarizing its
  meaning.
- Motion is limited to optional CSS hover transitions and respects
  `prefers-reduced-motion`.

## Data and Behavior

All values are hard-coded mock presentation data. The page has no network
requests, form submissions, working filters, authentication, storage, or AI
execution. Elements that resemble controls must either be presented as static
labels or have clearly non-functional demo treatment.

## Verification

Implementation is accepted when:

- `index.html` opens directly and renders without missing local assets.
- Browser developer tools show no page-load errors.
- No external network request is needed to render the page.
- The main regions remain readable at 375 px, 768 px, and 1440 px.
- All market values and sources are visibly identified as offline demonstration
  data.
- An HTML validation or equivalent structural check reports no material errors.
- A visual inspection confirms that the result matches the approved professional
  research-terminal direction.

## Out of Scope

- Real CSV ingestion.
- Live cryptocurrency prices.
- Bedrock or other AI model calls.
- Interactive charts, filters, tabs, or asset selection.
- Order entry, wallets, portfolio management, or trading features.
- Deployment or hosting.
