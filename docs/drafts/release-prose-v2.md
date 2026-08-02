# Release prose drafts — apply to GitHub after testing sign-off

These replace the published bodies of v2.0.0 and v2.1.0 once Jamison approves
the docs push (releases are edited via
`gh api -X PATCH repos/Jamisonfitz/marquee/releases/<id> -f body=...`).
Written in the explain-the-why voice; the What's new tab renders the
CHANGELOG, so these two only need to land on GitHub.

---

## v2.0.0 — Settings v2

**The settings page is the card now.**

Marquee's settings used to be a page of controls with a preview attached.
v2 flips that: the live preview fills the page, and you edit what you're
looking at. Tap the plot, the clock, the poster — or the card's empty
background — and just that thing's controls appear: font, color (new, and
per block), position, width, size, plus whatever the block owns. Clock style
lives with the clock. Weather effects live with the weather. The logo toggle
lives with the title. Nothing is more than one tap from the thing it changes.

**Why:** every option used to be global and somewhere else. You'd scroll a
wall of toggles wondering which of them touched the thing you were staring
at. Editing in place removes the translation step — and per-block color
replaces the old whole-card themes with something strictly more capable
(your saved theme keeps tinting until you recolor, so nothing changes on
update).

**Also in this release**

- **Presets** — bottle your current look onto the template carousel; Export
  backs them up.
- **Block chips** — one pill per block on the card: tap to edit, × to
  remove, "+ Add" brings anything back.
- **A six-step guided tour** over the real interface, once, for new installs.
- **Phones done right** — the preview pins to the top at a working size; the
  keyboard can never cover it.
- **Every old save and export imports cleanly** — presence flags and even
  pre-v1.10 flat layouts migrate automatically.

Gone: the vibes and theme rows (absorbed by per-block color), card-wide font
rows, and poster side.

---

## v2.1.0 — honest chips, shareable looks

**The chips stopped assuming.** A block can be on your card yet have nothing
to show — no scores for this title, an emptied metadata line. The old page
happily let you drag sliders at a block that wasn't on screen. Now the card
reports what it actually rendered after every frame: absent blocks go dashed
and dim, and the editor says plainly that there's nothing to show right now
— your changes still save for when there is.

**Looks are shareable, and credit travels.** "Share this look" copies your
screen setup as a small versioned JSON file — the template, every block's
position, size, font, and color, plus display settings that travel well
(never your location or credentials). It's tagged with your name; when
someone imports it, it lands on their carousel as a preset credited "by
you", one tap from applied. If people start trading these, the format is
ready for a community repo.

**About grew a memory.** TRusselo's backends and filters, catt (the casting
engine underneath everything), and the CodePen artists behind the weather
are now credited where users can see them — plus an optional Buy Me a
Coffee button. And What's new reads as release cards that explain the what
and the why, instead of a wall of changelog text.
