---
target: settings page
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-07-31T19-11-47Z
slug: cast-settings-html
---
# Critique — Marquee settings page (cast/settings.html), Operate mode

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Save status + live preview strong; dependent controls never reflect parent state |
| 2 | Match with real world | 3 | Row hints are excellent plain language |
| 3 | User control & freedom | 3 | Export/import, template reset; no post-save undo |
| 4 | Consistency & standards | 2 | Mixed thumbnail fidelities; mobile silently hides Template grid + Vibes row |
| 5 | Error prevention | 2 | Clock style/seconds editable with Clock off; weather intensity/ZIP/units live with Weather+effects off |
| 6 | Recognition over recall | 2 | Card content = 17 undifferentiated rows; clock/weather families exist only in the user's head |
| 7 | Flexibility & efficiency | 3 | Vibes presets + per-block editor is a real novice→expert ramp |
| 8 | Aesthetic & minimalist | 2 | Toggle wall reads as one grey column; desktop preview column holds a large black void below the open editor |
| 9 | Error recovery | 3 | Status line, resets |
| 10 | Help & documentation | 3 | Inline hints + What's-new panel |

**Total: 26/40** (all ten scored)

## Design Specificity Verdict
The page shares one committed palette (night + amber) with the card it configures — identity holds. The failures are structural, not stylistic.

## Priority Issues
1. **P1 — Card content is a flat wall.** Backdrop/logo/plot/genres/scores/media/rating/runtime/progress + 3 clock rows + 5 weather rows all render at equal weight. Group into visible families (Clock, Weather) and gate dependents.
2. **P1 — Dependents never disable.** Clock style/seconds active with Clock off; Weather effects/intensity/ZIP/units active with weather fully off. Error-prevention failure and the main "doesn't make sense" driver.
3. **P1 — Desktop preview void.** The block editor ships `open`, pushing the preview iframe deep down the sticky column; at 1440px the visible right column is mostly empty black. The product's stated core principle is "always see the preview."
4. **P2 — Mobile hides Template/Vibes** behind a JS carousel that renders no visible cards in a cold headless load; verify it actually paints before trusting it as the only mobile template picker.
5. **P3 — Panel headings are weak** (11px tracked caps) for a page this long; scanability suffers on mobile.

## Persona Red Flags
- *First-run Unraid user*: hits 17 toggles before finding the Save button relationship; cannot tell why Clock style does nothing.
- *Phone tuner (the owner)*: bottom sheet works, but the preview he insists on seeing sits below an open editor on desktop.

## Minor Observations
- Theme swatch "reset" chip floats oddly on wrap; Street thumbnail is a color sketch while others are dark screenshots.

## Questions to Consider
- Should Units/ZIP live under Weather rather than as peers of Plot?
