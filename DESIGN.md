# Design

## Design Direction

NCP-AAI is a restrained local study console. The physical scene is a focused evening study desk: browser on one side, notes and terminal nearby, low distraction, fast scanning, and clear evidence trails. Use a light interface for long reading and quiz sessions, with a botanical green accent reserved for active navigation, primary actions, and retrieval confidence.

## Color

Use OKLCH custom properties. The palette is restrained: pure white workspace, cool-neutral panels, deep green ink, and a single saturated green primary. Semantic colors are reserved for system status.

```css
--color-bg: oklch(1 0 0);
--color-surface: oklch(0.975 0.006 145);
--color-panel: oklch(0.946 0.01 145);
--color-border: oklch(0.875 0.014 145);
--color-ink: oklch(0.205 0.035 155);
--color-muted: oklch(0.435 0.026 155);
--color-subtle: oklch(0.62 0.022 155);
--color-primary: oklch(0.52 0.142 145);
--color-primary-strong: oklch(0.42 0.13 145);
--color-primary-soft: oklch(0.93 0.045 145);
--color-accent: oklch(0.5 0.12 235);
--color-accent-soft: oklch(0.935 0.035 235);
--color-success: oklch(0.48 0.13 145);
--color-warning: oklch(0.62 0.14 80);
--color-danger: oklch(0.54 0.16 28);
```

## Typography

Use `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Product typography uses a fixed rem scale: 12px meta labels, 14px body, 16px section headings, 20px page headings, 24px dashboard titles. Letter spacing is 0.

## Layout

Use a persistent app shell with a 248px sidebar, a 56px header, and a scrollable content region. Collapse navigation into a horizontal compact bar below 860px. Main content uses full-width bands and compact panels rather than nested decorative cards.

## Components

Buttons are 8px radius with clear default, hover, focus, active, disabled, and loading states. Use lucide icons for navigation and commands. Inputs, selects, and textareas share the same border, focus ring, and disabled treatment. Repeated data items may use 8px-radius cards with one border and no decorative shadow.

## States

Use skeleton rows for loading lists. Empty states should describe the next available action, not just absence. Errors should show what failed and expose retry where the action is recoverable. Disabled controls should include visible copy explaining the missing prerequisite.

## Motion

Keep motion to 150-200ms hover, focus, panel, and result transitions. No page-load choreography. Respect `prefers-reduced-motion: reduce` by removing transitions.
