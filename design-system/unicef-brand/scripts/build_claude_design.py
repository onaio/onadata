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
written = [write(g, f, h) for g, f, h in files]
for w in written:
    print("  wrote", w)
print(f"Done — {len(written)} cards into {os.path.relpath(OUT, HERE)}")
