#!/usr/bin/env python3
"""
build_pdf.py — Generate a magazine-quality A4 PDF portfolio from the website content.

Pipeline (deterministic):
  1. Extract a poster frame from each project's time-lapse video (ffmpeg).
  2. Generate a print-specific HTML document built around the A4 page (@page).
  3. Render it to PDF with headless Chromium (Playwright).

Output: "Alexander Brown - Portfolio.pdf" in the site root.

Usage:
  python3 print/build_pdf.py            # full build (reuses existing posters)
  python3 print/build_pdf.py --force    # re-extract poster frames

Intermediates (regenerable, safe to delete):
  print/posters/*.jpg          poster frames pulled from the time-lapse videos
  print/portfolio-print.html   the generated print document
"""

import html
import math
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
PRINT_DIR = Path(__file__).resolve().parent
ROOT = PRINT_DIR.parent
POSTER_DIR = PRINT_DIR / "posters"
CACHE_DIR = PRINT_DIR / "cache"
HTML_OUT = PRINT_DIR / "portfolio-print.html"
PDF_OUT = ROOT / "Alexander Brown - Portfolio.pdf"

IMAGES_PER_GALLERY_PAGE = 6          # 2 columns x 3 rows
COVER_SLUG = "perch"                 # which project's poster frames the cover
GALLERY_PX = 1300                    # longest edge for gallery plates
GALLERY_Q = 80                       # JPEG quality for gallery plates

# Populated by optimize_images(): {source relative path -> cached JPEG Path}
OPT: dict = {}

# ─────────────────────────────────────────────────────────────────────────────
# Content — transcribed from the live project pages
# ─────────────────────────────────────────────────────────────────────────────
PROJECTS = [
    {
        "slug": "pivot",
        "title": "Pivot",
        "year": "2016",
        "location": "London, UK",
        "type": "Collaboration",
        "video": "Assets/Pivot/HG time lapse.mp4",
        "text": [
            "Designed for a young family of four, this project transforms the ground and "
            "semi-basement levels of a London terrace into a brighter, more connected home "
            "centred around everyday family life. The brief was to turn the lower ground "
            "floor into a place the family actually wanted to spend time in — not just a "
            "secondary space, but the heart of the house. A glazed opening was introduced "
            "within the existing structure, pulling daylight deep into the plan and creating "
            "a generous double-height volume.",
            "A stepped sequence from the entrance leads down past a half-level library into "
            "a new kitchen and dining space that opens directly onto the garden. The result "
            "is a home that feels lighter, more open and more intuitive to move through, "
            "with the basement no longer hidden but fully integrated into daily life.",
        ],
        "images": [
            ("Assets/Pivot/HG light model.jpg", "Light model"),
            ("Assets/Pivot/HG Material 2.webp", "Material study"),
            ("Assets/Pivot/HG section.webp", "Section"),
            ("Assets/Pivot/HG plans.webp", "Floor plans"),
            ("Assets/Pivot/HG photo internal window.jpg", "Interior — window"),
            ("Assets/Pivot/HG photo internal glass.jpg", "Interior — glazed strip"),
            ("Assets/Pivot/HG photo rear evening.jpg", "Rear exterior — evening"),
            ("Assets/Pivot/HG photo internal library.jpg", "Interior — library"),
        ],
    },
    {
        "slug": "louvre",
        "title": "Louvre",
        "year": "2016",
        "location": "London, UK",
        "type": "Collaboration",
        "video": "Assets/Louvre/B Time Lapse.mp4",
        "text": [
            "This project introduces a new-build home in west London, following the "
            "completion of a neighbouring extension.",
            "The house reinterprets the traditional London brick typology, combining a "
            "composed street-facing façade with a lighter, more open rear. Towards the "
            "garden, the building transitions into a glass and steel structure, with timber "
            "louvres providing privacy within the dense urban setting while allowing "
            "generous daylight inside. A series of lower ground spaces accommodate more "
            "private functions, including a cinema room and a concealed car lift for "
            "multiple vehicles. The result is a contemporary home that builds on familiar "
            "forms while introducing a more refined and modern spatial experience.",
        ],
        "images": [
            ("Assets/Louvre/B Elevation Existing.webp", "Elevation — existing"),
            ("Assets/Louvre/B Concept.webp", "Concept"),
            ("Assets/Louvre/B Model Context.webp", "Model — context"),
            ("Assets/Louvre/B Elevation Proposed.webp", "Elevation — proposed"),
            ("Assets/Louvre/B Section.webp", "Section"),
            ("Assets/Louvre/B Axo.webp", "Axonometric"),
            ("Assets/Louvre/B Model Rear.webp", "Model — rear"),
            ("Assets/Louvre/B Detail 1.webp", "Detail"),
            ("Assets/Louvre/B Detail 2.webp", "Detail"),
            ("Assets/Louvre/B Photo Internal Living.jpg", "Internal — living"),
            ("Assets/Louvre/B Photo Internal Kitchen.jpg", "Internal — kitchen"),
            ("Assets/Louvre/B Photo Internal Kitchen 2.jpg", "Internal — kitchen"),
            ("Assets/Louvre/B Photo Front.jpg", "Front elevation"),
        ],
    },
    {
        "slug": "krets",
        "title": "Krets",
        "year": "2019",
        "location": "Limhamn, Sweden",
        "type": "Individual",
        "video": "Assets/Krets/Krets Time Lapse.mp4",
        "text": [
            "Krets (Orbit) explores how architecture can respond to the growing condition of "
            "urban loneliness, particularly among young adults living alone.",
            "Designed for people navigating independent city life, often living alone with "
            "limited opportunities for everyday interaction, the project questions the way "
            "contemporary housing prioritises privacy and efficiency at the expense of "
            "everyday human interaction.",
            "Drawing on research into wellbeing and social integration, the proposal "
            "positions architecture not as a cure but as a framework that can support "
            "healthier patterns of living. Studies consistently show that strong "
            "relationships are central to long-term wellbeing, yet current residential "
            "models offer few opportunities for connection beyond the private unit.",
            "Krets reconsiders the role of circulation within the apartment building. "
            "Rather than treating it as a purely functional necessity, the project "
            "transforms movement into a shared spatial experience. A continuous looping "
            "core organises the building, allowing residents to see, pass, and gradually "
            "recognise one another through daily routines.",
            "Responding to Limhamn's proximity to Malmö and its strong cycling culture, "
            "the loop is designed as a gentle continuous ramp that can be used on foot or "
            "by bicycle. This introduces a more active and slightly playful dimension to "
            "daily movement, embedding moments of encounter within routine journeys "
            "through the building.",
            "Shared programmes such as workspaces, activity rooms and informal communal "
            "areas are positioned along this route, allowing interaction to develop "
            "naturally rather than being imposed. The project proposes a shift from housing "
            "as a collection of isolated units towards housing as a social environment — "
            "exploring how the spaces between can support connection, wellbeing and a more "
            "resilient form of everyday urban life.",
        ],
        "images": [
            ("Assets/Krets/P1 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/P2 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/P3 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/P4 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/P5 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/P6 Krets Slideshow.jpg", "Visualisation"),
            ("Assets/Krets/Krets Photo Existing Hall 2.webp", "Existing hall"),
            ("Assets/Krets/Krets Concept.webp", "Concept"),
            ("Assets/Krets/Krets Elevation.webp", "Elevation"),
            ("Assets/Krets/Krets Axo.jpg", "Axonometric"),
            ("Assets/Krets/Krets Section.jpg", "Section"),
            ("Assets/Krets/Krets Section Killer.webp", "Section perspective"),
        ],
    },
    {
        "slug": "perch",
        "title": "Perch",
        "year": "2020",
        "location": "Båstad, Sweden",
        "type": "Individual",
        "video": "Assets/Perch/L Time Lapse.mp4",
        "text": [
            "Designed for a Stockholm-based entrepreneur, this project reworks a modest "
            "1960s villa on the ås in Båstad into a calm retreat overlooking the "
            "Skåne landscape and the sea. The approach was to build on what already "
            "existed, using a restrained material palette to embed the house within its "
            "setting. The volume was lifted to capture views, with the upper floor set back "
            "behind evergreen pines to form a sheltered south-facing terrace and a more "
            "private outlook towards the forest.",
            "The layout is organised around a clear vertical core, shaped by the "
            "requirement for the upper level to function as a fully accessible apartment in "
            "the future. This results in an inverted arrangement, with the main living "
            "spaces positioned above. Arrival is through a carport beneath the house, "
            "allowing the building to sit lightly within the landscape and reinforcing its "
            "role as a quiet, elevated retreat.",
        ],
        "images": [
            ("Assets/Perch/L Front 2 Existing.jpg", "Existing building"),
            ("Assets/Perch/L Arial Existing Photo.jpg", "Aerial — existing"),
            ("Assets/Perch/L Concept.webp", "Concept"),
            ("Assets/Perch/Villa_Analysis_June_0900.webp", "Sun study — 09:00"),
            ("Assets/Perch/Villa_Analysis_June_1200.webp", "Sun study — 12:00"),
            ("Assets/Perch/Villa_Analysis_June_1500.webp", "Sun study — 15:00"),
            ("Assets/Perch/L Site Raise G.webp", "Site strategy — raise"),
            ("Assets/Perch/L Site Push G.webp", "Site strategy — push"),
            ("Assets/Perch/L Axo Concept G.webp", "Axonometric concept"),
            ("Assets/Perch/L Model.jpg", "Architectural model"),
            ("Assets/Perch/L Plans G.webp", "Plans"),
            ("Assets/Perch/L Hidden External.jpg", "Exterior"),
            ("Assets/Perch/L Front External.jpg", "Front exterior"),
            ("Assets/Perch/L Living Internal.jpg", "Living interior"),
            ("Assets/Perch/L Sauna Internal.jpg", "Sauna interior"),
        ],
    },
    {
        "slug": "mantle",
        "title": "Mantle",
        "year": "2020",
        "location": "Halmstad, Sweden",
        "type": "Individual",
        "video": "Assets/Mantle/Hv Time Lapse.mp4",
        "text": [
            "Designed for a couple building a home together after finding love again, this "
            "project reworks a 1920s mansard-roofed villa in central Halmstad under strict "
            "planning constraints. The approach establishes a clear distinction between old "
            "and new, preserving the street-facing elevations while introducing carefully "
            "considered interventions elsewhere. A new entrance is subtly repositioned and "
            "treated as secondary to comply with regulations.",
            "Internally, the layout is restructured to feel more open and intuitive, with "
            "slight level changes used to define different zones within the home. The "
            "design draws on a restrained material palette and strengthens the connection "
            "to the south-west facing garden, bringing light and views deeper into the "
            "plan. The result is a sensitive transformation that balances regulatory "
            "constraints with a more generous and contemporary way of living.",
        ],
        "images": [
            ("Assets/Mantle/Hv Photo Existing.webp", "Existing building"),
            ("Assets/Mantle/Hv Site Analysis.webp", "Site analysis"),
            ("Assets/Mantle/Hv Concept Sketch.webp", "Concept sketch"),
            ("Assets/Mantle/Hv Plans.webp", "Plans"),
            ("Assets/Mantle/Hv Materials.jpg", "Materials"),
            ("Assets/Mantle/Hv Model.jpg", "Model"),
            ("Assets/Mantle/Hv External Front.jpg", "External — front"),
            ("Assets/Mantle/Hv External Rear.jpg", "External — rear"),
        ],
    },
    {
        "slug": "grain",
        "title": "Grain",
        "year": "2021",
        "location": "Malmö, Sweden",
        "type": "Individual",
        "video": "Assets/Grain/K Time Lapse.mp4",
        "text": [
            "Designed as both a personal project and a prototype for future homes, this "
            "compact Malmö apartment reworks a typical 1.5-room layout to better suit "
            "young professionals. The approach focused on small, precise interventions to "
            "unlock the potential of the existing plan. The kitchen was relocated to allow "
            "for a separate bedroom, creating a clearer distinction between living and "
            "private spaces within a limited footprint.",
            "The bathroom was reconfigured into a compact, efficient shower room with "
            "integrated laundry, while a series of subtle spatial adjustments improve "
            "everyday use. A sliding bedroom door reduces wasted space, the bathroom door "
            "helps define a small entrance zone, and additional storage is carefully "
            "integrated into the plan. The result is a modest but highly liveable "
            "apartment, where careful planning and restrained detailing significantly "
            "improve the quality of daily life.",
        ],
        "images": [
            ("Assets/Grain/K Concept.webp", "Concept"),
            ("Assets/Grain/K Plan Existing.webp", "Existing plan"),
            ("Assets/Grain/K Plan Demo .webp", "Demolition plan"),
            ("Assets/Grain/K Plan Proposed.webp", "Proposed plan"),
            ("Assets/Grain/K Axo.webp", "Axonometric"),
            ("Assets/Grain/K Materials.webp", "Materials"),
            ("Assets/Grain/K Elevations Bathroom.webp", "Bathroom elevations"),
            ("Assets/Grain/K Elevations Kitchen.webp", "Kitchen elevations"),
            ("Assets/Grain/K Photo Demo.jpg", "Demolition"),
            ("Assets/Grain/K Photo Demo 2.jpg", "Demolition"),
            ("Assets/Grain/K Photo AB Building 2.jpg", "Building"),
            ("Assets/Grain/K Photo AB Building 3.jpg", "Building"),
            ("Assets/Grain/K Photo Hall.jpg", "Hall"),
            ("Assets/Grain/K Photo Kitchen.jpg", "Kitchen"),
            ("Assets/Grain/K Photo Kitchen 2.jpg", "Kitchen"),
            ("Assets/Grain/K Photo Shower.jpg", "Shower room"),
            ("Assets/Grain/K Photo Bedroom.jpg", "Bedroom"),
            ("Assets/Grain/K Photo Bathroom.jpg", "Bathroom"),
            ("Assets/Grain/K Photo Bathroom 2.jpg", "Bathroom"),
        ],
    },
    {
        "slug": "hearth",
        "title": "Hearth",
        "year": "2021",
        "location": "London, UK",
        "type": "Individual",
        "video": "Assets/Hearth/S Time Lapse.mp4",
        "text": [
            "Designed for a young couple expecting their first child, this project "
            "transforms a terraced house in Balham to create a light-filled family space "
            "at the heart of the home.",
            "The brief centred on forming a generous kitchen and dining area where everyday "
            "life could unfold together. The design takes a soft, minimal approach, with "
            "careful attention to proportion and detailing to create a calm and cohesive "
            "interior.",
            "A key move was the refinement of the roof structure, developed to minimise its "
            "perceived thickness in elevation. The roof line is pulled forward to terminate "
            "before the glazing, creating a crisp, uninterrupted edge that enhances the "
            "sense of openness both internally and towards the garden. The result is a "
            "modern yet welcoming home, where restrained detailing and natural light "
            "support daily family life.",
        ],
        "images": [
            ("Assets/Hearth/S Model.webp", "Architectural model"),
            ("Assets/Hearth/S Materials.webp", "Materials"),
            ("Assets/Hearth/S Plan Existing Ground.webp", "Existing ground floor plan"),
            ("Assets/Hearth/S Elevation Existing.webp", "Existing elevation"),
            ("Assets/Hearth/S Elevation Proposed.webp", "Proposed elevation"),
            ("Assets/Hearth/S Section.webp", "Section"),
            ("Assets/Hearth/S Plan Proposed.webp", "Proposed plan"),
            ("Assets/Hearth/S Plan Electrical.webp", "Electrical plan"),
            ("Assets/Hearth/S Plan Loft.webp", "Loft plan"),
            ("Assets/Hearth/S External.jpg", "External view"),
            ("Assets/Hearth/S Internal.jpg", "Internal view"),
        ],
    },
    {
        "slug": "seam",
        "title": "Seam",
        "year": "2022",
        "location": "Malmö, Sweden",
        "type": "Individual",
        "video": "Assets/Seam/N Time Lapse.mp4",
        "text": [
            "Designed as a continuation of an ongoing series of small-scale renovations, "
            "this project reworks a 1930s two-room apartment in Malmö as a prototype for "
            "future homes aimed at young professionals. The design focuses on simplifying "
            "and opening up the existing layout. By removing the kitchen wall and internal "
            "doors, the plan is restructured into a more generous kitchen and dining space "
            "that becomes the centre of the home.",
            "A subtle concrete strip is cast into the timber floor to trace the line of the "
            "former wall, retaining a quiet reference to the apartment's original "
            "organisation. Elsewhere, underused areas are reconsidered, with the typical "
            "halva reimagined as a more intimate living nook leading into a larger bedroom "
            "with integrated storage. The result is a more coherent and liveable apartment, "
            "where a series of precise interventions reshape the way the space is used "
            "without increasing its footprint.",
        ],
        "images": [
            ("Assets/Seam/N Plan Existing.webp", "Existing plan"),
            ("Assets/Seam/N Concept.webp", "Concept"),
            ("Assets/Seam/N Plan Existing 2.webp", "Existing plan"),
            ("Assets/Seam/N Plans Proposed.webp", "Proposed plans"),
            ("Assets/Seam/N Materials.webp", "Materials"),
            ("Assets/Seam/N Photo Building.webp", "Building"),
            ("Assets/Seam/N Photo Building 2.webp", "Building"),
            ("Assets/Seam/N Photo Hall.jpg", "Hall"),
            ("Assets/Seam/N Photo Kitchen.jpg", "Kitchen"),
            ("Assets/Seam/N Photo Kitchen 2.jpg", "Kitchen"),
            ("Assets/Seam/N Photo Kitchen 3.jpg", "Kitchen"),
            ("Assets/Seam/N Photo Materals 2.jpeg", "Material detail"),
            ("Assets/Seam/N Photo Bedroom.jpg", "Bedroom"),
        ],
    },
]

ABOUT = {
    "name": "Alexander Brown",
    "credential": "SAR · Sveriges Arkitekter",
    "photo": "Assets/AWRB/Profile Photo.jpg",
    "bio": [
        "Architecture has been an adventure, taking me to new cities, countries, and "
        "experiences. At its heart, I've always seen it as being about people: "
        "understanding, learning, and working together to create something better.",
        "I've been lucky to work in design-led studios in London and Sweden, on projects "
        "across all stages from concept through to construction. Outside of work, I'm "
        "active and social. I enjoy most sports, especially football, and like sharing "
        "new ideas with friends over a drink.",
    ],
    "skills": [
        ("Vectorworks", 0.90),
        ("AutoCAD", 0.82),
        ("SketchUp", 0.82),
        ("Enscape", 0.75),
        ("Affinity", 0.68),
        ("Adobe Suite", 0.62),
        ("Revit", 0.52),
    ],
    "timeline": [
        {
            "dates": "2021 — 2026",
            "org": "Freelance Architect",
            "location": "Remote · UK / Sweden",
            "role": "Arkitekt SAR/MSA",
            "desc": [
                "Collaborating with several practices and private clients, contributing to "
                "projects across all stages from early concept and planning through to "
                "tender and construction.",
                "Alongside this, I undertook two apartment renovations in Malmö, and for "
                "the past two years have worked closely with an architect in London, "
                "playing a key role in establishing a new practice while delivering "
                "bespoke residential projects across the city.",
            ],
        },
        {
            "dates": "2020 — 2021",
            "org": "Krook & Tjäder",
            "location": "Halmstad, Sweden",
            "role": "Arkitekt SAR/MSA",
            "desc": [
                "Worked with one of Sweden's largest architectural practices, based in "
                "their close-knit Halmstad office. My work focused mainly on the concept "
                "and planning stages, from large apartment developments to small house "
                "extensions and private villas.",
                "From preparing bygglov submissions to learning Swedish standards, I "
                "gained a strong understanding of how practice operates in Sweden.",
            ],
        },
        {
            "dates": "2017 — 2019",
            "org": "Lunds Universitet",
            "location": "Lund, Sweden",
            "role": "Master of Architecture",
            "desc": [
                "Studied in Scandinavia to better understand the Swedish design process. "
                "Studio work shifted my perspective from the scale of the house to that "
                "of the city, and taught me to design collaboratively.",
                "The programme concluded with my master's thesis, exploring the "
                "relationship between psychology and architecture through human-centred "
                "questions in design.",
            ],
        },
        {
            "dates": "2016 — 2019",
            "org": "Trace Architects",
            "location": "London, UK",
            "role": "Part I Architectural Assistant",
            "desc": [
                "A small design-led residential studio in London, giving me exposure to "
                "the full breadth of UK practice across RIBA stages 1 to 5 — from early "
                "client meetings through to technical packages and work on site.",
                "I worked closely with clients, planning consultants, building control "
                "officers, structural engineers and contractors, reinforcing the "
                "importance of clear communication and teamwork.",
            ],
        },
        {
            "dates": "2012 — 2015",
            "org": "University of Liverpool",
            "location": "Liverpool, UK",
            "role": "Bachelor of Architecture (Hons) · 2:1",
            "desc": [
                "Studies focused on individual design development and hand drafting, "
                "alongside architectural history and theory, structures, environmental "
                "science and practice management.",
                "Culminated in my degree project: the design of a transport hub and "
                "underground station in Liverpool's Baltic Triangle.",
            ],
        },
        {
            "dates": "2004 — 2011",
            "org": "Kimbolton School",
            "location": "Cambridgeshire, UK",
            "role": "A-Level · Maths, Physics, Art",
            "desc": [],
        },
    ],
}

CONTACT_EMAIL = "ander.brown@icloud.com"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — poster frames from the time-lapse videos
# ─────────────────────────────────────────────────────────────────────────────
def ffprobe_duration(video_path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_posters(force: bool = False) -> None:
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    for proj in PROJECTS:
        dst = POSTER_DIR / f"{proj['slug']}.jpg"
        if dst.exists() and not force:
            print(f"  poster ok    {proj['slug']}.jpg")
            continue
        src = ROOT / proj["video"]
        if not src.exists():
            print(f"  !! missing video for {proj['slug']}: {src}")
            continue
        try:
            dur = ffprobe_duration(src)
        except Exception:
            dur = 4.0
        # Time-lapses resolve to the finished render near the end; grab at ~88%.
        seek = max(0.0, dur * 0.88)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seek:.3f}",
             "-i", str(src), "-frames:v", "1",
             "-vf", "scale=2000:-2:flags=lanczos", "-q:v", "3", str(dst)],
            check=True,
        )
        print(f"  poster built {proj['slug']}.jpg  (@ {seek:.1f}s of {dur:.1f}s)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — downsize images for a sane PDF file size
# ─────────────────────────────────────────────────────────────────────────────
def optimize_images(force: bool = False) -> None:
    """Resize every gallery / portrait image into print/cache as JPEG.

    Source assets are full-resolution (some > 3 MB); embedding them directly
    produces a ~300 MB PDF. Downsizing to ~1300 px keeps plates crisp on an A4
    page while bringing the document down to an emailable size.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    targets = [(ABOUT["photo"], 1200, 82)]
    for proj in PROJECTS:
        for src, _cap in proj["images"]:
            targets.append((src, GALLERY_PX, GALLERY_Q))

    built = 0
    for rel, longest, quality in targets:
        if rel in OPT:
            continue
        key = rel.replace("/", "__").rsplit(".", 1)[0] + ".jpg"
        dst = CACHE_DIR / key
        OPT[rel] = dst
        if dst.exists() and not force:
            continue
        src_path = ROOT / rel
        if not src_path.exists():
            print(f"  !! missing image: {rel}")
            continue
        subprocess.run(
            ["sips", "-Z", str(longest), "-s", "format", "jpeg",
             "-s", "formatOptions", str(quality),
             str(src_path), "--out", str(dst)],
            capture_output=True, check=True,
        )
        built += 1
    print(f"  optimized {len(OPT)} images -> print/cache/  ({built} rebuilt)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — generate the print HTML
# ─────────────────────────────────────────────────────────────────────────────
def furl(rel_or_path) -> str:
    """Absolute file:// URI for an asset (handles spaces / unicode)."""
    p = Path(rel_or_path)
    if not p.is_absolute():
        p = (ROOT / p)
    return p.resolve().as_uri()


def esc(s: str) -> str:
    return html.escape(s, quote=True)


ROT = [-0.55, 0.45, -0.35, 0.6, -0.45, 0.4]   # subtle scrapbook tilt per cell

CSS = r"""
@page { size: A4; margin: 0; }

* { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ink:    #000;
  --body:   rgba(0,0,0,0.72);
  --muted:  rgba(0,0,0,0.45);
  --faint:  rgba(0,0,0,0.10);
  --line:   rgba(0,0,0,0.14);
  --display: 'Montserrat', 'Helvetica Neue', Arial, sans-serif;
  --serif:   'Spectral', Georgia, serif;
}

html, body { width: 210mm; }
body {
  font-family: var(--display);
  color: var(--ink);
  background: #fff;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

img { display: block; }

.sheet {
  position: relative;
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  page-break-after: always;
  break-after: page;
  background: #fff;
}
.sheet:last-child { page-break-after: auto; break-after: auto; }

/* ── shared type ─────────────────────────────────────────── */
.kicker {
  font-family: var(--display);
  font-size: 7.5pt;
  font-weight: 700;
  letter-spacing: 0.34em;
  text-transform: uppercase;
  color: var(--muted);
}
.serif {
  font-family: var(--serif);
  color: var(--body);
}

/* ── running folio ───────────────────────────────────────── */
.folio {
  position: absolute;
  left: 16mm; right: 16mm; bottom: 10mm;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-family: var(--display);
  font-size: 7pt;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--muted);
}
.folio::before {
  content: "";
  position: absolute;
  left: 0; right: 0; top: -6mm;
  border-top: 0.5px solid var(--line);
}

/* ══ COVER ═══════════════════════════════════════════════ */
.cover .cover-img {
  width: 210mm;
  height: 182mm;
  object-fit: cover;
}
.cover .cover-foot {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 115mm;
  padding: 20mm 18mm 16mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.cover .cover-name {
  font-family: var(--display);
  font-weight: 700;
  font-size: 38pt;
  line-height: 1.0;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}
.cover .cover-sub {
  font-family: var(--serif);
  font-style: italic;
  font-size: 13pt;
  color: var(--body);
  margin-top: 6mm;
}
.cover .cover-meta {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
.cover .cover-years {
  font-family: var(--display);
  font-size: 9pt;
  font-weight: 500;
  letter-spacing: 0.28em;
}

/* ══ CONTENTS ════════════════════════════════════════════ */
.contents { padding: 30mm 18mm 0; }
.contents h2 {
  font-family: var(--display);
  font-weight: 700;
  font-size: 30pt;
  text-transform: uppercase;
  letter-spacing: -0.01em;
  margin-bottom: 14mm;
}
.toc-row {
  display: flex;
  align-items: baseline;
  padding: 6.4mm 0;
  border-top: 0.5px solid var(--line);
}
.toc-row:last-of-type { border-bottom: 0.5px solid var(--line); }
.toc-num {
  font-family: var(--display);
  font-size: 9pt;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--muted);
  width: 16mm;
  flex: none;
}
.toc-title {
  font-family: var(--display);
  font-size: 15pt;
  font-weight: 500;
  letter-spacing: 0.01em;
}
.toc-sub {
  font-family: var(--serif);
  font-style: italic;
  font-size: 9.5pt;
  color: var(--muted);
  margin-left: 6mm;
}
.toc-dots {
  flex: 1;
  margin: 0 4mm;
  border-bottom: 0.5px dotted var(--line);
  transform: translateY(-1mm);
}
.toc-page {
  font-family: var(--display);
  font-size: 10pt;
  font-weight: 500;
  color: var(--body);
}

/* ══ ABOUT ═══════════════════════════════════════════════ */
.about-intro { padding: 26mm 18mm 0; }
.about-grid {
  display: grid;
  grid-template-columns: 64mm 1fr;
  gap: 14mm;
  align-items: start;
}
.about-photo {
  width: 64mm;
  height: 84mm;
  object-fit: cover;
  object-position: 60% top;
}
.about-name {
  font-family: var(--display);
  font-weight: 700;
  font-size: 24pt;
  text-transform: uppercase;
  letter-spacing: -0.01em;
}
.about-cred {
  font-family: var(--display);
  font-size: 8pt;
  font-weight: 500;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 3mm 0 7mm;
}
.about-bio p {
  font-family: var(--serif);
  font-size: 10.5pt;
  line-height: 1.85;
  color: var(--body);
  text-align: justify;
}
.about-bio p + p { margin-top: 3.5mm; }

.skills { margin-top: 16mm; }
.skills .kicker { margin-bottom: 7mm; }
.skill {
  display: flex;
  align-items: center;
  gap: 8mm;
  padding: 2.6mm 0;
}
.skill-name {
  width: 38mm;
  flex: none;
  font-family: var(--display);
  font-size: 8.5pt;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.skill-track {
  flex: 1;
  height: 1.5px;
  background: var(--faint);
  position: relative;
}
.skill-fill {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: var(--ink);
}

.about-cv { padding: 24mm 18mm 0; }
.about-cv h2 {
  font-family: var(--display);
  font-weight: 700;
  font-size: 22pt;
  text-transform: uppercase;
  letter-spacing: -0.01em;
  margin-bottom: 11mm;
}
.cv-entry {
  display: grid;
  grid-template-columns: 34mm 1fr;
  gap: 10mm;
  padding: 8mm 0;
  border-top: 0.5px solid var(--line);
}
.cv-entry:last-child { border-bottom: 0.5px solid var(--line); }
.cv-dates {
  font-family: var(--display);
  font-size: 8.5pt;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--muted);
  padding-top: 0.6mm;
}
.cv-org {
  font-family: var(--display);
  font-size: 12pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0;
}
.cv-loc {
  font-family: var(--display);
  font-size: 8pt;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--muted);
  margin: 1.6mm 0 0.8mm;
}
.cv-role {
  font-family: var(--serif);
  font-style: italic;
  font-size: 9.5pt;
  color: var(--body);
  margin-bottom: 3.4mm;
}
.cv-desc p {
  font-family: var(--serif);
  font-size: 9.5pt;
  line-height: 1.75;
  color: var(--body);
  text-align: justify;
}
.cv-desc p + p { margin-top: 2mm; }

/* ══ PROJECT OPENER ══════════════════════════════════════ */
.opener .hero {
  width: 210mm;
  height: 168mm;
  object-fit: cover;
}
.opener .opener-body {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 129mm;
  padding: 16mm 18mm 20mm;
  display: grid;
  grid-template-columns: 74mm 1fr;
  gap: 14mm;
}
.opener-num {
  font-family: var(--display);
  font-weight: 300;
  font-size: 30pt;
  color: var(--faint);
  line-height: 1;
  letter-spacing: 0.04em;
}
.opener-title {
  font-family: var(--display);
  font-weight: 700;
  font-size: 33pt;
  text-transform: uppercase;
  letter-spacing: -0.015em;
  line-height: 1;
  margin: 4mm 0 7mm;
}
.opener-meta { border-top: 0.5px solid var(--line); padding-top: 4mm; }
.opener-meta div {
  font-family: var(--display);
  font-size: 8pt;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--body);
  line-height: 2.05;
}
.opener-text { column-gap: 8mm; }
.opener-text.two-col { column-count: 2; }
.opener-text p {
  font-family: var(--serif);
  font-size: 9.3pt;
  line-height: 1.78;
  color: var(--body);
  text-align: justify;
}
.opener-text p + p { margin-top: 2.6mm; }

/* ══ GALLERY ═════════════════════════════════════════════ */
.gallery {
  padding: 16mm 16mm 22mm;
  display: flex;
  flex-direction: column;
}
.gallery-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: 4mm;
  margin-bottom: 7mm;
  border-bottom: 0.5px solid var(--line);
}
.gallery-head .g-title {
  font-family: var(--display);
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.gallery-head .g-idx {
  font-family: var(--display);
  font-size: 7.5pt;
  font-weight: 500;
  letter-spacing: 0.2em;
  color: var(--muted);
}
.grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 7mm 8mm;
}
.plate {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  min-height: 0;
}
.plate .frame {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  min-height: 0;
}
.plate img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
}
.plate .cap {
  font-family: var(--display);
  font-size: 6.6pt;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  margin-top: 2.6mm;
  text-align: center;
}

/* ══ BACK COVER ══════════════════════════════════════════ */
.back {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 6mm;
}
.back .back-name {
  font-family: var(--display);
  font-weight: 700;
  font-size: 16pt;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.back .back-line {
  font-family: var(--serif);
  font-style: italic;
  font-size: 10.5pt;
  color: var(--body);
}
.back .back-mail {
  font-family: var(--display);
  font-size: 8.5pt;
  font-weight: 500;
  letter-spacing: 0.16em;
  margin-top: 4mm;
}
.back .back-rule {
  width: 22mm;
  border-top: 0.5px solid var(--ink);
  margin: 2mm 0;
}
"""


def folio(page_no: int) -> str:
    return (
        f'<div class="folio"><span>Alexander Brown</span>'
        f'<span>Selected Works · {page_no:02d}</span></div>'
    )


def render_cover() -> str:
    return f"""
<section class="sheet cover">
  <img class="cover-img" src="{furl(POSTER_DIR / (COVER_SLUG + '.jpg'))}" alt="">
  <div class="cover-foot">
    <div>
      <div class="kicker">Architecture Portfolio</div>
    </div>
    <div>
      <div class="cover-name">Alexander<br>Brown</div>
      <div class="cover-sub">Selected architectural works</div>
    </div>
    <div class="cover-meta">
      <div class="kicker">SAR &middot; Sveriges Arkitekter</div>
      <div class="cover-years">2016 &mdash; 2022</div>
    </div>
  </div>
</section>"""


def render_contents(toc, page_no: int) -> str:
    rows = [
        '<div class="toc-row">'
        '<span class="toc-num">&mdash;</span>'
        '<span class="toc-title">About</span>'
        '<span class="toc-sub">Profile &amp; background</span>'
        '<span class="toc-dots"></span>'
        f'<span class="toc-page">{toc["about"]:02d}</span>'
        '</div>'
    ]
    for i, proj in enumerate(PROJECTS, start=1):
        rows.append(
            '<div class="toc-row">'
            f'<span class="toc-num">{i:02d}</span>'
            f'<span class="toc-title">{esc(proj["title"])}</span>'
            f'<span class="toc-sub">{esc(proj["year"])} &nbsp;&middot;&nbsp; {esc(proj["location"])}</span>'
            '<span class="toc-dots"></span>'
            f'<span class="toc-page">{toc[proj["slug"]]:02d}</span>'
            '</div>'
        )
    return f"""
<section class="sheet contents">
  <h2>Contents</h2>
  {''.join(rows)}
  {folio(page_no)}
</section>"""


def render_about_intro(page_no: int) -> str:
    bio = "".join(f"<p>{esc(p)}</p>" for p in ABOUT["bio"])
    skills = "".join(
        f'<div class="skill"><span class="skill-name">{esc(name)}</span>'
        f'<span class="skill-track"><span class="skill-fill" style="width:{lvl*100:.0f}%"></span></span></div>'
        for name, lvl in ABOUT["skills"]
    )
    return f"""
<section class="sheet about-intro">
  <div class="kicker" style="margin-bottom:10mm">About</div>
  <div class="about-grid">
    <img class="about-photo" src="{furl(OPT.get(ABOUT['photo'], ABOUT['photo']))}" alt="">
    <div>
      <div class="about-name">{esc(ABOUT['name'])}</div>
      <div class="about-cred">{esc(ABOUT['credential'])}</div>
      <div class="about-bio">{bio}</div>
    </div>
  </div>
  <div class="skills">
    <div class="kicker">Software</div>
    {skills}
  </div>
  {folio(page_no)}
</section>"""


def render_about_cv(entries, page_no: int, first: bool) -> str:
    blocks = []
    for e in entries:
        desc = "".join(f"<p>{esc(p)}</p>" for p in e["desc"])
        blocks.append(f"""
    <div class="cv-entry">
      <div class="cv-dates">{esc(e['dates'])}</div>
      <div>
        <div class="cv-org">{esc(e['org'])}</div>
        <div class="cv-loc">{esc(e['location'])}</div>
        <div class="cv-role">{esc(e['role'])}</div>
        <div class="cv-desc">{desc}</div>
      </div>
    </div>""")
    heading = "<h2>Background</h2>" if first else '<h2 style="opacity:0;height:0;margin:0">Background</h2>'
    return f"""
<section class="sheet about-cv">
  {heading}
  {''.join(blocks)}
  {folio(page_no)}
</section>"""


def render_opener(idx: int, proj: dict, page_no: int) -> str:
    paras = "".join(f"<p>{esc(p)}</p>" for p in proj["text"])
    total_chars = sum(len(p) for p in proj["text"])
    two_col = " two-col" if total_chars > 900 else ""
    return f"""
<section class="sheet opener">
  <img class="hero" src="{furl(POSTER_DIR / (proj['slug'] + '.jpg'))}" alt="">
  <div class="opener-body">
    <div>
      <div class="opener-num">{idx:02d}</div>
      <div class="opener-title">{esc(proj['title'])}</div>
      <div class="opener-meta">
        <div>{esc(proj['year'])}</div>
        <div>{esc(proj['location'])}</div>
        <div>{esc(proj['type'])}</div>
      </div>
    </div>
    <div class="opener-text{two_col}">{paras}</div>
  </div>
  {folio(page_no)}
</section>"""


def render_gallery(proj: dict, chunk, page_no: int, part: int, parts: int) -> str:
    cells = []
    for j, (src, cap) in enumerate(chunk):
        rot = ROT[j % len(ROT)]
        cells.append(f"""
    <figure class="plate" style="transform:rotate({rot}deg)">
      <span class="frame"><img src="{furl(OPT.get(src, src))}" alt=""></span>
      <figcaption class="cap">{esc(cap)}</figcaption>
    </figure>""")
    idx_label = f"Plates &mdash; {part} / {parts}" if parts > 1 else "Plates"
    return f"""
<section class="sheet gallery">
  <div class="gallery-head">
    <span class="g-title">{esc(proj['title'])}</span>
    <span class="g-idx">{esc(proj['year'])} &nbsp;&middot;&nbsp; {idx_label}</span>
  </div>
  <div class="grid">{''.join(cells)}</div>
  {folio(page_no)}
</section>"""


def render_back(page_no: int) -> str:
    return f"""
<section class="sheet back">
  <div class="kicker">Thank you</div>
  <div class="back-rule"></div>
  <div class="back-name">Alexander Brown</div>
  <div class="back-line">Architect &middot; SAR / MSA</div>
  <div class="back-mail">{esc(CONTACT_EMAIL)}</div>
</section>"""


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def build_html() -> str:
    # ── Pass 1: lay out the page sequence to know page numbers ──
    # cover = 1, contents = 2, about-intro = 3, cv1 = 4, cv2 = 5, then projects.
    page = 1                       # cover
    page += 1                      # contents
    about_page = page + 1          # about-intro
    page = about_page              # 3
    page += 1                      # cv part 1  (4)
    page += 1                      # cv part 2  (5)

    toc = {"about": about_page}
    project_layout = []            # (proj, opener_page, [(chunk, page), ...])
    for proj in PROJECTS:
        page += 1
        opener_page = page
        toc[proj["slug"]] = opener_page
        gallery_pages = []
        for chunk in chunked(proj["images"], IMAGES_PER_GALLERY_PAGE):
            page += 1
            gallery_pages.append((chunk, page))
        project_layout.append((proj, opener_page, gallery_pages))
    page += 1                      # back cover

    # ── Pass 2: render ──
    parts = [render_cover()]
    parts.append(render_contents(toc, 2))
    parts.append(render_about_intro(about_page))

    cv = ABOUT["timeline"]
    parts.append(render_about_cv(cv[:3], about_page + 1, first=True))
    parts.append(render_about_cv(cv[3:], about_page + 2, first=False))

    for i, (proj, opener_page, gallery_pages) in enumerate(project_layout, start=1):
        parts.append(render_opener(i, proj, opener_page))
        n_parts = len(gallery_pages)
        for p_idx, (chunk, pno) in enumerate(gallery_pages, start=1):
            parts.append(render_gallery(proj, chunk, pno, p_idx, n_parts))

    parts.append(render_back(page))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Alexander Brown &mdash; Portfolio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;700&family=Spectral:ital,wght@0,400;0,500;1,400;1,500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
{''.join(parts)}
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — render to PDF with headless Chromium
# ─────────────────────────────────────────────────────────────────────────────
def render_pdf() -> None:
    from playwright.sync_api import sync_playwright

    def _go(p):
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(HTML_OUT.resolve().as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(900)
        pg.pdf(
            path=str(PDF_OUT),
            prefer_css_page_size=True,
            print_background=True,
        )
        browser.close()

    with sync_playwright() as p:
        try:
            _go(p)
        except Exception as exc:
            if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
                print("  Chromium not installed for Playwright — installing…")
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                _go(p)
            else:
                raise


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    force = "--force" in sys.argv

    print("1/4  Extracting poster frames from time-lapse videos…")
    extract_posters(force=force)

    print("2/4  Downsizing images for print…")
    optimize_images(force=force)

    print("3/4  Generating print HTML…")
    HTML_OUT.write_text(build_html(), encoding="utf-8")
    print(f"     wrote {HTML_OUT.relative_to(ROOT)}")

    print("4/4  Rendering PDF with headless Chromium…")
    render_pdf()
    size_mb = PDF_OUT.stat().st_size / 1_048_576
    print(f"\n✓  {PDF_OUT.name}  ({size_mb:.1f} MB)")
    print(f"   {PDF_OUT}")


if __name__ == "__main__":
    main()
