#!/usr/bin/env python3
"""Join per-page Markdown files into the final document and bundle its figures in one PDF.

usage: assemble.py WORKDIR/md OUTDIR --name NAME [--figures DIR] [--dpi-floor 150]
                   [--manifest WORKDIR/manifest.json] [--printed-offset K|none]

NAME is the original PDF's file name without ".pdf", unchanged. Writes
    OUTDIR/NAME.md           the text-only document (no image data inside)
    OUTDIR/NAME_figures.pdf  every figure, packed several per page; only written
                             if the document has figures

Pages: page_NNN.md files are concatenated in page order, separated by a blank
line. A page file whose last line is exactly  <!-- continues -->  ends
mid-paragraph: the marker is removed and the next page's first line is joined
to it with a single space, so a paragraph broken by a page break comes out whole.

Page markers: the page files carry no page numbers; this script adds them. The
document opens with a one-line legend, and every page starts with
    <!-- page N -->                 N = page number in the PDF (from page_NNN.md)
    <!-- page N (printed M) -->     when the number printed on the page differs
on its own line. Where a paragraph runs across the break, the marker stands
inline at the exact point of the break:  ...end of one <!-- page 7 --> page...
Printed numbers come from manifest.json (default: next to the md folder, written
by prepare.py); --printed-offset K sets printed = N + K for every page instead,
--printed-offset none drops them. A page file that already contains a page marker
is an error.

Figures: each placeholder  ![Fig. N](figure:figN)  becomes the text line
    *[Fig. N: NAME_figures.pdf, page P]*
naming the page of the figures PDF that shows it. In the figures PDF each figure
is labelled with its number and the document page it comes from. The images (from figures.py, in
DIR, default the 'figures' folder next to the md folder) are placed at their
native size, in order of appearance, each under a small "Fig. N" label.

Adaptive packing: Claude sees a PDF page as one image of at most ~1.15 megapixels
(and 1,568 px on the long edge). More figures per page cost fewer tokens each but
get fewer pixels. Figures are added to a page until its area would exceed
1.15e6 / dpi_floor**2 square inches or its long edge 1568 / dpi_floor inches, so
every figure keeps at least --dpi-floor (default 150) effective resolution: the
level at which small labels stayed reliably legible in tests. Typical
single-column figures land 3-4 per page; a large figure takes a page with at
most one small companion; a figure too large for any page goes alone, and a
warning gives its effective resolution. A missing figure is an error.
"""
import sys, os, re, glob, argparse, math, json
import pymupdf
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('outdir')
ap.add_argument('--name', required=True); ap.add_argument('--figures')
ap.add_argument('--dpi-floor', type=float, default=150)
ap.add_argument('--manifest'); ap.add_argument('--printed-offset')
a = ap.parse_args()
if a.name.lower().endswith('.pdf'): a.name = a.name[:-4]
workdir = os.path.dirname(os.path.abspath(a.src))
figdir = a.figures or os.path.join(workdir, 'figures')
files = sorted(glob.glob(os.path.join(a.src, 'page_*.md')), key=lambda f: int(re.search(r'page_(\d+)', os.path.basename(f)).group(1)))
if not files: sys.exit(f'no page_NNN.md files in {a.src}')

# printed page numbers: from the manifest, or an explicit offset
man = a.manifest or os.path.join(workdir, 'manifest.json')
pnum = lambda f: int(re.search(r'page_(\d+)', os.path.basename(f)).group(1))
nums = [pnum(f) for f in files]
printed = {}
if a.printed_offset is None and os.path.exists(man):
    printed = {p['page']: p.get('printed') for p in json.load(open(man))['pages']}
elif a.printed_offset and a.printed_offset.lower() != 'none':
    k = int(a.printed_offset)
    printed = {n: str(n + k) for n in nums if k and n + k > 0}
MARK = re.compile(r'<!--\s*page\s+\d+')
def marker(n):
    pr = printed.get(n)
    return f'<!-- page {n} (printed {pr}) -->' if pr else f'<!-- page {n} -->'

CONT = '<!-- continues -->'
doc, joined, figpage = '', 0, {}
for f in files:
    n = pnum(f)
    t = open(f).read().strip('\n')
    if MARK.search(t): sys.exit(f'{os.path.basename(f)} contains a page marker; remove it, assemble.py adds them')
    for fig in re.findall(r'!\[[^\]]*\]\(figure:([\w.-]+)\)', t): figpage.setdefault(fig, n)
    if doc.endswith(CONT):
        doc = doc[:-len(CONT)].rstrip()
        if re.match(r'\s*(\$\$|#|!\[|\|)', t):          # page opens with a block: marker on its own line
            doc += '\n\n' + marker(n) + '\n\n' + t.lstrip()
        else:                                           # paragraph runs on: marker inline at the break
            doc += ' ' + marker(n) + ' ' + t.lstrip()
        joined += 1
    else:
        doc = (doc + '\n\n' if doc else '') + marker(n) + ('\n\n' + t if t.strip() else '')
if doc.endswith(CONT): doc = doc[:-len(CONT)].rstrip()
legend = (f'<!-- Transcription of {a.name}.pdf. "page N" markers give the PDF page on which the following text starts'
          + ('; "printed M" is the page number printed on that page' if any(printed.get(n) for n in nums) else '')
          + '. -->')
doc = legend + '\n\n' + doc

os.makedirs(a.outdir, exist_ok=True)
MP, LONG_PX, NATIVE_DPI = 1.15e6, 1568, 200            # image-size rules; figures.py renders at 200 dpi
MARGIN, GAP, LABEL, ROW_W = 0.15, 0.15, 0.22, 7.6      # inches; ROW_W fits two single-column figures
AREA_MAX, LONG_MAX = MP / a.dpi_floor ** 2, LONG_PX / a.dpi_floor

# collect figures in order of first appearance
order, missing = [], []
for alt, fig in re.findall(r'!\[([^\]]*)\]\(figure:([\w.-]+)\)', doc):
    if fig in [f for f, *_ in order]: continue
    path = next((os.path.join(figdir, f'{fig}.{e}') for e in ('png', 'jpg') if os.path.exists(os.path.join(figdir, f'{fig}.{e}'))), None)
    if not path: missing.append(fig); continue
    from PIL import Image
    w, h = Image.open(path).size
    order.append((fig, alt, path, w / NATIVE_DPI, h / NATIVE_DPI))
if missing: sys.exit(f'figure(s) not found in {figdir}: {missing}')

def dims(rows):
    W = max(sum(f[3] for f in r) + GAP * (len(r) - 1) for r in rows) + 2 * MARGIN
    H = sum(max(f[4] for f in r) + LABEL for r in rows) + GAP * (len(rows) - 1) + 2 * MARGIN
    return W, H
pages, cur = [], []
for f in order:
    if not cur: cur = [[f]]; continue
    last = cur[-1]
    fits_row = sum(x[3] for x in last) + GAP * len(last) + f[3] <= ROW_W
    cand = cur[:-1] + [last + [f]] if fits_row else cur + [[f]]
    W, H = dims(cand)
    if W * H <= AREA_MAX and max(W, H) <= LONG_MAX: cur = cand
    else: pages.append(cur); cur = [[f]]
if cur: pages.append(cur)

pdfname = f'{a.name}_figures.pdf'; pdfpath = os.path.join(a.outdir, pdfname)
if os.path.exists(pdfpath): os.remove(pdfpath)
where, report = {}, []
if order:
    out_pdf = pymupdf.open()
    for pno, rows in enumerate(pages, 1):
        W, H = dims(rows); page = out_pdf.new_page(width=W * 72, height=H * 72)
        y = MARGIN
        for r in rows:
            x = MARGIN; rh = max(f[4] for f in r)
            for fig, alt, path, w, h in r:
                src = figpage[fig]; pr = printed.get(src)
                label = f'{alt}, p. {src}' + (f' (printed {pr})' if pr else '')
                fs = max(5, min(8, 8 * w * 72 / max(1, pymupdf.get_text_length(label, 'helv', 8))))
                page.insert_text(((x) * 72, (y + LABEL * 0.7) * 72), label, fontsize=fs, fontname='helv')
                page.insert_image(pymupdf.Rect(x * 72, (y + LABEL) * 72, (x + w) * 72, (y + LABEL + h) * 72), filename=path)
                where[fig] = pno; x += w + GAP
            y += rh + LABEL + GAP
        eff = min(math.sqrt(MP / (W * H)), LONG_PX / max(W, H), NATIVE_DPI)
        names = ', '.join(f[1] for r in rows for f in r)
        report.append(f'   page {pno}: {names}  ({W:.1f} x {H:.1f} in, ~{eff:.0f} dpi effective)'
                      + ('  WARNING: below the floor, figure too large for one page' if eff < a.dpi_floor - 0.5 else ''))
    out_pdf.save(pdfpath, garbage=4, deflate=True)

def ref(m):
    alt, fig = m.group(1), m.group(2)
    return f'*[{alt}: {pdfname}, page {where[fig]}]*'
doc = re.sub(r'!\[([^\]]*)\]\(figure:([\w.-]+)\)', ref, doc)
if re.search(r'data:image/', doc): sys.exit('image data found in the Markdown; figures must be placeholders')
out = os.path.join(a.outdir, f'{a.name}.md')
open(out, 'w').write(doc + '\n')
print(f'{len(files)} pages -> {out} ({os.path.getsize(out)//1024} KB, text only; {joined} paragraph(s) joined across page breaks)')
pr_pages = [n for n in nums if printed.get(n)]
print(f'page markers: PDF pages {nums[0]}-{nums[-1]}'
      + (f', printed numbers on {len(pr_pages)} page(s), first {printed[pr_pages[0]]}' if pr_pages else ', no printed numbers'))
if order:
    print(f'{len(order)} figure(s) -> {pdfpath} ({os.path.getsize(pdfpath)//1024} KB, {len(pages)} page(s), floor {a.dpi_floor:.0f} dpi):')
    print('\n'.join(report))
else:
    print('no figures: no figures PDF written')
