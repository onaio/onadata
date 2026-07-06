# UNICEF Brand 4.0 — Claude Design import bundle

This folder is the **UNICEF Brand 4.0 system packaged for [Claude Design](https://claude.ai/design)**
(claude.ai/design design-system projects).

Each `.html` here is a **self-contained preview card**. Its first line is a
`@dsCard` marker, so Claude Design's *Design System* pane indexes it as a card
and groups it automatically. Noto Sans is inlined in every file, so each card
renders standalone.

## Cards

| Group | Card | File |
|---|---|---|
| Foundations | Colour palette | `foundations/colour-palette.html` |
| Foundations | Typography | `foundations/typography.html` |
| Foundations | Brand statement | `foundations/brand-statement.html` |
| Brand | Tone of voice | `brand/tone-of-voice.html` |
| Brand | Do & Don't | `brand/dos-and-donts.html` |
| Components | Buttons | `components/buttons.html` |
| Components | Tags & pills | `components/tags.html` |
| Components | Callouts | `components/callouts.html` |
| Components | Cards | `components/cards.html` |
| Components | Form fields | `components/forms.html` |
| Components | Data table | `components/tables.html` |
| Data visualization | Charts & palette | `dataviz/charts-and-palette.html` |
| Layouts | Slide layouts | `layouts/slides.html` |
| Layouts | Document cover | `layouts/document-cover.html` |

### Data-visualization palette

Charts follow the brand's data-viz allowance (tints/steps permitted, Brand Book
p.53) and were validated for colour-blind separation and contrast:

- **Sequential** (magnitude, one measure) — UNICEF Blue ramp:
  `#C2ECFB · #6FD0EF · #00AEEF · #0086C1 · #005A82`
- **Categorical** (series identity, always direct-labelled) —
  `#009BDC · #F07B00 · #1B9E8A · #5B7BD4 · #C99400`

One y-axis, recessive grid, direct labels over colour-only encoding.

## How to import into Claude Design

Pushing directly from this web session isn't possible — the sync tool needs an
interactive design login. Use **either** path:

**A. From Claude Design (recommended)**
1. Open <https://claude.ai/design> and create a new project — set the type to
   **Design System** (this type is fixed at creation).
2. Use **"Send to Claude Code Web"** to seed the project into a Code session, or
   run `/design-sync` in an interactive Claude Code that's logged in.
3. Point the sync at this folder (`design-system/unicef-brand/claude-design/`).
   The pane builds its card index from the `@dsCard` markers automatically.

**B. Manual**
1. Create the Design System project at <https://claude.ai/design>.
2. Upload the files in this folder, preserving the `foundations/ brand/ components/`
   paths. The `@dsCard` first-line markers do the grouping.

## Regenerating

```bash
python3 ../scripts/build_claude_design.py
```

Cards are generated from the same brand tokens as the rest of the system, so
edits stay consistent. See `../design-system.md` for the cited source values.
