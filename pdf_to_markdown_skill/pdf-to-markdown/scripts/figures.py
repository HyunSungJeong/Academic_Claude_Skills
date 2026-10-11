#!/usr/bin/env python3
"""Find figures by their captions and save each as an image for embedding.

usage: figures.py INPUT.pdf WORKDIR [--dpi 200] [--max-kb 1500]

A figure is anchored on its caption: a text block starting "Fig. N", "Figure N"
or "FIG. N". The figure is the graphics (vector paths, raster images) and the
small text inside them (axis labels, legends) directly above the caption, within
the caption's column, up to the nearest line of running prose. The region is
rendered whole, so composite figures (vector art + embedded heatmaps) stay intact.
Decorative graphics without a caption (logos, badges, icons) are ignored.

Writes WORKDIR/figures/figN.png (JPEG figN.jpg if the PNG exceeds --max-kb) and
WORKDIR/figures/check_figN.png: a low-resolution view of the surroundings with the
crop drawn as a red box, for checking that nothing is cut off or included by
mistake. Prints one line per figure. In the page Markdown, place a figure with
    ![Fig. N](figure:figN)
and assemble.py embeds the image itself, so the output is one self-contained file.
"""
import sys, os, re, argparse, statistics
import pymupdf

CAP = re.compile(r'\s*(?:Fig\.|Figure|FIG\.)\s*(\d+)')
ap = argparse.ArgumentParser()
ap.add_argument('pdf'); ap.add_argument('work')
ap.add_argument('--dpi', type=int, default=200)
ap.add_argument('--max-kb', type=int, default=1500)
a = ap.parse_args()
out = os.path.join(a.work, 'figures'); os.makedirs(out, exist_ok=True)
doc = pymupdf.open(a.pdf)
chk = pymupdf.open(a.pdf)   # separate copy: check boxes must never leak into figure renders
found = []

for pno, page in enumerate(doc, 1):
    d = page.get_text('dict')
    lines = []                                   # (bbox, text, size)
    for b in d['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            if t:
                lines.append((pymupdf.Rect(l['bbox']), t, max(s['size'] for s in l['spans'])))
    if not lines: continue
    body = statistics.mode(round(sz * 2) / 2 for _, t, sz in lines if len(t) > 30) if any(len(t) > 30 for _, t, _ in lines) else 10
    caps = [(pymupdf.Rect(b[:4]), CAP.match(b[4]).group(1)) for b in page.get_text('blocks') if CAP.match(b[4])]
    graphics = [pymupdf.Rect(dr['rect']) for dr in page.get_drawings()]
    for img in page.get_images(full=True):
        graphics += list(page.get_image_rects(img[0]))
    for cap, num in caps:
        colw = cap.width
        xl, xr = cap.x0 - 12, cap.x1 + 12
        inx = lambda r: r.x1 > xl and r.x0 < xr and (min(r.x1, xr) - max(r.x0, xl)) > 0.5 * min(r.width, colw) - 1
        # top limit: lowest line of running prose above the caption in this column
        prose = [r.y1 for r, t, sz in lines if r.y1 <= cap.y0 + 1 and inx(r) and len(t) >= 35
                 and r.width >= 0.7 * colw and abs(sz - body) <= 1.0 and not CAP.match(t)]
        # prose that is itself inside the figure would sit below graphics; take the lowest prose line
        # that has graphics below it
        top = 0
        for y in sorted(prose, reverse=True):
            if any(g.y0 >= y - 1 and g.y1 <= cap.y0 + 2 and inx(g) for g in graphics):
                top = y; break
        items = [g for g in graphics if g.y0 >= top - 1 and g.y1 <= cap.y0 + 2 and inx(g) and g.width * g.height > 0]
        items += [r for r, t, sz in lines if r.y0 >= top - 1 and r.y1 <= cap.y0 + 1 and inx(r) and not CAP.match(t)]
        if not any(g for g in graphics if g in items):
            print(f'fig{num} p{pno}: caption found but no graphics above it -> place by hand or skip'); continue
        reg = pymupdf.Rect(items[0])
        for r in items[1:]: reg |= r
        reg = (reg + (-3, -3, 3, 3)) & page.rect
        pix = page.get_pixmap(dpi=a.dpi, clip=reg)
        data, ext = pix.tobytes('png'), 'png'
        if len(data) > a.max_kb * 1024:
            data, ext = pix.tobytes('jpeg', jpg_quality=90), 'jpg'
        for e in ('png', 'jpg'):                 # no stale file of the other type
            if os.path.exists(f'{out}/fig{num}.{e}'): os.remove(f'{out}/fig{num}.{e}')
        open(f'{out}/fig{num}.{ext}', 'wb').write(data)
        # crop check: surroundings at low resolution with the crop outlined
        ctx = (reg + (-25, -25, 25, 25)) & page.rect
        cp = chk[pno - 1]
        shape = cp.new_shape(); shape.draw_rect(reg); shape.finish(color=(1, 0, 0), width=1.2)
        shape.commit()
        cp.get_pixmap(dpi=90, clip=ctx).save(f'{out}/check_fig{num}.png')
        found.append(num)
        print(f'fig{num} p{pno}: {pix.width}x{pix.height} {ext} {len(data)//1024} KB -> figure:fig{num} | check {out}/check_fig{num}.png')

print(f'{len(found)} figures in {out}' + ('' if found else ' (none: no captions starting "Fig." / "Figure" found)'))
