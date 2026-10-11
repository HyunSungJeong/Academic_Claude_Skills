#!/usr/bin/env python3
"""Proofreading sheets: each tagged display equation as printed in the PDF (top)
and as re-typeset from the transcription with pdflatex (bottom).

usage: verify_eqs.py TRANSCRIPT.md WORKDIR [--per-sheet 4]
Writes WORKDIR/verify/sheet_NN.png. View each sheet and compare symbol by symbol:
signs, indices, bars, tildes, primes, bold/calligraphic/roman, brace extents.
Needs pdflatex; prints a notice and exits if it is missing.
"""
import sys, os, re, json, subprocess, shutil, argparse, tempfile
import pymupdf
pymupdf.TOOLS.set_small_glyph_heights(True)  # tight line boxes: big operators otherwise swallow neighbouring rows
from PIL import Image, ImageDraw, ImageOps

ap = argparse.ArgumentParser(); ap.add_argument('md'); ap.add_argument('work')
ap.add_argument('--per-sheet', type=int, default=4); a = ap.parse_args()
if not shutil.which('pdflatex'): sys.exit('pdflatex not found: skip this step and proofread from strips instead')
md = open(a.md).read(); man = json.load(open(os.path.join(a.work, 'manifest.json')))
doc = pymupdf.open(man['source'])
out = os.path.join(a.work, 'verify'); os.makedirs(out, exist_ok=True)
where = {t['tag']: (p['page'], t['y'], p['clip_x']) for p in man['pages'] for t in p['equation_tags']}

def trim(im, pad=12):
    bbox = ImageOps.invert(im.convert('L')).point(lambda v: 255 if v > 30 else 0).getbbox()
    return ImageOps.expand(im.crop(bbox), pad, 'white') if bbox else im

def original(tag):
    pno, y, (x0, x1) = where[tag]; page = doc[pno - 1]
    raw = [(l['bbox'], ''.join(s['text'] for s in l['spans']).strip())
           for b in page.get_text('dict')['blocks'] for l in b.get('lines', [])]
    H = page.rect.height
    footer = [bb for bb, t in raw if re.fullmatch(r'[-–—\s]*\d{1,4}[-–—\s]*', t) and bb[1] > 0.88 * H]
    ls = sorted((bb for bb, t in raw if t and bb not in footer), key=lambda b: b[1])
    margin = min(b[0] for b in ls)
    # the equation sits between the nearest prose lines (lines starting at the left margin) above and below
    prose = [b for b in ls if b[0] <= margin + 15]
    above = [b[3] for b in prose if (b[1] + b[3]) / 2 < y - 4]
    below = [b[1] for b in prose + footer if (b[1] + b[3]) / 2 > y + 4]
    top = max(max(above, default=y - 60), y - 70)
    bot = min(min(below, default=y + 60), y + 70)
    pix = page.get_pixmap(dpi=200, clip=pymupdf.Rect(x0, top, x1, bot + 1))
    return trim(Image.frombytes('RGB', (pix.width, pix.height), pix.samples))

PRE = r'''\documentclass[11pt]{article}\usepackage{amsmath,amssymb,mathtools,bm}
\usepackage[paperwidth=7in,paperheight=3in,margin=0.2in]{geometry}\pagestyle{empty}\begin{document}
\begin{equation*}%s\end{equation*}\end{document}'''

def retypeset(tex):
    with tempfile.TemporaryDirectory() as d:
        open(f'{d}/e.tex', 'w').write(PRE % tex)
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'e.tex'],
                           cwd=d, capture_output=True, text=True)
        if r.returncode: 
            err = [l for l in r.stdout.splitlines() if l.startswith('!')]
            return None, (err[0] if err else 'pdflatex failed')
        pix = pymupdf.open(f'{d}/e.pdf')[0].get_pixmap(dpi=200)
        return trim(Image.frombytes('RGB', (pix.width, pix.height), pix.samples)), None

eqs = [(m.group(1), re.search(r'\\tag\{([^}]*)\}', m.group(1))) for m in re.finditer(r'\$\$(.*?)\$\$', md, re.S)]
eqs = [(t, m.group(1)) for t, m in eqs if m]
panels, problems = [], []
for tex, tag in eqs:
    if tag not in where: problems.append(f'({tag}): not located in PDF'); continue
    new, err = retypeset(tex)
    if err: problems.append(f'({tag}): {err}'); continue
    orig = original(tag)
    w = max(orig.width, new.width) + 20
    p = Image.new('RGB', (w, orig.height + new.height + 50), 'white'); dr = ImageDraw.Draw(p)
    dr.text((4, 2), f'({tag}) PDF', fill='red'); p.paste(orig, (10, 14))
    dr.line((0, orig.height + 22, w, orig.height + 22), fill='red')
    dr.text((4, orig.height + 26), f'({tag}) transcript', fill='blue'); p.paste(new, (10, orig.height + 38))
    panels.append(p)
for k in range(0, len(panels), a.per_sheet):
    group = panels[k:k + a.per_sheet]; W = max(p.width for p in group)
    sheet = Image.new('RGB', (W, sum(p.height + 16 for p in group)), 'white'); y = 0
    for p in group: sheet.paste(p, (0, y)); y += p.height + 16
    sheet.save(f'{out}/sheet_{k // a.per_sheet + 1:02d}.png')
print(f'{len(panels)} equations on {-(-len(panels) // a.per_sheet)} sheets in {out}')
for p in problems: print('PROBLEM', p)
