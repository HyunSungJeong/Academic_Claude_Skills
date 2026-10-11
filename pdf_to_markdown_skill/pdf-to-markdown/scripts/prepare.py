#!/usr/bin/env python3
"""Prepare a PDF for Markdown transcription.

usage: prepare.py INPUT.pdf WORKDIR [--dpi 170] [--strip 180]

Writes to WORKDIR:
  page_NNN.txt        text layer of the page; grep it for a doubtful word, never read it whole
  page_NNN_sKK.png    horizontal strips of the page at --dpi, cut in the gaps between
                      text lines so no line or equation is sliced in half
  manifest.json       per page: math-font share, strip files + their y-ranges (pt),
                      equation tags found at the right margin, page-break info,
                      and the page number printed on the page ('printed')
Prints one compact line per page with everything the transcription needs (strip
files with their y-ranges in points, equation tags, the printed page number when it
differs from the PDF page number), so manifest.json, which the check scripts and
assemble.py read, never has to be opened.

Printed page numbers: taken from the PDF's own page labels if it defines them;
otherwise from bare numbers in the header or footer (and numbers at either end of
a running head), accepted only if at least two pages agree on one constant offset
from the PDF page number, which is then applied to every page. assemble.py writes
both numbers into the page markers of the Markdown.

170 dpi is rendered natively (no later downscaling for a normal text width); in a
blind test every symbol distinction tested was still read correctly at 100 dpi.
"""
import sys, os, re, json, argparse
from collections import Counter
import pymupdf

MATH_FONT = re.compile(r'(CMMI|CMSY|CMEX|CMBSY|MSAM|MSBM|EUFM|EUSM|RSFS|STIXMath|STIXGeneral|'
                       r'CambriaMath|Cambria-Math|XITSMath|LatinModernMath|NewCMMath|Symbol|MathematicalPi|'
                       r'TeXGyre.*Math|MTMI|MTSY|Mathematica)', re.I)
TAG = re.compile(r'^\(\s*(\d+[a-z]?|[A-Z]\.?\d+[a-z]?)\s*\)$')
BARE_NUM = re.compile(r'[-–—\s]*(\d{1,4})[-–—\s]*')

ap = argparse.ArgumentParser()
ap.add_argument('pdf'); ap.add_argument('out')
ap.add_argument('--dpi', type=int, default=170)
ap.add_argument('--strip', type=float, default=180, help='target strip height in pt')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
doc = pymupdf.open(a.pdf)
manifest = {'source': os.path.abspath(a.pdf), 'pages': []}
printouts, numcands = [], {}          # numcands: PDF page -> numbers seen in its header/footer

for pno, page in enumerate(doc, 1):
    W, H = page.rect.width, page.rect.height
    d = page.get_text('dict')
    lines, math_chars, text_chars, tags = [], 0, 0, []
    for b in d['blocks']:
        for l in b.get('lines', []):
            txt = ''.join(s['text'] for s in l['spans']).strip()
            if not txt: continue
            bare = BARE_NUM.fullmatch(txt)
            foot, head = l['bbox'][1] > 0.85 * H, l['bbox'][3] < 0.15 * H
            if bare and (foot or head):
                numcands.setdefault(pno, set()).add(int(bare.group(1)))
            elif head:                         # running head with the number at either end
                m = re.match(r'(\d{1,4})\s+\S', txt) or re.search(r'\S\s+(\d{1,4})$', txt)
                if m: numcands.setdefault(pno, set()).add(int(m.group(1)))
            if bare and foot:
                continue  # page number in the footer: no strip for it (assemble.py writes page markers)
            lines.append(l['bbox'])
            for s in l['spans']:
                n = len(s['text'].strip())
                if MATH_FONT.search(s['font']): math_chars += n
                else: text_chars += n
            # equation tag: a span "(N)" at the right margin, alone on its line or at the end of a longer one
            last = [s for s in l['spans'] if s['text'].strip()][-1]
            cand = last['text'].strip() if TAG.match(last['text'].strip()) else txt
            if TAG.match(cand) and (last['bbox'][0] > 0.75 * W or l['bbox'][0] > 0.75 * W):
                tags.append({'tag': TAG.match(cand).group(1), 'y': round((l['bbox'][1] + l['bbox'][3]) / 2, 1)})
    open(f'{a.out}/page_{pno:03d}.txt', 'w').write(page.get_text('text'))

    # strips: merge line bboxes into vertical bands, then cut only in empty gaps
    bands = []
    for y0, y1 in sorted((b[1], b[3]) for b in lines):
        if bands and y0 <= bands[-1][1] + 1.0: bands[-1][1] = max(bands[-1][1], y1)
        else: bands.append([y0, y1])
    if not bands: bands = [[0, H]]
    x0 = max(0, min(b[0] for b in lines) - 8) if lines else 0
    x1 = min(W, max(b[2] for b in lines) + 8) if lines else W
    strips, cur = [], [bands[0][0], bands[0][1]]
    for y0, y1 in bands[1:]:
        if y1 - cur[0] > a.strip: strips.append(cur); cur = [y0, y1]
        else: cur[1] = y1
    strips.append(cur)
    files = []
    for k, (y0, y1) in enumerate(strips, 1):
        r = pymupdf.Rect(x0, max(0, y0 - 4), x1, min(H, y1 + 4))
        fn = f'page_{pno:03d}_s{k:02d}.png'
        page.get_pixmap(dpi=a.dpi, clip=r).save(f'{a.out}/{fn}')
        files.append({'file': fn, 'y0': round(r.y0, 1), 'y1': round(r.y1, 1)})
    share = math_chars / max(1, math_chars + text_chars)
    manifest['pages'].append({'page': pno, 'math_share': round(share, 3), 'math_chars': math_chars,
                              'needs_images': math_chars > 0, 'strips': files, 'equation_tags': tags,
                              'clip_x': [round(x0, 1), round(x1, 1)]})
    st = ' '.join(f's{k:02d} {f["y0"]:.0f}-{f["y1"]:.0f}' for k, f in enumerate(files, 1))
    printouts.append(f'{"img" if math_chars else "text-ok"} | {st} | tags {" ".join(t["tag"] for t in tags) or "-"}')

# printed page numbers: PDF page labels if defined, else one constant offset seen on >= 2 pages
labels = [pg.get_label() for pg in doc]
if any(labels):
    printed = [l if l and l != str(k) else None for k, l in enumerate(labels, 1)]
    psrc = 'PDF page labels'
else:
    offs = Counter(n - k for k, ns in numcands.items() for n in ns)
    off, cnt = offs.most_common(1)[0] if offs else (0, 0)
    if off and cnt >= 2 and cnt >= 0.5 * len(numcands):
        printed = [str(k + off) if k + off > 0 else None for k in range(1, len(doc) + 1)]
        psrc = f'offset {off:+d} from page headers/footers ({cnt} pages agree)'
    else:
        printed = [None] * len(doc)
        psrc = 'same as PDF page numbers' if cnt and not off else 'none detected'
for p, pr, line in zip(manifest['pages'], printed, printouts):
    p['printed'] = pr
    print(f'p{p["page"]}{f" (printed {pr})" if pr else ""}: {line}')

json.dump(manifest, open(f'{a.out}/manifest.json', 'w'), indent=1)
need = [p['page'] for p in manifest['pages'] if p['needs_images']]
xr = sorted({tuple(p['clip_x']) for p in manifest['pages']})
print(f'strips: {a.out}/page_NNN_sKK.png at {a.dpi} dpi | coordinates in pt, text x-range {xr[0][0]:.0f}-{xr[-1][1]:.0f}, '
      f'page {doc[0].rect.width:.0f}x{doc[0].rect.height:.0f} | image pages: {"all" if len(need) == len(doc) else need}')
print(f'printed page numbers: {psrc}')
