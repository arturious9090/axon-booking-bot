---
name: Axon · Admin and existing demo
description: Restrained, clear scheduling administration; preserved public demonstration identity.
colors:
  admin-primary: '#36533b'
  admin-primary-hover: '#29432e'
  admin-link-hover: '#243e29'
  admin-paper: '#f6f7f3'
  admin-surface: '#ffffff'
  admin-ink: '#26332a'
  admin-secondary-text: '#526157'
  admin-muted: '#647164'
  admin-line: '#d9e0d5'
  admin-hairline: '#e5e9e1'
  admin-input-line: '#cbd5c5'
  admin-accent-soft: '#e8efdf'
  admin-selected: '#edf2e8'
  admin-nav-selected: '#dfe9d5'
  admin-nav-selected-ink: '#2c492f'
  admin-sidebar: '#f0f3ec'
  admin-focus: '#54783d'
  admin-danger: '#a13632'
  admin-danger-hover: '#852a27'
  admin-inactive: '#f0f1ed'
  admin-cancelled: '#f1f2ef'
  admin-absence: '#fff3da'
  admin-absence-ink: '#74551b'
  landing-paper: '#f6f5f0'
  landing-ink: '#20291f'
  landing-muted: '#697163'
  landing-line: '#dddfd4'
  landing-green: '#d9ed9a'
  landing-dark: '#2d3d29'
typography:
  admin-headline:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -.025em
  admin-title:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 16px
    fontWeight: 600
  admin-body:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 14px
    lineHeight: 1.55
  admin-field:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 13px
  admin-label:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 12px
    fontWeight: 600
  admin-status:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
    fontSize: 11px
    fontWeight: 500
  landing-display:
    fontFamily: '''Manrope'', system-ui, sans-serif'
    fontSize: clamp(40px, 4.8vw, 66px)
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: -.03em
  landing-body:
    fontFamily: '''Manrope'', system-ui, sans-serif'
    fontSize: 15px
    lineHeight: 1.6
  landing-brand:
    fontFamily: '''DM Sans'', sans-serif'
    fontSize: 32px
    fontWeight: 700
    letterSpacing: -2px
rounded:
  status: 5px
  field: 6px
  button: 7px
  nav: 8px
  module: 10px
  surface: 12px
  login: 14px
spacing:
  '6': 6px
  '8': 8px
  '10': 10px
  '12': 12px
  '14': 14px
  '16': 16px
  '18': 18px
  '20': 20px
  '22': 22px
  '24': 24px
  '28': 28px
  '32': 32px
  '36': 36px
components:
  admin-button-primary:
    backgroundColor: '{colors.admin-primary}'
    textColor: '{colors.admin-surface}'
    typography: '{typography.admin-label}'
    rounded: '{rounded.button}'
    padding: 8px 15px
  admin-button-primary-hover:
    backgroundColor: '{colors.admin-primary-hover}'
  admin-button-secondary:
    backgroundColor: '{colors.admin-surface}'
    textColor: '{colors.admin-primary}'
    typography: '{typography.admin-label}'
    rounded: '{rounded.button}'
    padding: 8px 15px
  admin-button-quiet:
    backgroundColor: transparent
    textColor: '{colors.admin-primary}'
    rounded: '{rounded.button}'
    padding: 8px 15px
  admin-button-danger:
    backgroundColor: '{colors.admin-danger}'
    textColor: '{colors.admin-surface}'
    rounded: '{rounded.button}'
    padding: 8px 15px
  admin-field:
    backgroundColor: '{colors.admin-surface}'
    textColor: '{colors.admin-ink}'
    typography: '{typography.admin-field}'
    rounded: '{rounded.field}'
    padding: 9px 11px
  admin-navigation:
    textColor: '{colors.admin-secondary-text}'
    rounded: '{rounded.nav}'
    padding: 11px 13px
  admin-status:
    backgroundColor: '{colors.admin-accent-soft}'
    textColor: '{colors.admin-primary}'
    typography: '{typography.admin-status}'
    rounded: '{rounded.status}'
    padding: 3px 8px
  admin-panel:
    backgroundColor: '{colors.admin-surface}'
    rounded: '{rounded.surface}'
    padding: 20px
  admin-visit:
    backgroundColor: '{colors.admin-accent-soft}'
    textColor: '{colors.admin-primary}'
    rounded: '{rounded.button}'
    padding: 9px 8px
---

# Design System: Axon

## Overview

**Creative North Star: "Axon · рабочее расписание"**

Axon Admin is a restrained, light working environment: pale green selection, white forms and tables, dark green actions, and quiet neutral framing. The confirmed direction is clear and intuitive rather than ornamental. The system extends Django Admin and keeps its functional forms and permission-aware navigation.

This document records the shipped source. Tokens prefixed `admin-` apply to `static/booking/admin.css` and `templates/admin/`; they are not universal replacements for the public demo. The existing landing page in `static/booking/site.css` and `templates/booking/home.html` retains its own warmer paper, lime accent, Manrope typography, DM Sans wordmark, and illustrative chat treatment. Landing tokens are explicitly prefixed `landing-`.

**Key Characteristics:**
- Light neutral background with white working surfaces.
- Dark green actions and pale green selection.
- Compact, readable administration with explicit labels and visible focus.
- Separate, preserved visual treatment for the public demo.

## Colors

The administration combines a dark, muted green accent with pale green selection and light neutral surfaces. Frontmatter owns the exact primitives; the source stylesheets remain implementation evidence.

### Primary

- **Admin forest green** (`admin-primary`): links, primary actions, module headings, and active status text. Its darker hover variants distinguish link and button states.
- **Admin pale green** (`admin-accent-soft`, `admin-selected`, `admin-nav-selected`): visit blocks, status badges, module headings, and selected navigation. These are surfaces for dark text, not light text.
- **Landing lime and forest** (`landing-green`, `landing-dark`): outgoing example chat bubbles and the public demo call to action. Keep these within the landing treatment.

### Secondary

- **Admin destructive red** (`admin-danger`, `admin-danger-hover`): errors and the final cancellation action.
- **Admin absence amber** (`admin-absence`, `admin-absence-ink`): absence information accompanied by a readable label.

### Neutral

- **Admin paper and white** (`admin-paper`, `admin-surface`): page and working surfaces; sidebar uses its slightly green neutral.
- **Admin ink, secondary, and muted text**: hierarchy for headings, field labels, supporting details, and calendar metadata.
- **Admin lines**: quiet separators, container edges, and a stronger input stroke.
- **Admin inactive and cancelled**: subdued state backgrounds; cancelled visits also use explicit text and struck-through time.
- **Landing paper, ink, muted, and line**: the incumbent warmer public-page neutrals.

**The Scoped Palettes Rule.** Use admin tokens on administrative screens and landing tokens on the public demo; shared green character does not make the two palettes interchangeable.

**The Color with Meaning Rule.** Reserve red for errors and destructive confirmation; show status in words as well as color.

## Typography

**Admin font:** the native system stack recorded in the `admin-` typography roles. It serves both headings and body text. There is no separate decorative display face in administration.

**Landing fonts:** Manrope for content and DM Sans for the wordmark, loaded by the existing public stylesheet.

### Hierarchy

- **Admin headline:** page titles and the calendar heading; reduced to (25px) at the narrowest breakpoint.
- **Admin title:** week range; reduced to (14px) on small screens.
- **Admin body:** general administration; table rows and form inputs use the smaller field role.
- **Admin label:** compact action text. Navigation is (13px), regular at rest and semibold when selected.
- **Admin status:** compact badges. Calendar supporting details use (10–11px); mobile visit title and detail sizes rise to (14px) and (12px).
- **Numeric information:** calendar dates and visit/working times use tabular numerals.
- **Landing display/body/brand:** their own recorded roles; the landing hero uses explicit responsive overrides (46px at 900px, 48px at 640px).

Typography entries include only observed properties. Unspecified weight or line height inherits from the relevant stylesheet rather than declaring a new scale.

## Layout

Administration uses a persistent sidebar (230px) and flexible main content with (32px 36px) padding. At (1200px) the sidebar reduces to (206px), with content padding (28px 24px). At (900px), navigation becomes a horizontal scrollable row, the header wraps, and main content becomes one column with (26px 22px) padding. At (600px), content padding is (24px 18px), filter fields and principal filter action fill the available width, and field labels stack above controls.

The desktop week table has a minimum width (900px), a specialist column (156px), seven day columns, and an overflow container. At (900px) and below it is replaced by a daily agenda; this is the calendar’s responsive implementation, not a universal page template. Native form layouts retain labels, help text, errors, and submit controls. The dual-list selector stacks vertically at (900px), with down/up transfer directions; working intervals become labelled grid rows at (600px). Existing-object captions in those interval rows are hidden to avoid collisions.

Spacing is compact but deliberate. Small gaps separate related controls; larger padding defines panels and sections. Frontmatter lists observed reused pixel steps rather than claiming a strict mathematical scale. Form text fields cap at (420px), textareas at (560px), and cancellation context at (680px), with prose capped at (65ch).

The public landing retains a centered shell (1280px maximum) with desktop horizontal padding (64px), then (30px at 900px) and (22px at 640px). Its hero and three-column catalog/team layouts collapse at (640px). These public-page proportions do not define admin density.

## Elevation & Depth

Admin depth comes from white surfaces, hairlines, and pale green state changes. No custom admin box shadows are defined. A keyboard focus outline is structural state feedback (2px with 3px offset), not ambient elevation. Button state transitions use (160ms ease-out); reduced-motion preference disables transitions.

**The Flat Working Surfaces Rule.** Admin surfaces use borders and tonal changes to establish hierarchy, without decorative shadows.

The existing landing alone uses a diffuse preview shadow (`0 24px 60px #3344220d`) and a faint chat-bubble shadow (`0 2px 3px #00000003`). Its preview is slightly rotated on larger screens and straightens on mobile; do not extend that illustration treatment into administration.

## Shapes

Admin shapes are gently rounded rectangles with one-pixel borders. Fields use the field radius, actions the button radius, navigation the nav radius, and larger working surfaces the surface radius. Compact status badges use the status radius. Module/submit containers use the module radius; the login shell has its own larger radius. Calendar avatars are circles. Keep the distinction between compact controls and larger enclosing surfaces.

The public demo keeps its own rounded cards (12px), asymmetric chat bubbles, circular initials, and larger illustrative preview frame (22px). These are existing landing patterns, not admin primitives.

## Components

### Buttons

Primary actions are dark green with white text, compact padding, and a minimum height (38px). Secondary actions use a white surface, quiet border, and green text; hover adds pale green. Quiet links use transparent surfaces and a pale green hover. Destructive red is used at final cancellation confirmation. The same global visible-focus treatment applies to all variants. Week arrows are square controls (34px) with SVG icons and accessible labels. Retain the native Django submit-row behaviors.

### Chips

Status badges are compact text labels with pale green or inactive neutral fill. They are informational rather than toggles; state remains readable without color.

### Cards / Containers

Calendar toolbar, changelist, fieldsets, and agenda days share white surfaces and thin neutral borders. Toolbar padding is (20px), agenda padding (18px), and form rows (18px 22px); mobile form rows reduce to (16px). The cancellation panel uses the same material with a subdued summary region. Do not introduce shadows to distinguish nested admin containers.

### Inputs / Fields

Native inputs, selects, and textareas retain their browser and Django functionality. They have a white surface, stronger neutral stroke, field radius, padding (9px 11px), and minimum height (38px). Calendar controls use a denser (12px) text role and (7px 10px) padding. Focus uses the shared green outline, with green caret and accent. Required labels use ink; help uses muted text. Django error states remain visible. Dual-list selector headings and selected-list footers use pale green with dark green text.

### Navigation

Labelled SVG icons precede text. Resting links use secondary text, hover adds a subtle green surface, and the current page uses pale green plus semibold dark text and `aria-current`. The mobile row preserves readable labels and scrolls horizontally. Account actions wrap within the header. Native changelist view links omit the colored eye background so they remain plain, readable links.

### Calendar visits

Visit blocks show time, client, and service in that order. Desktop blocks are compact, while mobile agenda blocks use larger text and add the specialist. Cancelled blocks are neutral, with a cancellation label and struck-through time. Absence and working hours remain separate information. These styles are extracted from source; populated visits and cancellation confirmation were not visually captured in the recorded QA set.

## Do's and Don'ts

### Do:
- **Do** use white working surfaces and pale green selection within the admin palette.
- **Do** pair status color with readable text and retain visible keyboard focus.
- **Do** let the admin header, filters, and actions wrap on narrow screens.
- **Do** preserve the public demo’s separate typography, palette, and existing illustration.

### Don't:
- **Don’t** apply admin tokens globally to the public landing page.
- **Don’t** replace real schedule information with decorative analytics or invented activity.
- **Don’t** remove field labels, confirmation context, permission checks, or native form behavior for visual simplicity.
- **Don’t** introduce decorative motion into administration.
