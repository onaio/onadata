# UNICEF Brand 4.0 — Document Authoring Design System

A design system for authoring on-brand **PowerPoint, Word, and other documents**,
built from **UNICEF Brand Book 4.0**. Use it as your default styling unless a
specific piece calls for otherwise.

## What's here

| File | What it is |
|---|---|
| [`design-system.md`](design-system.md) | The reference: colour, type, brand statement, tone, layout, and machine-readable tokens — every value cited to a Brand Book page. |
| [`brand-guidelines.html`](brand-guidelines.html) | Visual guidelines page (swatches, type specimens, do's & don'ts). Open in a browser. |
| `office/UNICEF-Brand-4.0.thmx` | **Office Theme** — wires UNICEF Blue + Noto Sans into PowerPoint **and** Word natively. |
| `office/UNICEF-Brand-4.0.potx` | **PowerPoint template** — 16:9, branded cover / section / content slides. |
| `office/UNICEF-Brand-4.0.dotx` | **Word template** — branded Title, Heading 1–3, Body, Caption styles. |
| `scripts/build_office_assets.py` | Regenerates the three Office files from the shared tokens. |

## Quick start

### 1. Install the font (do this first)

Download **Noto Sans** (free) from Google Fonts → <https://fonts.google.com/noto/specimen/Noto+Sans>
and install Light, Regular, and Bold. Optionally install **Aleo** for serif
keyword highlights. Without Noto Sans installed, Office falls back to **Arial**.

### 2. Use the templates

- **PowerPoint:** double-click `UNICEF-Brand-4.0.potx` (or *File → New from Template*).
  Start from the cover, section, and content slides provided.
- **Word:** double-click `UNICEF-Brand-4.0.dotx` (or *File → New from Template*).
  Apply the **Title / Heading 1–3 / Normal / Caption** styles from the Styles gallery.

### 3. Apply the theme to an existing file

To brand a document you already started, apply the Office **Theme**:

- **PowerPoint:** *Design → Themes → Browse for Themes…* → pick `UNICEF-Brand-4.0.thmx`.
- **Word:** *Design → Themes → Browse for Themes…* → pick `UNICEF-Brand-4.0.thmx`.

The theme sets **UNICEF Blue as Accent 1** and **Noto Sans** as the document font,
so the palette and fonts appear natively in the colour picker and Styles.

## Golden rules (from the Brand Book)

1. **UNICEF Blue `#00AEEF` is dominant** in every piece.
2. **Accents are subtle** and never outweigh UNICEF Blue.
3. **Never alter colours** — no lightening, darkening, or transparency (tints only
   in charts and publication inside-pages).
4. **Noto Sans** for everything; the brand statement is lowercase — tagline Regular
   + keyword **Bold**: *for every child,* **every right**.
5. **Avoid visual clutter.**
6. **Logos:** use official WeShare assets, never recolour or distort. Don't place a
   logo over a child's face; keep two-emblem clear space.

## Accessibility

UNICEF Blue on white **fails WCAG AA for small text** (~1.9:1). Use it for large
headings and fills, not body copy. For small text on white, use **Black** or
**Accent Blue `#0047BB`**. See `design-system.md` §1.6.

## Regenerating the Office assets

```bash
pip install python-pptx python-docx lxml
python3 scripts/build_office_assets.py
```

---

*Derived from UNICEF Brand Book 4.0 (May 2024). An authoring aid — it does not
supersede the Brand Book or official brand assets in the WeShare Brand library.*
