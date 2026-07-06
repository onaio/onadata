#!/usr/bin/env python3
"""
Generate a Claude Design (claude.ai/design) import bundle from the UNICEF Brand
4.0 system.

Each output is a self-contained preview HTML whose FIRST line is a
`<!-- @dsCard group="..." name="..." subtitle="..." -->` marker, so the Claude
Design "Design System" pane indexes it as a card. Noto Sans is inlined per file
so every card renders standalone in the pane.

Output: ../claude-design/<group>/<name>.html
Run:    python3 build_claude_design.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "claude-design"))
B64 = open(os.path.join(
    os.path.dirname(HERE), "..", "..",
)) if False else None

# Load the inlined font produced during the guidelines build.
FONT_B64_PATH = os.environ.get("NOTO_B64_PATH", "")
if not FONT_B64_PATH:
    # fall back to scratchpad copy if present, else extract from guidelines html
    cand = os.path.join(HERE, "notosans-b64.txt")
    FONT_B64_PATH = cand
if os.path.exists(FONT_B64_PATH):
    NOTO_B64 = open(FONT_B64_PATH).read().strip()
else:
    # extract from the already-built guidelines page
    html = open(os.path.join(os.path.dirname(HERE), "brand-guidelines.html")).read()
    import re
    m = re.search(r"base64,([A-Za-z0-9+/=]+)\)", html)
    NOTO_B64 = m.group(1)

# ---------------------------------------------------------------------------
BRAND = dict(
    blue="#00AEEF", blueInk="#0047BB", green="#004C45", orange="#FF8200",
    yellow="#FFB500", ltcyan="#9ADBE8", red="#E2231A",
    ink="#0a1417", muted="#5b6c73", hair="#d9e6ec", panel="#f5fafc",
    panel2="#eef6f9",
)

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
@font-face{{font-family:"Noto Sans";font-style:normal;font-weight:100 900;
font-display:swap;src:url(data:font/woff2;base64,{font}) format("woff2");}}
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{font-family:"Noto Sans",Arial,system-ui,sans-serif;color:{ink};
background:#ffffff;-webkit-font-smoothing:antialiased;
padding:28px;line-height:1.55;}}
.card-title{{font-size:12px;font-weight:700;letter-spacing:.16em;
text-transform:uppercase;color:{blue};margin:0 0 4px}}
.card-sub{{font-size:13px;color:{muted};margin:0 0 22px}}
h1,h2,h3,p{{margin:0}}
</style></head><body>
"""


def page(group, name, subtitle, body, title, tagline):
    marker = f'<!-- @dsCard group="{group}" name="{name}" subtitle="{subtitle}" -->\n'
    head = HEAD.format(font=NOTO_B64, **BRAND)
    intro = (f'<p class="card-title">{title}</p>'
             f'<p class="card-sub">{tagline}</p>')
    return marker + head + intro + body + "\n</body></html>\n"


def write(group_dir, filename, html):
    d = os.path.join(OUT, group_dir)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, filename)
    open(p, "w").write(html)
    return os.path.relpath(p, OUT)


B = BRAND
files = []

# ---------------------------------------------------------------------------
# FOUNDATIONS — Colour
# ---------------------------------------------------------------------------
swatches = [
    ("UNICEF Blue", B["blue"], "on-dark", "Primary · dominant",
     ["HEX #00AEEF", "RGB 0 / 174 / 239", "CMYK 100/0/0/0", "Pantone Process Cyan"]),
    ("White", "#FFFFFF", "on-light", "Neutral",
     ["HEX #FFFFFF", "RGB 255/255/255", "Primary background"]),
    ("Black", "#000000", "on-dark", "Neutral",
     ["HEX #000000", "RGB 0 / 0 / 0", "Must not dominate"]),
    ("Accent Blue", B["blueInk"], "on-dark", "Accent",
     ["HEX #0047BB", "Pantone 2728"]),
    ("Accent Green", B["green"], "on-dark", "Accent",
     ["HEX #004C45", "Pantone 3302C"]),
    ("Accent Orange", B["orange"], "on-dark", "Accent",
     ["HEX #FF8200", "Pantone 151C"]),
    ("Accent Yellow", B["yellow"], "on-light", "Accent",
     ["HEX #FFB500", "Pantone 7549C"]),
    ("Light Cyan", B["ltcyan"], "on-light", "Accent",
     ["HEX #9ADBE8", "Pantone 304C"]),
    ("Emergency Red", B["red"], "on-dark", "Emergency only",
     ["HEX #E2231A", "Pantone 485"]),
]
cells = ""
for name, hexv, tone, role, vals in swatches:
    rolebg = "rgba(0,0,0,.35);color:#fff" if tone == "on-dark" else "rgba(255,255,255,.92);color:#0a1417"
    border = f";border:1px solid {B['hair']}" if hexv == "#FFFFFF" else ""
    valrows = "".join(f'<span>{v}</span>' for v in vals)
    cells += f'''
    <div style="border:1px solid {B['hair']};border-radius:12px;overflow:hidden;background:{B['panel']}">
      <div style="height:78px;background:{hexv}{border};display:flex;align-items:flex-end;padding:10px">
        <span style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:3px 7px;border-radius:12px;background:{rolebg}">{role}</span>
      </div>
      <div style="padding:11px 13px 13px">
        <div style="font-weight:700;font-size:14px;margin-bottom:6px">{name}</div>
        <div style="display:grid;gap:2px;font-size:11.5px;color:{B['muted']};font-variant-numeric:tabular-nums">{valrows}</div>
      </div>
    </div>'''
body = f'''
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">{cells}</div>
<div style="margin-top:18px;padding:13px 16px;border-radius:10px;background:{B['panel2']};border-left:4px solid {B['blue']};font-size:13px">
<b>Colours cannot be altered</b> — no lightening, darkening, or transparency. UNICEF Blue stays dominant. Tints only in data-viz and publication inside-pages. <i>(Brand Book 4.0, p.53)</i>
</div>'''
files.append(("foundations", "colour-palette.html",
              page("Foundations", "Colour palette",
                   "Primary · neutrals · accents · emergency", body,
                   "Foundations — Colour", "UNICEF Blue leads; neutrals frame it; accents support it.")))

# ---------------------------------------------------------------------------
# FOUNDATIONS — Typography
# ---------------------------------------------------------------------------
type_rows = [
    ("Title", "Bold · 32pt", "Every child deserves a childhood", 34, 700, B["blue"]),
    ("Heading 1", "Bold · 20pt", "Protecting the rights of every child", 26, 700, B["blue"]),
    ("Heading 2", "Bold · 15pt", "Survive, thrive, reach full potential", 21, 700, B["blueInk"]),
    ("Heading 3", "Bold · 12pt", "In more than 190 countries", 17, 700, B["green"]),
    ("Body", "Regular · 11pt", "Body text is set in Noto Sans Regular for maximum legibility and calm, uncluttered layouts.", 15, 400, B["ink"]),
    ("Caption", "Regular · 9pt", "© UNICEF/UN0241775/Dejongh — credits sit quietly beneath imagery.", 12, 400, B["muted"]),
]
rows = ""
for k, meta, sample, size, weight, color in type_rows:
    rows += f'''
    <div style="display:grid;grid-template-columns:130px 1fr;border-top:1px solid {B['hair']}">
      <div style="padding:14px 16px;background:{B['panel2']};font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:{B['muted']};font-weight:700;display:flex;flex-direction:column;justify-content:center;gap:3px">
        {k}<span style="font-size:10.5px;text-transform:none;letter-spacing:0;font-weight:500">{meta}</span>
      </div>
      <div style="padding:12px 18px;display:flex;align-items:center;font-size:{size}px;font-weight:{weight};color:{color};letter-spacing:-.01em">{sample}</div>
    </div>'''
body = f'''
<div style="border:1px solid {B['hair']};border-radius:14px;overflow:hidden;background:{B['panel']}">{rows}</div>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px">
{"".join(f'<span style="font-size:12px;font-weight:600;padding:5px 11px;border-radius:16px;border:1px solid {B["hair"]};color:{B["muted"]}">{t}</span>' for t in ["Light","Regular","Bold","+ Obliques","Secondary: Aleo (serif)","Office fallback: Arial"])}
</div>'''
files.append(("foundations", "typography.html",
              page("Foundations", "Typography",
                   "Noto Sans — Title to Caption", body,
                   "Foundations — Typography", "One typeface, Noto Sans, used with intent across the hierarchy.")))

# ---------------------------------------------------------------------------
# FOUNDATIONS — Brand statement
# ---------------------------------------------------------------------------
kws = ["every right", "education", "peace", "nutrition", "a healthy future",
       "gender equality", "opportunity", "protection", "a fair chance",
       "safe water", "inclusion", "love"]
kwhtml = "".join(f'<span style="font-size:13px;padding:5px 11px;border-radius:8px;background:{B["panel2"]};color:{B["ink"]}">{k}</span>' for k in kws)
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div style="border:1px solid {B['hair']};border-radius:14px;padding:24px;background:{B['panel']}">
    <div style="font-size:30px;letter-spacing:-.02em;text-transform:lowercase;line-height:1.15;margin-bottom:16px">
      <span style="font-weight:400">for every child,</span> <span style="font-weight:700;color:{B['blue']}">every right</span>
    </div>
    <div style="display:flex;gap:8px;font-size:12.5px;color:{B['muted']};margin-bottom:6px"><span style="width:9px;height:9px;border-radius:2px;background:{B['muted']};margin-top:3px"></span>Tagline — Noto Sans <b style="color:{B['ink']}">Regular</b>, lowercase</div>
    <div style="display:flex;gap:8px;font-size:12.5px;color:{B['muted']}"><span style="width:9px;height:9px;border-radius:2px;background:{B['blue']};margin-top:3px"></span>Keyword — Noto Sans <b style="color:{B['ink']}">Bold</b>, same size</div>
  </div>
  <div style="border:1px solid {B['hair']};border-radius:14px;padding:24px;background:{B['panel']}">
    <div style="font-weight:700;font-size:15px;margin-bottom:12px">Approved keywords</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">{kwhtml}</div>
  </div>
</div>'''
files.append(("foundations", "brand-statement.html",
              page("Foundations", "Brand statement",
                   "Tagline + keyword, always lowercase", body,
                   "Foundations — Brand statement", "The signature lockup: tagline Regular + keyword Bold, same size.")))

# ---------------------------------------------------------------------------
# BRAND — Tone of voice
# ---------------------------------------------------------------------------
tones = [("Direct", "Say it plainly. Lead with the point."),
         ("Authoritative", "Grounded in evidence and field expertise."),
         ("Positive", "Show the solution and the opportunity."),
         ("Engaging", "Human, warm, centred on the child.")]
tcards = "".join(f'''<div style="border:1px solid {B['hair']};border-radius:12px;padding:18px 20px;background:{B['panel']}">
  <b style="display:block;color:{B['blue']};font-size:18px;margin-bottom:5px">{t}</b>
  <span style="font-size:13.5px;color:{B['muted']}">{d}</span></div>''' for t, d in tones)
body = f'<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px">{tcards}</div>'
files.append(("brand", "tone-of-voice.html",
              page("Brand", "Tone of voice", "Direct · Authoritative · Positive · Engaging",
                   body, "Brand — Tone of voice", "How we sound on the page, whatever the format.")))

# ---------------------------------------------------------------------------
# BRAND — Do & Don't
# ---------------------------------------------------------------------------
dos = ["Keep UNICEF Blue the dominant colour.",
       "Set everything in Noto Sans; statement lowercase.",
       "Use accents sparingly, in support of blue.",
       "Favour one strong photo over busy collage.",
       "Use official WeShare logo assets."]
donts = ["Lighten, darken, or make colours transparent.",
         "Let black or an accent out-weigh blue.",
         "Recolour, distort, or add words to the logo.",
         "Place a logo over a child's face.",
         "Fill the page with clutter."]
def lst(items, color):
    return "".join(f'<li style="font-size:13.5px;padding-left:18px;position:relative;margin-bottom:9px;list-style:none">'
                   f'<span style="position:absolute;left:0;top:7px;width:7px;height:7px;border-radius:50%;background:{color}"></span>{i}</li>' for i in items)
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div style="border:1px solid {B['hair']};border-radius:14px;padding:22px;background:{B['panel']}">
    <h3 style="display:flex;align-items:center;gap:8px;font-size:15px;margin-bottom:12px"><span style="width:22px;height:22px;border-radius:50%;background:{B['green']};color:#fff;display:grid;place-items:center;font-size:13px">✓</span>Do</h3>
    <ul style="margin:0;padding:0">{lst(dos, B['green'])}</ul>
  </div>
  <div style="border:1px solid {B['hair']};border-radius:14px;padding:22px;background:{B['panel']}">
    <h3 style="display:flex;align-items:center;gap:8px;font-size:15px;margin-bottom:12px"><span style="width:22px;height:22px;border-radius:50%;background:{B['red']};color:#fff;display:grid;place-items:center;font-size:13px">✕</span>Don't</h3>
    <ul style="margin:0;padding:0">{lst(donts, B['red'])}</ul>
  </div>
</div>'''
files.append(("brand", "dos-and-donts.html",
              page("Brand", "Do & Don't", "Application rules from the Brand Book",
                   body, "Brand — Do & Don't", "The core application rules, at a glance.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Buttons  (accessible: dark ink on UNICEF Blue = 8.6:1)
# ---------------------------------------------------------------------------
btn = "display:inline-flex;align-items:center;justify-content:center;font-family:inherit;font-size:15px;font-weight:700;padding:11px 22px;border-radius:8px;border:2px solid transparent;cursor:pointer;letter-spacing:.01em"
body = f'''
<div style="display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-bottom:22px">
  <button style="{btn};background:{B['blue']};color:{B['ink']}">Primary action</button>
  <button style="{btn};background:transparent;border-color:{B['blue']};color:{B['blueInk']}">Secondary</button>
  <button style="{btn};background:transparent;color:{B['blueInk']}">Ghost</button>
  <button style="{btn};background:{B['hair']};color:{B['muted']};cursor:not-allowed">Disabled</button>
</div>
<div style="display:flex;flex-wrap:wrap;gap:14px;align-items:center">
  <button style="{btn};background:{B['blueInk']};color:#fff">On dark ground</button>
  <button style="{btn};background:{B['green']};color:#fff">Confirm</button>
</div>
<div style="margin-top:20px;padding:12px 15px;border-radius:10px;background:{B['panel2']};border-left:4px solid {B['orange']};font-size:12.5px;color:{B['ink']}">
<b>Accessibility:</b> primary uses dark ink on UNICEF Blue (~8.6:1, AA ✓). White text on UNICEF Blue is only ~2.4:1 — avoid it for button labels; use Accent Blue <b>#0047BB</b> when white text is required.
</div>'''
files.append(("components", "buttons.html",
              page("Components", "Buttons", "Primary · secondary · ghost · disabled",
                   body, "Components — Buttons", "Actions built from the brand palette, with accessible contrast.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Tags / pills
# ---------------------------------------------------------------------------
tag = "display:inline-flex;align-items:center;font-size:13px;font-weight:600;padding:5px 13px;border-radius:20px;letter-spacing:.01em"
body = f'''
<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px">
  <span style="{tag};background:{B['blue']};color:{B['ink']}">Primary</span>
  <span style="{tag};background:{B['blueInk']};color:#fff">Accent</span>
  <span style="{tag};background:{B['green']};color:#fff">Programme</span>
  <span style="{tag};background:transparent;border:1px solid {B['hair']};color:{B['muted']}">Neutral</span>
</div>
<div style="display:flex;flex-wrap:wrap;gap:10px">
  <span style="{tag};background:{B['yellow']};color:{B['ink']}">Highlight</span>
  <span style="{tag};background:{B['red']};color:#fff">Emergency</span>
  <span style="{tag};background:{B['ltcyan']};color:{B['ink']}">Info</span>
</div>
<div style="margin-top:20px;padding:12px 15px;border-radius:10px;background:{B['panel2']};border-left:4px solid {B['blue']};font-size:12.5px">
Solid brand colours only — no tints (Brand Book p.53). Text colour is chosen per swatch to keep labels legible.
</div>'''
files.append(("components", "tags.html",
              page("Components", "Tags & pills", "Status and category chips",
                   body, "Components — Tags", "Compact labels using solid brand colours, not tints.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Callouts
# ---------------------------------------------------------------------------
def callout(rule, title, text):
    return f'''<div style="padding:15px 18px;border-radius:12px;background:{B['panel']};border:1px solid {B['hair']};border-left:5px solid {rule};margin-bottom:12px">
      <div style="font-weight:700;font-size:14px;margin-bottom:3px">{title}</div>
      <div style="font-size:13px;color:{B['muted']}">{text}</div></div>'''
body = (callout(B['blue'], "Information", "Neutral guidance, with UNICEF Blue as the accent rule.") +
        callout(B['orange'], "Caution", "Something to double-check before proceeding.") +
        callout(B['green'], "Success", "A completed or confirmed state.") +
        callout(B['red'], "Emergency", "Reserved for emergency communications only."))
files.append(("components", "callouts.html",
              page("Components", "Callouts", "Info · caution · success · emergency",
                   body, "Components — Callouts", "Left-ruled notes; the rule carries a solid brand colour.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Content card
# ---------------------------------------------------------------------------
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div style="border:1px solid {B['hair']};border-radius:16px;overflow:hidden;background:#fff">
    <div style="height:96px;background:{B['blue']}"></div>
    <div style="padding:18px 20px">
      <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{B['blue']};margin-bottom:6px">Programme</div>
      <h3 style="font-size:18px;color:{B['ink']};margin-bottom:8px">Every child, a healthy start</h3>
      <p style="font-size:13.5px;color:{B['muted']};margin-bottom:14px">A short supporting sentence describing the initiative in the brand's direct, positive voice.</p>
      <div style="font-size:14px;text-transform:lowercase"><span style="font-weight:400">for every child,</span> <span style="font-weight:700;color:{B['blue']}">nutrition</span></div>
    </div>
  </div>
  <div style="border:1px solid {B['hair']};border-radius:16px;overflow:hidden;background:{B['blue']};color:#fff">
    <div style="padding:22px 20px;min-height:96px">
      <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;opacity:.85;margin-bottom:8px">Impact</div>
      <div style="font-size:40px;font-weight:700;letter-spacing:-.02em">190+</div>
      <div style="font-size:13.5px;opacity:.9">countries and territories</div>
    </div>
    <div style="padding:14px 20px;background:rgba(0,0,0,.12);font-size:13px;text-transform:lowercase">
      <span style="font-weight:400">for every child,</span> <span style="font-weight:700">everywhere</span>
    </div>
  </div>
</div>'''
files.append(("components", "cards.html",
              page("Components", "Cards", "Content card · stat card",
                   body, "Components — Cards", "Containers on white and on the dominant UNICEF Blue ground.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Forms
# ---------------------------------------------------------------------------
field = (f"width:100%;font-family:inherit;font-size:14px;color:{B['ink']};"
         f"padding:10px 12px;border:1.5px solid {B['hair']};border-radius:8px;"
         f"background:#fff;outline:none")
lab = f"display:block;font-size:12.5px;font-weight:700;color:{B['ink']};margin-bottom:6px"
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px 24px;max-width:640px">
  <div>
    <label style="{lab}">Full name</label>
    <input style="{field}" value="Sofia Okoro" readonly>
    <div style="font-size:11.5px;color:{B['muted']};margin-top:5px">Help text sits quietly beneath the field.</div>
  </div>
  <div>
    <label style="{lab}">Country / territory</label>
    <div style="{field};display:flex;justify-content:space-between;align-items:center">Kenya <span style="color:{B['muted']}">▾</span></div>
  </div>
  <div>
    <label style="{lab}">Focus area</label>
    <div style="{field};border-color:{B['blue']};box-shadow:0 0 0 3px rgba(0,174,239,.18)">Nutrition<span style="border-right:2px solid {B['blue']};margin-left:1px">&nbsp;</span></div>
    <div style="font-size:11.5px;color:{B['blue']};margin-top:5px;font-weight:600">Focus state — UNICEF Blue ring</div>
  </div>
  <div>
    <label style="{lab}">Reference code</label>
    <input style="{field};border-color:{B['red']}" value="UN-000">
    <div style="font-size:11.5px;color:{B['red']};margin-top:5px;font-weight:600">Enter a valid 8-digit code.</div>
  </div>
</div>
<div style="display:flex;gap:22px;margin-top:20px;align-items:center">
  <label style="display:flex;align-items:center;gap:8px;font-size:13.5px"><span style="width:18px;height:18px;border-radius:5px;background:{B['blue']};display:inline-grid;place-items:center;color:{B['ink']};font-size:12px;font-weight:700">✓</span> Consent given</label>
  <label style="display:flex;align-items:center;gap:8px;font-size:13.5px"><span style="width:18px;height:18px;border-radius:5px;border:1.5px solid {B['hair']}"></span> Subscribe</label>
  <label style="display:flex;align-items:center;gap:8px;font-size:13.5px"><span style="width:18px;height:18px;border-radius:50%;border:5px solid {B['blue']};background:#fff"></span> Selected</label>
  <label style="display:flex;align-items:center;gap:8px;font-size:13.5px;color:{B['muted']}"><span style="width:18px;height:18px;border-radius:50%;border:1.5px solid {B['hair']}"></span> Option</label>
</div>'''
files.append(("components", "forms.html",
              page("Components", "Form fields", "Inputs · select · states · choices",
                   body, "Components — Forms", "Fields with the UNICEF Blue focus ring and a clear error state.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Tables  (blue header, dark ink = AA; neutral zebra, no tint)
# ---------------------------------------------------------------------------
rows_data = [
    ("Eastern & Southern Africa", "23.1M", "88%", "On track"),
    ("West & Central Africa", "19.4M", "81%", "On track"),
    ("South Asia", "31.7M", "76%", "Watch"),
    ("Middle East & N. Africa", "9.8M", "84%", "On track"),
]
trs = ""
for i, (region, reach, cov, status) in enumerate(rows_data):
    bg = "#ffffff" if i % 2 == 0 else B["panel"]
    scol = B["green"] if status == "On track" else B["orange"]
    trs += f'''<tr style="background:{bg}">
      <td style="padding:12px 16px;font-size:13.5px;border-bottom:1px solid {B['hair']}">{region}</td>
      <td style="padding:12px 16px;font-size:13.5px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px solid {B['hair']}">{reach}</td>
      <td style="padding:12px 16px;font-size:13.5px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px solid {B['hair']}">{cov}</td>
      <td style="padding:12px 16px;border-bottom:1px solid {B['hair']}"><span style="font-size:12px;font-weight:600;color:{scol}">● {status}</span></td>
    </tr>'''
body = f'''
<div style="border:1px solid {B['hair']};border-radius:12px;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:{B['blue']}">
    <th style="padding:12px 16px;text-align:left;font-size:12px;font-weight:700;color:{B['ink']};letter-spacing:.02em">Region</th>
    <th style="padding:12px 16px;text-align:right;font-size:12px;font-weight:700;color:{B['ink']}">Children reached</th>
    <th style="padding:12px 16px;text-align:right;font-size:12px;font-weight:700;color:{B['ink']}">Coverage</th>
    <th style="padding:12px 16px;text-align:left;font-size:12px;font-weight:700;color:{B['ink']}">Status</th>
  </tr></thead>
  <tbody>{trs}</tbody>
</table></div>
<div style="font-size:11.5px;color:{B['muted']};margin-top:10px">Header: dark ink on UNICEF Blue (8.6:1, AA ✓). Zebra rows use a neutral tint, not a brand-colour tint.</div>'''
files.append(("components", "tables.html",
              page("Components", "Data table", "Blue header · zebra rows · status",
                   body, "Components — Tables", "Accessible header, neutral zebra rows, status encoded by colour + label.")))

# ---------------------------------------------------------------------------
# DATA VISUALIZATION — palette + bar + line
# Validated (light) via the dataviz skill: sequential UNICEF Blue ramp is
# monotonic; categorical set passes band/chroma/CVD (contrast relieved by
# direct labels). Tints/steps are permitted in data-viz (Brand Book p.53).
# ---------------------------------------------------------------------------
SEQ = ["#C2ECFB", "#6FD0EF", "#00AEEF", "#0086C1", "#005A82"]
CAT = ["#009BDC", "#F07B00", "#1B9E8A", "#5B7BD4", "#C99400"]
GRID = "#e7eef1"

def swrow(label, colors):
    chips = "".join(
        f'<div style="flex:1;min-width:0"><div style="height:34px;background:{c};border-radius:6px;border:1px solid rgba(0,0,0,.06)"></div>'
        f'<div style="font-size:10.5px;color:{B["muted"]};margin-top:4px;text-align:center;font-variant-numeric:tabular-nums">{c}</div></div>'
        for c in colors)
    return (f'<div style="margin-bottom:14px"><div style="font-size:11px;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{B["muted"]};margin-bottom:7px">{label}</div>'
            f'<div style="display:flex;gap:8px">{chips}</div></div>')

# --- bar chart (single series, UNICEF Blue, direct value labels) ---
bars = [("ESA", 88), ("WCA", 81), ("SA", 76), ("MENA", 84), ("EAP", 90), ("LAC", 85)]
BW, BH, PL, PB, PT = 512, 190, 16, 26, 22
n = len(bars); slot = (BW - PL) / n; bw = 34
gl = ""
for gy in (0, 25, 50, 75, 100):
    y = PT + (BH - PT - PB) * (1 - gy / 100)
    gl += f'<line x1="{PL}" y1="{y:.1f}" x2="{BW}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
    gl += f'<text x="0" y="{y+3:.1f}" font-size="9" fill="{B["muted"]}">{gy}</text>'
bar_marks = ""
for i, (lbl, v) in enumerate(bars):
    x = PL + slot * i + (slot - bw) / 2
    h = (BH - PT - PB) * (v / 100)
    y = (BH - PB) - h
    bar_marks += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="{B["blue"]}"/>'
    bar_marks += f'<text x="{x+bw/2:.1f}" y="{y-5:.1f}" font-size="10.5" font-weight="700" fill="{B["ink"]}" text-anchor="middle">{v}</text>'
    bar_marks += f'<text x="{x+bw/2:.1f}" y="{BH-PB+13:.1f}" font-size="9.5" fill="{B["muted"]}" text-anchor="middle">{lbl}</text>'
barsvg = f'<svg viewBox="0 0 {BW} {BH}" width="100%" role="img" aria-label="Coverage by region"><line x1="{PL}" y1="{BH-PB}" x2="{BW}" y2="{BH-PB}" stroke="{B["hair"]}" stroke-width="1.5"/>{gl}{bar_marks}</svg>'

# --- line chart (2 series, categorical, direct end-labels + legend) ---
LW, LH, LPL, LPB, LPT, LPR = 512, 190, 20, 24, 16, 66
years = [2019, 2020, 2021, 2022, 2023]
s1 = [64, 61, 70, 79, 86]   # series A
s2 = [52, 55, 60, 66, 72]   # series B
def line_pts(series):
    pts = []
    for i, v in enumerate(series):
        x = LPL + (LW - LPL - LPR) * (i / (len(series) - 1))
        y = LPT + (LH - LPT - LPB) * (1 - (v - 40) / 60)
        pts.append((x, y, v))
    return pts
lgrid = ""
for gy in (40, 60, 80, 100):
    y = LPT + (LH - LPT - LPB) * (1 - (gy - 40) / 60)
    lgrid += f'<line x1="{LPL}" y1="{y:.1f}" x2="{LW-LPR}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
    lgrid += f'<text x="0" y="{y+3:.1f}" font-size="9" fill="{B["muted"]}">{gy}</text>'
def series_svg(series, color, name):
    pts = line_pts(series)
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y, _ in pts)
    marks = f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    for x, y, _ in pts:
        marks += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" stroke="{color}" stroke-width="2"/>'
    ex, ey, ev = pts[-1]
    marks += f'<text x="{ex+7:.1f}" y="{ey+3:.1f}" font-size="10" font-weight="700" fill="{color}">{name} {ev}</text>'
    return marks
xlab = "".join(f'<text x="{LPL+(LW-LPL-LPR)*(i/(len(years)-1)):.1f}" y="{LH-LPB+13:.1f}" font-size="9.5" fill="{B["muted"]}" text-anchor="middle">{y}</text>' for i, y in enumerate(years))
linesvg = (f'<svg viewBox="0 0 {LW} {LH}" width="100%" role="img" aria-label="Trend by year">'
           f'<line x1="{LPL}" y1="{LH-LPB}" x2="{LW-LPR}" y2="{LH-LPB}" stroke="{B["hair"]}" stroke-width="1.5"/>'
           f'{lgrid}{xlab}{series_svg(s1, CAT[0], "Girls")}{series_svg(s2, CAT[1], "Boys")}</svg>')

body = f'''
{swrow("Sequential — UNICEF Blue (magnitude)", SEQ)}
{swrow("Categorical — series (identity, direct-labelled)", CAT)}
<div style="display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px">
  <div>
    <div style="font-size:12.5px;font-weight:700;margin-bottom:8px">Coverage by region <span style="color:{B['muted']};font-weight:400">— % reached</span></div>
    {barsvg}
  </div>
  <div>
    <div style="font-size:12.5px;font-weight:700;margin-bottom:8px">Coverage trend <span style="color:{B['muted']};font-weight:400">— by year</span></div>
    {linesvg}
  </div>
</div>
<div style="font-size:11.5px;color:{B['muted']};margin-top:14px">Single measure → sequential UNICEF Blue. Categories → the validated series set, always direct-labelled (never colour alone). One y-axis; recessive grid. Tints/steps are permitted in data-viz (Brand Book p.53).</div>'''
files.append(("dataviz", "charts-and-palette.html",
              page("Data visualization", "Charts & palette", "Sequential ramp · series colours · bar · line",
                   body, "Data visualization — Charts", "UNICEF Blue leads; a validated series set covers categories, direct-labelled.")))

# ---------------------------------------------------------------------------
# LAYOUTS — Slide layouts (16:9 previews) and document cover
# ---------------------------------------------------------------------------
def slide_frame(inner, ratio=56.25):
    return (f'<div style="position:relative;width:100%;padding-top:{ratio}%;'
            f'border:1px solid {B["hair"]};border-radius:12px;overflow:hidden;box-shadow:0 8px 24px -12px rgba(0,74,120,.25)">'
            f'<div style="position:absolute;inset:0">{inner}</div></div>')

stmt = f'<span style="font-weight:400">for every child,</span> <span style="font-weight:700">{{kw}}</span>'
title_slide = slide_frame(f'''<div style="width:100%;height:100%;background:{B['blue']};color:#fff;padding:9% 8%;display:flex;flex-direction:column;justify-content:center">
  <div style="font-size:2.4vw;font-weight:700;letter-spacing:-.02em;line-height:1.05">Every child deserves<br>a fair chance</div>
  <div style="font-size:1.2vw;margin-top:2.5%;opacity:.9">Subtitle · author · date</div>
  <div style="position:absolute;left:8%;bottom:7%;font-size:1.1vw;text-transform:lowercase">{stmt.format(kw="every right")}</div>
  <div style="position:absolute;right:7%;top:8%;font-size:1vw;font-weight:700;border:1.5px solid rgba(255,255,255,.6);padding:.5% 1.5%;border-radius:3px">UNICEF ▸ logo</div>
</div>''')
section_slide = slide_frame(f'''<div style="width:100%;height:100%;background:#fff;padding:0 8%;display:flex;align-items:center;position:relative">
  <div style="position:absolute;left:0;top:34%;bottom:34%;width:2.2%;background:{B['blue']};border-radius:0 3px 3px 0"></div>
  <div style="font-size:2.2vw;font-weight:700;color:{B['blue']};letter-spacing:-.02em">01 — Our approach</div>
  <div style="position:absolute;left:8%;bottom:7%;font-size:1.1vw;text-transform:lowercase;color:{B['blue']}">{stmt.format(kw="opportunity")}</div>
</div>''')
content_slide = slide_frame(f'''<div style="width:100%;height:100%;background:#fff;padding:6% 8%;position:relative">
  <div style="font-size:1.7vw;font-weight:700;color:{B['blue']}">Content heading</div>
  <div style="width:16%;height:2.5px;background:{B['blue']};margin:1.6% 0 3%"></div>
  <div style="font-size:1.15vw;color:{B['ink']};line-height:1.7">
    • Body text in Noto Sans Regular, kept uncluttered.<br>
    • UNICEF Blue stays the dominant colour.<br>
    • Accents support, never overpower.</div>
  <div style="position:absolute;left:8%;bottom:7%;font-size:1vw;text-transform:lowercase;color:{B['blue']}">{stmt.format(kw="education")}</div>
</div>''')
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
  <div><div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Title (16:9)</div>{title_slide}</div>
  <div><div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Section divider</div>{section_slide}</div>
  <div style="grid-column:1/-1"><div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Content</div>{content_slide}</div>
</div>'''
files.append(("layouts", "slides.html",
              page("Layouts", "Slide layouts", "Title · section · content (16:9)",
                   body, "Layouts — Slides", "The PowerPoint template as previews: blue cover, ruled section, clean content.")))

# document cover (A4 portrait)
cover = f'''<div style="position:relative;width:64%;margin:0 auto;padding-top:90%;border:1px solid {B['hair']};border-radius:8px;overflow:hidden;box-shadow:0 10px 30px -14px rgba(0,74,120,.3)">
  <div style="position:absolute;inset:0;background:#fff;display:flex;flex-direction:column">
    <div style="height:52%;background:{B['blue']};position:relative">
      <div style="position:absolute;right:8%;top:7%;font-size:11px;font-weight:700;color:#fff;border:1.5px solid rgba(255,255,255,.6);padding:4px 8px;border-radius:3px">UNICEF ▸ logo</div>
    </div>
    <div style="padding:8% 9%;flex:1;display:flex;flex-direction:column">
      <div style="font-size:15px;font-weight:700;color:{B['blue']};letter-spacing:-.01em;line-height:1.15">The State of the<br>World's Children</div>
      <div style="font-size:11px;color:{B['muted']};margin-top:6px">Flagship report · 2026</div>
      <div style="margin-top:auto;font-size:11px;text-transform:lowercase;color:{B['blue']}"><span style="font-weight:400">for every child,</span> <span style="font-weight:700">a future</span></div>
    </div>
  </div>
</div>'''
body = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start">
  {cover}
  <div style="padding-top:8px">
    <div style="font-size:14px;font-weight:700;margin-bottom:10px">Cover anatomy</div>
    <ul style="margin:0;padding:0;list-style:none;display:grid;gap:10px">
      <li style="font-size:13.5px;padding-left:18px;position:relative"><span style="position:absolute;left:0;top:7px;width:7px;height:7px;border-radius:50%;background:{B['blue']}"></span>Logo (with container) top or bottom of the cover.</li>
      <li style="font-size:13.5px;padding-left:18px;position:relative"><span style="position:absolute;left:0;top:7px;width:7px;height:7px;border-radius:50%;background:{B['blue']}"></span>Single strong photograph, ideally full-bleed.</li>
      <li style="font-size:13.5px;padding-left:18px;position:relative"><span style="position:absolute;left:0;top:7px;width:7px;height:7px;border-radius:50%;background:{B['blue']}"></span>Title / subtitle in Noto Sans; add a cyan or white bar if contrast is low.</li>
      <li style="font-size:13.5px;padding-left:18px;position:relative"><span style="position:absolute;left:0;top:7px;width:7px;height:7px;border-radius:50%;background:{B['blue']}"></span>Back cover is UNICEF Blue with logo + contact info.</li>
    </ul>
    <div style="font-size:11.5px;color:{B['muted']};margin-top:14px"><i>Brand Book 4.0, p.72–73. Logo shown as a placeholder — use official WeShare assets.</i></div>
  </div>
</div>'''
files.append(("layouts", "document-cover.html",
              page("Layouts", "Document cover", "Publication / report cover",
                   body, "Layouts — Document cover", "Word & publication cover: blue field, single photo, Noto Sans title.")))

# ---------------------------------------------------------------------------
# IMAGERY — Photography treatment  (no real/AI photos: labelled placeholders +
# composition and rules, per Brand Book p.64-67)
# ---------------------------------------------------------------------------
def photo_ph(icon_inner, label, sub):
    return f'''<div style="border-radius:12px;overflow:hidden;border:1px solid {B['hair']}">
      <div style="aspect-ratio:4/3;background:linear-gradient(135deg,{B['ltcyan']},{B['blue']});display:flex;align-items:center;justify-content:center;position:relative">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="opacity:.85">{icon_inner}</svg>
        <span style="position:absolute;left:9px;bottom:8px;font-size:9px;color:#fff;background:rgba(0,0,0,.32);padding:2px 6px;border-radius:4px">placeholder</span>
      </div>
      <div style="padding:10px 12px;background:{B['panel']}">
        <div style="font-weight:700;font-size:13px">{label}</div>
        <div style="font-size:11.5px;color:{B['muted']};margin-top:2px">{sub}</div>
      </div></div>'''
I_CHILD = '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>'
I_ACTION = '<path d="M20 7h-4l-2-2H8L6 7H2v13h18z"/><circle cx="11" cy="13" r="3.5"/>'
I_LIFT = '<circle cx="12" cy="5" r="2.4"/><path d="M8 21l1.5-6L7 12l2-3h6l2 3-2.5 3L16 21"/>'
dodont = lambda items, c: "".join(f'<li style="font-size:12.5px;padding-left:16px;position:relative;margin-bottom:7px;list-style:none"><span style="position:absolute;left:0;top:6px;width:6px;height:6px;border-radius:50%;background:{c}"></span>{t}</li>' for t in items)
body = f'''
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
  {photo_ph(I_CHILD, "Child-focused", "Direct gaze into the camera; conveys hope.")}
  {photo_ph(I_ACTION, "UNICEF in action", "Staff or supplies showing our role; caption it.")}
  {photo_ph(I_LIFT, "Caregiver lifting a child", "The emblem gesture — security and joy.")}
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px">
  <div style="border:1px solid {B['hair']};border-radius:12px;padding:16px 18px;background:{B['panel']}">
    <div style="font-size:13px;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:8px"><span style="width:20px;height:20px;border-radius:50%;background:{B['green']};color:#fff;display:grid;place-items:center;font-size:12px">✓</span>Do</div>
    <ul style="margin:0;padding:0">{dodont(["Obtain informed consent; use written releases.","Credit every photo — ©UNICEF/UN062441/LeMoyne.","Reflect real diversity; represent people as equals.","Cropping and flipping are fine (if no text in frame).","Keep captions consistent with the photo's content."], B['green'])}</ul>
  </div>
  <div style="border:1px solid {B['hair']};border-radius:12px;padding:16px 18px;background:{B['panel']}">
    <div style="font-size:13px;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:8px"><span style="width:20px;height:20px;border-radius:50%;background:{B['red']};color:#fff;display:grid;place-items:center;font-size:12px">✕</span>Don't</div>
    <ul style="margin:0;padding:0">{dodont(["No synthetic or AI-generated images — ever.","No generative fill, manipulation, or composites.","Don't add/remove content or change the meaning.","Never reveal identities of children at risk.","No commercial use of UNICEF photography."], B['red'])}</ul>
  </div>
</div>
<div style="margin-top:14px;padding:11px 15px;border-radius:10px;background:{B['panel2']};border-left:4px solid {B['blue']};font-size:12px">
Credit-line format: <code style="font-family:inherit;font-weight:700;background:#fff;padding:1px 6px;border-radius:4px;border:1px solid {B['hair']}">©UNICEF/UN062441/LeMoyne</code> &nbsp;·&nbsp; <i>Brand Book 4.0, p.64–67. Frames are placeholders — source real imagery from the WeShare Photography Guidelines.</i>
</div>'''
files.append(("imagery", "photography.html",
              page("Imagery", "Photography", "Three image types · rules · credit line",
                   body, "Imagery — Photography", "Children, direct gaze, dignity — and never AI-generated or manipulated.")))

# ---------------------------------------------------------------------------
# IMAGERY — Iconography  (single-colour line icons, consistent stroke)
# ---------------------------------------------------------------------------
ICONS = [
    ("Health", '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.7-7.5 1.1-1.1a5.5 5.5 0 0 0 0-7.8z"/>'),
    ("Education", '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1 3 3 6 3s6-2 6-3v-5"/>'),
    ("Water", '<path d="M12 2.7l5.7 6.4a8 8 0 1 1-11.4 0z"/>'),
    ("Nutrition", '<path d="M12 8c0-3 2-5 5-5 0 3-2 5-5 5z"/><path d="M12 8c-1.7-1.7-4.5-1.7-6 .3C4 11 5 17 8 20c1.2 1.2 2.8 1.2 4 0 1.2 1.2 2.8 1.2 4 0 3-3 4-9 2-11.7-1.5-2-4.3-2-6-.3z"/>'),
    ("Protection", '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
    ("Every child", '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>'),
    ("Vaccines", '<path d="M18 2l4 4"/><path d="M15 5l4 4"/><path d="M16.5 6.5L8 15l-2 4-2-2 4-2 8.5-8.5"/><path d="M9 11l2 2"/>'),
    ("Global", '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19"/><path d="M12 2.5a15 15 0 0 1 0 19a15 15 0 0 1 0-19z"/>'),
    ("Impact", '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'),
    ("Hope", '<circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
]
def icon_tile(name, inner, color=B["blue"], bg="#fff"):
    return f'''<div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 8px;border:1px solid {B['hair']};border-radius:12px;background:{bg}">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>
      <span style="font-size:11px;color:{('#fff' if bg!='#fff' else B['muted'])}">{name}</span></div>'''
grid_icons = "".join(icon_tile(n, i) for n, i in ICONS)
onblue = "".join(icon_tile(n, i, color="#fff", bg=B["blue"]) for n, i in ICONS[:5])
body = f'''
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">{grid_icons}</div>
<div style="margin-top:18px;font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">On UNICEF Blue</div>
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">{onblue}</div>
<div style="margin-top:16px;padding:11px 15px;border-radius:10px;background:{B['panel2']};border-left:4px solid {B['blue']};font-size:12px">
Single-colour line icons — consistent <b>1.75</b> stroke, rounded caps, 24-unit grid. UNICEF Blue on light; white on blue. A full official set is on WeShare; these illustrate the treatment.
</div>'''
files.append(("imagery", "iconography.html",
              page("Imagery", "Iconography", "Single-colour line icons · consistent stroke",
                   body, "Imagery — Iconography", "One weight, one colour, rounded caps — calm and consistent.")))

# ---------------------------------------------------------------------------
# COMPONENTS — Navigation & header
# ---------------------------------------------------------------------------
def navlink(text, active=False):
    if active:
        return f'<span style="font-size:13.5px;font-weight:700;color:#fff;padding-bottom:3px;border-bottom:2px solid #fff">{text}</span>'
    return f'<span style="font-size:13.5px;color:rgba(255,255,255,.85)">{text}</span>'
def tab(text, active=False):
    if active:
        return f'<span style="font-size:13.5px;font-weight:700;color:{B["blue"]};padding:0 2px 10px;border-bottom:2.5px solid {B["blue"]}">{text}</span>'
    return f'<span style="font-size:13.5px;color:{B["muted"]};padding:0 2px 10px">{text}</span>'
body = f'''
<div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Primary header</div>
<div style="background:{B['blue']};border-radius:12px 12px 0 0;padding:0 20px;height:60px;display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:28px">
    <span style="font-size:13px;font-weight:700;color:#fff;border:1.5px solid rgba(255,255,255,.6);padding:5px 9px;border-radius:4px">UNICEF ▸ logo</span>
    <div style="display:flex;gap:22px;align-items:center">{navlink("Our work", True)}{navlink("Stories")}{navlink("Research")}{navlink("About")}</div>
  </div>
  <button style="font-family:inherit;font-size:13px;font-weight:700;background:#fff;color:{B['blueInk']};border:none;padding:9px 18px;border-radius:7px;cursor:pointer">Donate</button>
</div>
<div style="border:1px solid {B['hair']};border-top:none;border-radius:0 0 12px 12px;padding:0 20px;background:#fff">
  <div style="display:flex;gap:26px;padding-top:14px">{tab("Overview", True)}{tab("Programmes")}{tab("Results")}{tab("Reports")}</div>
</div>

<div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin:24px 0 8px">Breadcrumb</div>
<div style="font-size:13px;color:{B['muted']}">Home <span style="opacity:.6">›</span> Our work <span style="opacity:.6">›</span> <span style="color:{B['blue']};font-weight:700">Nutrition</span></div>

<div style="font-size:12px;font-weight:700;color:{B['muted']};text-transform:uppercase;letter-spacing:.08em;margin:24px 0 8px">Sidebar navigation</div>
<div style="max-width:260px;border:1px solid {B['hair']};border-radius:12px;overflow:hidden">
  <div style="padding:11px 16px;font-size:13.5px;font-weight:700;color:{B['blue']};background:{B['panel2']};border-left:3px solid {B['blue']}">Overview</div>
  <div style="padding:11px 16px;font-size:13.5px;color:{B['ink']};border-top:1px solid {B['hair']}">Health &amp; nutrition</div>
  <div style="padding:11px 16px;font-size:13.5px;color:{B['ink']};border-top:1px solid {B['hair']}">Education</div>
  <div style="padding:11px 16px;font-size:13.5px;color:{B['ink']};border-top:1px solid {B['hair']}">Child protection</div>
</div>
<div style="margin-top:16px;font-size:11.5px;color:{B['muted']}">Header uses UNICEF Blue as the dominant field; the active state is a solid white/blue underline. Donate CTA is white with Accent Blue text (AA ✓).</div>'''
files.append(("components", "navigation.html",
              page("Components", "Navigation & header", "Header · tabs · breadcrumb · sidebar",
                   body, "Components — Navigation", "Wayfinding built on the dominant blue field, with clear active states.")))

# ---------------------------------------------------------------------------
written = [write(g, f, h) for g, f, h in files]
for w in written:
    print("  wrote", w)
print(f"Done — {len(written)} cards into {os.path.relpath(OUT, HERE)}")
