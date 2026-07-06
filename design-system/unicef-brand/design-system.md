# UNICEF Brand 4.0 — Document Authoring Design System

A reusable design system for authoring **PowerPoint decks, Word documents, and
other documents**, derived faithfully from **UNICEF Brand Book 4.0** ("How we
show up").

> **Scope & source of truth.** Every brand-mandated value below is drawn
> directly from Brand Book 4.0, with the source page cited. This is the
> *document-authoring subset* of the brand — the full logo lockups, photography
> direction, and print-collateral rules remain governed by the Brand Book and
> the official assets in the WeShare Brand library, not by this system.
> Values marked **[extension]** are reasonable authoring defaults (e.g. a body
> type scale) that the Brand Book does not specify; treat them as sensible
> starting points, not brand law.

---

## 1. Colour

### 1.1 Primary — UNICEF Blue (dominant) · *Brand Book p.49–50*

UNICEF Blue is Process Cyan at 100%. It is how UNICEF is instantly recognized
and **must be present, and dominant, in all messaging**.

| Token | Value | Notes |
|---|---|---|
| **UNICEF Blue** | HEX `#00AEEF` · RGB `0/174/239` · CMYK `100/0/0/0` · Pantone Process Cyan | Use the **RGB/HEX value in Office** — the Brand Book specifies RGB for PowerPoint and software (p.49). |

### 1.2 Neutrals · *p.50*

| Token | Value | Rule |
|---|---|---|
| **White** | `#FFFFFF` (CMYK 0/0/0/0) | Primary background. |
| **Black** | `#000000` (CMYK 100/100/100/100) | Text and detail. **Must not dominate** the colour scheme unless a sombre expression is needed. |

### 1.3 Accent colours · *p.53*

Use **subtly**. Accents complement UNICEF Blue and **must never take prominence
over it**.

| Token | HEX | Pantone / CMYK |
|---|---|---|
| Accent Blue | `#0047BB` | Pantone 2728 · C93/M78/Y0/K0 |
| Accent Green | `#004C45` | Pantone 3302C · C91/M41/Y67/K42 |
| Accent Orange (deep) | `#FF7100` | C0/M72/Y100/K0 |
| Accent Orange | `#FF8200` | Pantone 151C · C0/M60/Y100/K0 |
| Accent Yellow | `#FFB500` | Pantone 7549C · C0/M32/Y100/K0 |
| Accent Light Cyan | `#9ADBE8` | Pantone 304C · C36/M0/Y8/K0 |

### 1.4 Emergency palette · *p.56*

Only for emergency communications: **Red `#E2231A`** (Pantone 485). Cyan must be
used alongside red in equal or greater amount. Black backgrounds are acceptable
only when UNICEF Blue is also dominant.

### 1.5 Colour rules (hard constraints) · *p.53*

- Colours **may not be lightened, darkened, or shown transparently.**
- **Tints are permitted only** in data visualization and publication inside-pages.
- **UNICEF Blue must be dominant** in every piece.
- Accent colours must never out-weigh UNICEF Blue.

### 1.6 Accessibility note **[extension]**

UNICEF Blue (`#00AEEF`) on white gives a contrast ratio of ~1.9:1 — it **fails
WCAG AA for body text**. Use it for large headings, fills, and graphic elements,
**not for small body copy**. For small text on white use Black (`#000000`) or
Accent Blue `#0047BB` (~8.6:1). White text on UNICEF Blue (~1.9:1) is also
below AA for small text — reserve it for large display type.

---

## 2. Typography

### 2.1 Fonts · *p.57–60*

| Role | Font | Use |
|---|---|---|
| **Primary** | **Noto Sans** (Google Fonts; free, 800+ languages incl. all six UN languages) | Everything: headings, body, captions. Weights: Light, Regular, Bold (+ obliques). |
| **Secondary** | **Aleo** (serif) | Highlighting keywords in a brand statement. **Roman alphabet only** — use Noto Sans for non-Roman scripts. |
| Handwritten | (sparingly) | Only to add a human touch; large sizes, lowercase, high contrast. Never body text, never uppercase. |
| **Office fallback [extension]** | **Arial** | If Noto Sans is not installed. Install Noto Sans for true fidelity (see README). |

### 2.2 Type scale **[extension]** — not brand-mandated

A practical hierarchy for documents, built on Noto Sans.

| Style | PowerPoint | Word | Weight | Colour |
|---|---|---|---|---|
| Cover / Title | 44 pt | 32 pt | Bold | White on Blue (cover) / UNICEF Blue on white |
| Heading 1 | 28 pt | 20 pt | Bold | UNICEF Blue `#00AEEF` |
| Heading 2 | 22 pt | 15 pt | Bold | Accent Blue `#0047BB` |
| Heading 3 | 18 pt | 12 pt | Bold | Accent Green `#004C45` |
| Body | 18 pt | 11 pt | Regular | Black `#000000` |
| Caption | 12 pt | 9 pt | Regular | Accent Green `#004C45` |

Line spacing: 1.15 (Word body); paragraph space-after 8–10 pt.

---

## 3. The brand statement · *p.61*

The signature lockup: tagline **+** keyword, always **lowercase**, same size.

- Tagline `for every child,` → **Noto Sans Regular**
- Keyword (e.g. `every right`) → **Noto Sans Bold**

Example: *for every child,* **every right**

Approved keywords (p.10, p.63) include: *every right, education, peace,
nutrition, a healthy future, gender equality, opportunity, protection,
a fair chance, love, play, a childhood, safe water, vaccines, inclusion.*
Use these as document footers / closing slides.

---

## 4. Tone of voice · *p.15*

UNICEF speaks in a way that is **Direct · Authoritative · Positive · Engaging.**
Brand personality (p.12): Hopeful, Compassionate, Collaborative (+ three more).

**Boilerplate description (short form, p.18):**
> UNICEF, the United Nations agency for children, works to protect the rights of
> every child, everywhere, especially the most disadvantaged children and in the
> toughest places to reach.

---

## 5. Layout principles · *p.4, p.72*

- **Avoid visual clutter** — a core brand directive.
- Favour a single, strong photograph (full-bleed on covers) over busy collages.
- Keep UNICEF Blue dominant across the layout.
- Back covers / closing slides are UNICEF Blue and carry the logo + contact info.

---

## 6. Design tokens (machine-readable)

```json
{
  "color": {
    "primary": { "unicefBlue": "#00AEEF" },
    "neutral": { "white": "#FFFFFF", "black": "#000000" },
    "accent": {
      "blue": "#0047BB", "green": "#004C45", "orangeDeep": "#FF7100",
      "orange": "#FF8200", "yellow": "#FFB500", "lightCyan": "#9ADBE8"
    },
    "emergency": { "red": "#E2231A" }
  },
  "font": {
    "primary": "Noto Sans",
    "secondary": "Aleo",
    "officeFallback": "Arial"
  }
}
```

---

## 7. Logo (reference only — use official assets)

The system does **not** ship logo files. Download approved logo lockups (with
container / without container / without tagline, in 75+ languages) from the
**WeShare Brand library**. Key rules if you place a logo yourself:

- Primary version: **logo with container** on UNICEF Blue (p.30).
- Clear space = two emblems around the logo (p.35).
- Minimum size with container: **35 mm / 225 px** (p.35).
- Ideal placement: top-right (stacked) / bottom-right (horizontal).
- Never recolour, distort, add words, apply effects, or use the emblem alone
  (p.36, p.45).

---

*Derived from UNICEF Brand Book 4.0 (Division of Global Communication and
Advocacy, May 2024). This authoring system is an aid for consistent document
production and does not supersede the Brand Book or official brand assets.*
