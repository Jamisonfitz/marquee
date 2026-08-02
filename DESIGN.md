---
name: Marquee
description: A cinematic now-playing marquee for the Nest Hub — and the letterboard you compose it on
colors:
  night-asphalt: "#0B0D10"
  booth-panel: "#14171C"
  panel-sheen-top: "#171B21"
  panel-sheen-bottom: "#12151A"
  hairline: "#262B33"
  house-white: "#F2EEE6"
  soft-white: "#C7CBD1"
  usher-gray: "#9AA1AB"
  marquee-amber: "#E5A83B"
  card-panel-amberwarm: "#17130D"
  swatch-ice: "#7FB8E8"
  swatch-crimson: "#E85454"
  swatch-emerald: "#5BC98F"
typography:
  display:
    fontFamily: "'Bebas Neue', 'Arial Narrow', sans-serif"
    fontSize: "30px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: ".045em"
  headline:
    fontFamily: "'Bebas Neue', 'Arial Narrow', sans-serif"
    fontSize: "21px"
    fontWeight: 400
    letterSpacing: ".07em"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "11.5px"
    fontWeight: 700
    letterSpacing: ".07em"
rounded:
  control: "8px"
  seg: "9px"
  panel: "14px"
  bezel: "12px"
  pill: "99px"
spacing:
  row-gap: "12px"
  row-pad: "9px"
  panel-pad: "20px"
  section-gap: "18px"
components:
  button-save:
    backgroundColor: "{colors.marquee-amber}"
    textColor: "{colors.night-asphalt}"
    typography: "{typography.headline}"
    rounded: "{rounded.seg}"
    padding: "9px 24px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.house-white}"
    rounded: "{rounded.seg}"
    padding: "8px 13px"
  chip-block:
    backgroundColor: "{colors.night-asphalt}"
    textColor: "{colors.usher-gray}"
    rounded: "{rounded.pill}"
    padding: "9px 14px"
  chip-block-selected:
    backgroundColor: "rgba(229,168,59,.08)"
    textColor: "{colors.house-white}"
    rounded: "{rounded.pill}"
  seg-active:
    backgroundColor: "{colors.marquee-amber}"
    textColor: "{colors.night-asphalt}"
  panel:
    backgroundColor: "{colors.booth-panel}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel-pad}"
---

# Design System: Marquee

## Overview

**Creative North Star: "The Letterboard"**

Everything in Marquee is a sign you compose. The card the Hub shows is a
letterboard — movable blocks of lettering, a poster pinned beside them, bulbs
around the edge — and the settings page is the same letterboard laid on the
workbench: bulb rails across the masthead, template cards like poster proofs,
chips that read as little name-plates you press on and pull off. Nothing here
is a "form"; it's signage being arranged.

The personality is a **playful poster shop**, not a solemn theater: the demo
films are jokes (Rat King III, Participation Trophy), the copy talks like a
person, and warmth wins ties — rounded pieces, amber light, humor allowed.
The dark ground exists so the lettering and the art can glow, and depth comes
from light, not shadow: what's live is lit, what's off is dark glass.
Confirmed anti-references: generic dark-admin dashboards; walls of toggle
rows; solemn "home theater" luxury.

**Key characteristics**
- One warm accent (marquee amber) doing the work of ten
- Bebas Neue letterboard voice for headings; quiet system type for prose
- Chips and pills as the unit of interaction; panels as workbenches
- State = light: lit when live, dim when off, dashed when absent
- Original, funny demo content is part of the brand

## Colors

A single warm accent over a near-black ground, with the card's eight
selectable colorways treated as gels over the same night.

### Primary
- **Marquee Amber** (#E5A83B): the working light. Save, active seg options,
  selected cards and chips, focus rings, section headings, every glow. On any
  lit amber surface, ink is Night Asphalt.

### Neutral
- **Night Asphalt** (#0B0D10): the page ground and chip resting fill; also the
  ink color on lit amber.
- **Booth Panel** (#14171C, sheen gradient #171B21→#12151A): panels and the
  editor — the workbench surfaces.
- **Hairline** (#262B33): every border and rule; 1px always.
- **House White** (#F2EEE6): primary text and lit chip labels.
- **Usher Gray** (#9AA1AB): secondary text, hints, resting chip labels
  (large/short strings only — body prose stays House White).

### Card colorways (the gels)
The card ships eight user-selectable accents (amber default, ice #7FB8E8,
crimson #E85454, emerald #5BC98F, campaign, concrete, trophy, bsides) plus
per-block custom color. The settings chrome itself never changes color —
**the chrome stays amber; only the card wears gels.**

### Named Rules
**The One Bulb Rule.** Amber is the only accent in the settings chrome. Reds
exist solely as destructive hover (chip ×), greens not at all. If a second
color appears in chrome, it's a bug, not a theme.

**The Gels Rule.** User color belongs to the card. Chrome demonstrates
restraint so the user's choices are what pops in the preview.

## Typography

**Display Font:** Bebas Neue (fallback Arial Narrow) — loaded from Google
Fonts with graceful offline fallback, same as the card.
**Body Font:** system-ui stack.

**Character:** Bebas is the letterboard voice — condensed capitals like
press-on marquee letters, used for the masthead, tab names, section headings,
and the Save button. Body text stays quiet and system-native so the signage
reads as signage. The pairing is playful-confident, never shouty: Bebas sizes
stay modest (30px masthead, 21px headings) and letter-spacing does the work.

### Hierarchy
- **Display** (400, 30px, ls .045em, uppercase): masthead "MARQUEE settings";
  the amber word carries a soft glow.
- **Headline** (400, 21px, ls .07em, uppercase, amber): section headings with
  a 1px hairline underline; also tab labels (17px) and "EDITING: <BLOCK>".
- **Body** (400–500, 13.5–15px, lh 1.5): row labels, prose, release cards.
- **Label** (700, 11.5–12px, ls .07em, uppercase, Usher Gray): slider captions
  and micro-labels.

### Named Rules
**The Letterboard Rule.** Bebas appears only where a sign would: names of
things, headings, the one primary action. Never body copy, never hints, never
more than one size jump at a time.

## Layout

Single page column, max 1460px. The Design tab is the anatomy of the product:
tabs → template carousel (horizontal scroll, 108px cards) → preview row
(CSS grid `minmax(0,1fr) 360px`: card preview + chip strip left, sticky
editor right). Connection is stacked panels of `label+hint | control` rows
with hairline rules, max 860px. Rows: 9px vertical padding, 12px gaps;
panels: 20px padding, 18px between.

Breakpoint 900px. Under it: the preview pins sticky to the top
(`max-width: min(100%, 42dvh)` keeps it small enough to work beneath),
template thumbs drop to 60px, the editor folds behind an "Edit blocks"
button (selection force-opens it), touch targets rise to ≥44px, and segs
grow. The on-screen keyboard can never cover a top-pinned preview — that's
why it's pinned top, and it must stay there.

## Elevation & Depth

**Light is depth.** Surfaces are flat; hierarchy comes from what's lit:
the amber glow on Save, the halo on a selected template card, the lit dot in
a checked switch, the sheen gradient across panels. Box shadows exist only to
ground large physical objects — the preview bezel (dark frame + faint amber
under-glow, like screen light on a wall) and the floating tour card. Never
shadow a row, chip, or button. Absent things go the other way: dashed
borders and .55 opacity (ghost chips, the add tray, the "+ Save preset" card).

## Shapes

Pills (99px) for anything you tap in passing: chips, add-tray options, the
metadata name-plates. Rounded rectangles at 8–9px for controls (inputs,
selects, segs, secondary buttons), 12px for the screen bezel, 14px for
panels and template cards. Bulb rails (repeating radial-gradient dots, one
amber bulb per three dim) frame only the masthead — they are the letterboard's
signature and must not spread to every edge. Dashed borders always mean
"not really here": ghost chips, add affordances, tour highlights.

## Components

- **Save (the one primary):** lit amber plate, Bebas caps, its own glow +
  cast light; hover brightens. There is exactly one on screen, in the top bar.
- **Secondary buttons:** hairline-bordered transparent plates; hover warms the
  border amber. Text 13px/700.
- **Block chips:** pill name-plates. Resting: dark fill, gray label. Selected:
  amber border + amber-tinted fill + white label. Ghost (on card, nothing
  rendered): dashed + dimmed — the truth state, never fake it. The × sits
  inside the pill and only it turns red on hover.
- **Template/preset cards:** 16:10 thumb + name; selected takes the amber
  border + soft halo. Preset cards carry a tiny "by <author>" credit line and
  an × badge. "+ Save preset" and "+ Add" are dashed (absent-things grammar).
- **Switches:** 44×25 pill; checked = amber-tinted track + glowing amber knob.
  A switch's glow *is* its state — no other on-indicator.
- **Segs:** hairline pill-row; the active option is a solid amber block with
  dark ink.
- **Sliders:** native ranges with amber accent-color, value readouts in
  tabular numerals beside their labels.
- **The editor:** one panel, contextual — header names the block, then only
  that block's rows. Gated rows dim to .45 with disabled controls (dead
  controls must look dead).
- **Tour card:** fixed bottom-center, amber border, Bebas title, dashed
  amber outline + pulse on the spotlighted element (pulse dies under
  reduced-motion).
- **Feel:** playful poster shop — pieces read as pressable, rounded, warm.
  When adding a component, err toward a name-plate you'd press on a board,
  not a form field.

## Do's and Don'ts

**Do**
- Let the demo films be funny; write UI copy like a person explaining, why
  first ("Lit = on the card. Tap to flip.").
- Keep every "save to apply" promise: drafts announce themselves in the
  status line.
- Judge card typography from couch distance on a 7″ Hub (hard floor from
  PRODUCT.md).
- Honor prefers-reduced-motion on both surfaces; keep the amber focus ring.

**Don't**
- Add a second accent to the settings chrome (One Bulb Rule).
- Shadow small components; depth is light (ghosts are dashed, not shadowed).
- Bring back toggle walls — new options join the block that owns them, or
  Connection if they're plumbing.
- Set Bebas in body sizes or lowercase; it is signage only.
- Ship real posters in demo content, ever.
